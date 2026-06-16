"""认证 service:注册、登录、改密。"""
from __future__ import annotations

import logging

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request

from app.audit.constants import AuditAction, AuditResourceType
from app.audit.logger import write_audit
from app.constants.country_registration import (
    BUSINESS_CODE_EMAIL_ALREADY_REGISTERED,
    BUSINESS_CODE_PHONE_ALREADY_REGISTERED,
    BUSINESS_CODE_SUPPLIER_ALREADY_REGISTERED,
    DUPLICATE_REGISTRATION_ERROR_MESSAGE,
    EMAIL_ALREADY_REGISTERED_MESSAGE,
    PHONE_ALREADY_REGISTERED_MESSAGE,
)
from app.core.exceptions import (
    AccountDisabledError,
    ConflictError,
    InvalidCredentialsError,
    MultipleValidationError,
    NotFoundError,
    SupplierAlreadyRegisteredError,
    TooManyAttemptsError,
    ValidationFailedError,
)
from app.core.security import (
    PASSWORD_RULE_MESSAGE,
    create_access_token,
    create_refresh_token,
    hash_password,
    validate_password_strength,
    verify_password,
)
from app.db.models.audit_log import AuditStatus
from app.db.models.buyer_member import BuyerMember
from app.db.models.buyer_organization import BuyerOrganization, BuyerOrgStatus
from app.db.models.role import Role, RoleCode
from app.db.models.supplier_member import SupplierMember
from app.db.models.supplier_organization import SupplierOrganization
from app.db.models.user import User, UserStatus
from app.db.models.user_role import UserRole
from app.services.rate_limit import login_rate_limiter
from sqlalchemy.exc import IntegrityError

logger = logging.getLogger(__name__)


def _client_ip(request: Request | None) -> str:
    if request is None or request.client is None:
        return "-"
    return request.client.host or "-"


async def _get_role(db: AsyncSession, code: str) -> Role:
    row = await db.execute(select(Role).where(Role.code == code))
    role = row.scalar_one_or_none()
    if role is None:
        raise NotFoundError(f"Role not found: {code}")
    return role


async def _email_exists(db: AsyncSession, email: str) -> bool:
    row = await db.execute(select(User.id).where(User.email == email))
    return row.scalar_one_or_none() is not None


async def _username_exists(db: AsyncSession, username: str) -> bool:
    row = await db.execute(select(User.id).where(User.username == username))
    return row.scalar_one_or_none() is not None


async def _phone_exists(db: AsyncSession, phone: str) -> bool:
    row = await db.execute(select(User.id).where(User.phone == phone))
    return row.scalar_one_or_none() is not None


def _classify_identifier(identifier: str) -> str:
    """返回 'email' / 'phone' / 'username',用于日志和分支查询。

    phone 判定:能被 phonenumbers 解析为受支持的有效号即 phone,
    不再按长度/前缀猜测国家。
    """
    ident = identifier.strip()
    if "@" in ident:
        return "email"
    # 带 + 前缀或纯数字 ≥ 7 位 → 尝试作为 phone
    if ident.startswith("+") or (ident.isdigit() and len(ident) >= 7):
        return "phone"
    return "username"


async def _find_user_by_identifier(
    db: AsyncSession, identifier: str, phone_region: str | None = None,
) -> User | None:
    """三选一识别:邮箱(含 @) / 手机号 / 用户名。

    phone 分支:用 normalize_phone_to_e164 归一化后精确匹配,
    归一化失败则回退为 username 查。
    """
    from app.core.phone import normalize_phone_to_e164
    from app.core.exceptions import PhoneFormatError, PhoneUnsupportedRegionError

    ident = identifier.strip()
    kind = _classify_identifier(ident)
    if kind == "email":
        row = await db.execute(select(User).where(User.email == ident))
    elif kind == "phone":
        try:
            e164 = normalize_phone_to_e164(ident, phone_region)
            row = await db.execute(select(User).where(User.phone == e164))
        except (PhoneFormatError, PhoneUnsupportedRegionError):
            # 归一化失败:回退为 username 查(不暴露失败原因,防枚举)
            row = await db.execute(select(User).where(User.username == ident))
    else:
        row = await db.execute(select(User).where(User.username == ident))
    return row.scalar_one_or_none()


async def register_buyer(
    db: AsyncSession,
    *,
    phone: str,
    password: str,
    name: str,
    company_name: str,
    address: str,
    business_category_codes: list[str],
    storefront_images: list[tuple[str, int, int, int]],
    email: str | None = None,
    tin: str | None = None,
    brela_no: str | None = None,
    license_images: list[tuple[str, int, int, int]] | None = None,
    language_preference: str | None = None,
    request: Request | None = None,
) -> tuple[User, dict]:
    """坦桑尼亚买方自助注册(单事务聚合写 + 自动登录)。

    storefront_images / license_images 每个元素 = (image_key, w, h, file_size),
    即已由调用方处理落盘后的结果。
    返回 (user, token_dict)。
    """
    from app.db.models.buyer_browse_preference import BuyerBrowsePreference
    from app.db.models.buyer_org_image import BuyerOrgImage

    if not validate_password_strength(password):
        raise ValidationFailedError(PASSWORD_RULE_MESSAGE)

    # 唯一性一次性收集(不短路)
    errors: list[dict] = []
    if await _phone_exists(db, phone):
        errors.append({
            "field": "phone",
            "code": 40921,
            "message": "该手机号已注册",
        })
    if email and await _email_exists(db, email):
        errors.append({
            "field": "email",
            "code": 40922,
            "message": "该邮箱已注册",
        })
    if errors:
        raise MultipleValidationError(errors)

    # 单事务写入
    user = User(
        email=email,
        name=name,
        phone=phone,
        password_hash=hash_password(password),
        language_preference=language_preference or None,
        status=UserStatus.ACTIVE,
        must_change_password=False,
    )
    db.add(user)
    await db.flush()

    org = BuyerOrganization(
        name=company_name,
        address=address,
        tin=tin,
        brela_no=brela_no,
        business_category_codes=business_category_codes,
        status=BuyerOrgStatus.ACTIVE,
    )
    db.add(org)
    await db.flush()

    db.add(BuyerMember(user_id=user.id, buyer_org_id=org.id, is_owner=True))

    role = await _get_role(db, RoleCode.BUYER)
    db.add(UserRole(user_id=user.id, role_id=role.id))

    # 门店照片
    for idx, (key, w, h, fsize) in enumerate(storefront_images):
        db.add(BuyerOrgImage(
            buyer_org_id=org.id, image_key=key, image_type="STOREFRONT",
            sort_order=idx, width=w, height=h, file_size=fsize,
        ))

    # 证照图片
    for idx, (key, w, h, fsize) in enumerate(license_images or []):
        db.add(BuyerOrgImage(
            buyer_org_id=org.id, image_key=key, image_type="LICENSE",
            sort_order=idx, width=w, height=h, file_size=fsize,
        ))

    # 浏览偏好初始化 = 经营品类
    db.add(BuyerBrowsePreference(
        user_id=user.id,
        category_codes=business_category_codes,
    ))

    await write_audit(
        db,
        resource_type=AuditResourceType.USER,
        action=AuditAction.REGISTER,
        user_id=user.id,
        user_email=user.email or user.phone,
        resource_id=user.id,
        request=request,
        extra={
            "role": RoleCode.BUYER,
            "buyer_org_id": org.id,
        },
        commit=False,
    )
    await db.commit()
    await db.refresh(user)

    # 注册即自动登录:签发 token
    access_token, expires_in = create_access_token(user.id, user.email, user.token_version)
    refresh_token = create_refresh_token(user.id, user.email, user.token_version)

    return user, {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "Bearer",
        "expires_in": expires_in,
    }


async def register_supplier(
    db: AsyncSession,
    *,
    email: str,
    name: str,
    phone: str,
    password: str,
    company_name: str,
    country_code: str,
    registration_no: str,
    language_preference: str,
    request: Request | None = None,
) -> tuple[User, int]:
    """供应商自助注册(PRD v1.3 §4.3)。

    返回 (user, supplier_org_id) —— org_id 供注册接口注入异步评分初始化。

    唯一性按 (country_code, registration_no) 复合判定;不同国家可撞号。
    重复时抛 409 + 标准化文案,不暴露已有 owner / 公司名 / 任何字段。
    """
    if not validate_password_strength(password):
        raise ValidationFailedError(PASSWORD_RULE_MESSAGE)

    # v1.5 Δ3:收集所有唯一性冲突,一次性返回(不短路)
    # WHY:用户单次提交想一次拿到所有错误,避免反复试错
    errors: list[dict] = []
    # 顺序:registration_no(40901) → email(40902) → phone(40903),前端按该顺序定位首错滚动
    sup_row = await db.execute(
        select(SupplierOrganization.id).where(
            and_(
                SupplierOrganization.country_code == country_code,
                SupplierOrganization.registration_no == registration_no,
            )
        )
    )
    if sup_row.scalar_one_or_none() is not None:
        errors.append({
            "field": "registration_no",
            "code": BUSINESS_CODE_SUPPLIER_ALREADY_REGISTERED,
            "message": DUPLICATE_REGISTRATION_ERROR_MESSAGE,
        })
    if await _email_exists(db, email):
        errors.append({
            "field": "email",
            "code": BUSINESS_CODE_EMAIL_ALREADY_REGISTERED,
            "message": EMAIL_ALREADY_REGISTERED_MESSAGE,
        })
    if phone and await _phone_exists(db, phone):
        errors.append({
            "field": "phone",
            "code": BUSINESS_CODE_PHONE_ALREADY_REGISTERED,
            "message": PHONE_ALREADY_REGISTERED_MESSAGE,
        })

    if errors:
        raise MultipleValidationError(errors)

    user = User(
        email=email,
        name=name,
        phone=phone,
        password_hash=hash_password(password),
        status=UserStatus.ACTIVE,
        must_change_password=False,
        language_preference=language_preference,
    )
    db.add(user)
    await db.flush()

    org = SupplierOrganization(
        name=company_name,
        country_code=country_code,
        registration_no=registration_no,
        status="DRAFT",
    )
    db.add(org)
    await db.flush()

    db.add(SupplierMember(user_id=user.id, supplier_org_id=org.id, is_owner=True))
    role = await _get_role(db, RoleCode.SUPPLIER)
    db.add(UserRole(user_id=user.id, role_id=role.id))

    await write_audit(
        db,
        resource_type=AuditResourceType.USER,
        action=AuditAction.REGISTER,
        user_id=user.id,
        user_email=user.email,
        resource_id=user.id,
        request=request,
        extra={
            "role": RoleCode.SUPPLIER,
            "supplier_org_id": org.id,
            "country_code": country_code,
            "language_preference": language_preference,
        },
        commit=False,
    )
    await db.commit()
    await db.refresh(user)
    return user, org.id


async def login(
    db: AsyncSession,
    *,
    identifier: str,
    password: str,
    phone_region: str | None = None,
    request: Request | None = None,
) -> dict:
    """identifier 支持邮箱 / 手机号 / 用户名。限流以 identifier+ip 为 key。"""
    ip = _client_ip(request)
    rate_key = identifier.strip().lower()

    if login_rate_limiter.is_locked(rate_key, ip):
        await write_audit(
            db,
            resource_type=AuditResourceType.AUTH,
            action=AuditAction.LOGIN_LOCKED,
            status=AuditStatus.FAILED,
            user_email=identifier,
            request=request,
            error_message="locked",
            extra={"identifier": identifier},
        )
        raise TooManyAttemptsError()

    user = await _find_user_by_identifier(db, identifier, phone_region)

    # 用户不存在 / 密码错误 → 统一返回 401,防枚举
    if user is None or not verify_password(password, user.password_hash):
        locked_now = login_rate_limiter.record_failure(rate_key, ip)
        action = AuditAction.LOGIN_LOCKED if locked_now else AuditAction.LOGIN_FAILED
        await write_audit(
            db,
            resource_type=AuditResourceType.AUTH,
            action=action,
            status=AuditStatus.FAILED,
            user_email=user.email if user else identifier,
            user_id=user.id if user else None,
            request=request,
            error_message="invalid credentials",
            extra={"identifier": identifier},
        )
        if locked_now:
            raise TooManyAttemptsError()
        raise InvalidCredentialsError()

    if user.status == UserStatus.DISABLED:
        await write_audit(
            db,
            resource_type=AuditResourceType.AUTH,
            action=AuditAction.LOGIN_FAILED,
            status=AuditStatus.FAILED,
            user_id=user.id,
            user_email=user.email,
            request=request,
            error_message="account disabled",
        )
        raise AccountDisabledError()

    # 成功
    login_rate_limiter.reset(rate_key, ip)
    access_token, expires_in = create_access_token(user.id, user.email, user.token_version)
    refresh_token = create_refresh_token(user.id, user.email, user.token_version)
    await write_audit(
        db,
        resource_type=AuditResourceType.AUTH,
        action=AuditAction.LOGIN_SUCCESS,
        user_id=user.id,
        user_email=user.email,
        request=request,
        extra={"identifier_used": _classify_identifier(identifier)},
    )
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "Bearer",
        "expires_in": expires_in,
    }


async def change_password(
    db: AsyncSession,
    *,
    user_id: int,
    old_password: str,
    new_password: str,
    request: Request | None = None,
) -> None:
    user = await db.get(User, user_id)
    if user is None:
        raise NotFoundError("User not found")
    if not verify_password(old_password, user.password_hash):
        await write_audit(
            db,
            resource_type=AuditResourceType.AUTH,
            action=AuditAction.PASSWORD_CHANGE,
            status=AuditStatus.FAILED,
            user_id=user.id,
            user_email=user.email,
            request=request,
            error_message="old password incorrect",
        )
        raise InvalidCredentialsError("旧密码错误")
    if not validate_password_strength(new_password):
        raise ValidationFailedError(PASSWORD_RULE_MESSAGE)

    user.password_hash = hash_password(new_password)
    user.must_change_password = False
    # 吊销该用户所有旧 token(当前会话也随之失效,需重新登录)
    user.token_version += 1

    await write_audit(
        db,
        resource_type=AuditResourceType.AUTH,
        action=AuditAction.PASSWORD_CHANGE,
        user_id=user.id,
        user_email=user.email,
        request=request,
        commit=False,
    )
    await db.commit()


async def logout(
    db: AsyncSession,
    *,
    user_id: int,
    user_email: str,
    request: Request | None = None,
) -> None:
    """无状态 JWT 登出:仅写审计,前端自行清 token。"""
    await write_audit(
        db,
        resource_type=AuditResourceType.AUTH,
        action=AuditAction.LOGOUT,
        user_id=user_id,
        user_email=user_email,
        request=request,
    )


# ── 浏览偏好 ──────────────────────────────────────────────


async def get_browse_preferences(db: AsyncSession, user_id: int) -> list[str]:
    """读取买方浏览偏好品类 code 列表(过滤已停用品类)。"""
    from app.db.models.buyer_browse_preference import BuyerBrowsePreference
    from app.db.models.category import Category

    row = await db.execute(
        select(BuyerBrowsePreference).where(BuyerBrowsePreference.user_id == user_id)
    )
    pref = row.scalar_one_or_none()
    if pref is None or not pref.category_codes:
        return []

    # 过滤已停用品类(读取时过滤,不改存储)
    result = await db.execute(
        select(Category.code).where(
            Category.code.in_(pref.category_codes),
            Category.level == 1,
            Category.is_active == True,  # noqa: E712
        )
    )
    return [r[0] for r in result.all()]


async def replace_browse_preferences(
    db: AsyncSession,
    user_id: int,
    codes: list[str],
    request: Request | None = None,
) -> list[str]:
    """全量替换浏览偏好(仅允许操作本人)。"""
    from app.db.models.buyer_browse_preference import BuyerBrowsePreference
    from app.services._buyer_utils import validate_active_level1_categories

    await validate_active_level1_categories(db, codes)

    # 去重保序
    seen: set[str] = set()
    unique_codes = []
    for c in codes:
        if c not in seen:
            seen.add(c)
            unique_codes.append(c)

    row = await db.execute(
        select(BuyerBrowsePreference).where(BuyerBrowsePreference.user_id == user_id)
    )
    pref = row.scalar_one_or_none()
    if pref is None:
        pref = BuyerBrowsePreference(user_id=user_id, category_codes=unique_codes)
        db.add(pref)
    else:
        pref.category_codes = unique_codes

    await write_audit(
        db,
        resource_type=AuditResourceType.USER,
        action=AuditAction.UPDATE,
        user_id=user_id,
        resource_id=user_id,
        request=request,
        extra={"browse_preferences": unique_codes},
        commit=False,
    )
    await db.commit()
    return unique_codes
