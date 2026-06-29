"""认证路由 /api/v1/auth/*"""
from __future__ import annotations

from dataclasses import asdict

import os

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, Request, Response, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.dependencies import CurrentUser, get_current_user
from app.core.exceptions import MultipleValidationError, NotAuthenticatedError, success
from app.core.security import create_access_token, create_refresh_token, decode_token
from app.db.models.user import User, UserStatus
from jose import JWTError
from urllib.parse import urlparse
from app.db.session import get_db
from app.rbac.constants import Permissions
from app.rbac.guards import block_if_must_change_password, require_permission
from app.schemas.auth import (
    BuyerRegisterIn,
    ChangePasswordIn,
    LoginIn,
    MeOut,
    RegisterOut,
    SupplierRegisterIn,
    TokenOut,
)
from app.schemas.me import ChangeEmailIn, ChangePhoneIn, ChangeUsernameIn, ProfileUpdateIn
from app.services import auth_service, me_service, verification_service
from app.services.credit.harvester.harvest_task import harvest_after_register
from app.services.credit.registration_hook import initialize_credit_for_new_supplier

from pydantic import BaseModel as _BaseModel

from email_validator import validate_email as ev_validate, EmailNotValidError
from sqlalchemy import and_, select
from app.constants.country_registration import (
    BUSINESS_CODE_EMAIL_ALREADY_REGISTERED,
    BUSINESS_CODE_PHONE_ALREADY_REGISTERED,
    BUSINESS_CODE_SUPPLIER_ALREADY_REGISTERED,
    COUNTRY_CODES,
    COUNTRY_META,
    DUPLICATE_REGISTRATION_ERROR_MESSAGE,
    EMAIL_ALREADY_REGISTERED_MESSAGE,
    LANGUAGE_CODES,
    PHONE_ALREADY_REGISTERED_MESSAGE,
    validate_registration_no,
)
from app.core.security import PASSWORD_RULE_MESSAGE, validate_password_strength
from app.db.models.supplier_organization import SupplierOrganization


# ---- 供应商注册:全量校验(格式 + 业务一次性返回) ----

# 与 schemas/auth.py 中 SUPPLIER_PHONE_REGEX 一致
import re
_SUPPLIER_PHONE_RE = re.compile(r"^[+0-9\s\-]{6,20}$")


def _validate_supplier_register(raw: dict) -> tuple["SupplierRegisterIn | None", list[dict]]:
    """手动跑全部格式校验,收集所有错误而不短路。
    返回 (parsed_body_or_None, format_errors)。
    """
    errors: list[dict] = []

    # 必填检查
    required = ["email", "name", "phone", "password", "company_name",
                 "country_code", "registration_no", "language_preference"]
    for f in required:
        if not raw.get(f):
            errors.append({"field": f, "code": 42200, "message": f"{f} 不能为空"})

    # 逐字段格式校验(仅在有值时校验)
    email = raw.get("email", "")
    if email:
        try:
            ev_validate(email, check_deliverability=False)
        except EmailNotValidError:
            errors.append({"field": "email", "code": 42200, "message": "邮箱格式不正确"})

    phone = raw.get("phone", "")
    # phone_region 优先用显式传入,回退到 country_code(供应商已有)
    phone_region = raw.get("phone_region") or raw.get("country_code") or None
    if phone:
        from app.core.phone import normalize_phone_to_e164, try_normalize_phone
        # 供应商覆盖 9 国,部分不在 SUPPORTED_REGIONS;尽力归一化,失败走宽松校验
        normalized = try_normalize_phone(phone, phone_region)
        if normalized is not None:
            raw["phone"] = normalized
        elif not _SUPPLIER_PHONE_RE.match(phone):
            errors.append({"field": "phone", "code": 42221,
                            "message": "联系电话格式不正确(6-20 位,允许 +、数字、空格、短横)"})

    password = raw.get("password", "")
    if password and not validate_password_strength(password):
        errors.append({"field": "password", "code": 42200, "message": PASSWORD_RULE_MESSAGE})

    name = raw.get("name", "")
    if name and len(name) > 100:
        errors.append({"field": "name", "code": 42200, "message": "联系人姓名不能超过 100 个字符"})

    company_name = raw.get("company_name", "")
    if company_name and len(company_name) > 200:
        errors.append({"field": "company_name", "code": 42200, "message": "公司名称不能超过 200 个字符"})

    country_code = raw.get("country_code", "")
    if country_code and country_code not in COUNTRY_CODES:
        errors.append({"field": "country_code", "code": 42200,
                        "message": f"country_code 必须是合法国家之一:{','.join(COUNTRY_CODES)}"})

    registration_no = raw.get("registration_no", "")
    if registration_no and country_code and country_code in COUNTRY_CODES:
        if not validate_registration_no(country_code, registration_no):
            hint = COUNTRY_META.get(country_code, {}).get("reg_no_hint", "格式不符")
            errors.append({"field": "registration_no", "code": 42200,
                            "message": f"注册号格式不符,应为:{hint}"})

    language_preference = raw.get("language_preference", "")
    if language_preference and language_preference not in LANGUAGE_CODES:
        errors.append({"field": "language_preference", "code": 42200,
                        "message": f"语言偏好必须是合法值之一:{','.join(LANGUAGE_CODES)}"})

    if errors:
        return None, errors

    # 格式全通过,用 Pydantic 构建对象
    try:
        body = SupplierRegisterIn(**raw)
    except Exception as e:
        # 防御：请求体含 schema 未定义的字段时 Pydantic 抛 extra_forbidden
        return None, [{"field": "unknown", "code": 42200, "message": str(e)}]
    return body, []


async def _check_supplier_duplicates(
    db: "AsyncSession", raw: dict, format_errors: list[dict],
) -> list[dict]:
    """对格式校验通过的字段,跑业务唯一性检查。"""
    errors: list[dict] = []
    errored_fields = {e["field"] for e in format_errors}

    # 注册号重复(需要 country_code 和 registration_no 都格式合法)
    if "country_code" not in errored_fields and "registration_no" not in errored_fields:
        country_code = raw.get("country_code", "")
        registration_no = raw.get("registration_no", "")
        if country_code and registration_no:
            row = await db.execute(
                select(SupplierOrganization.id).where(
                    and_(
                        SupplierOrganization.country_code == country_code,
                        SupplierOrganization.registration_no == registration_no,
                    )
                )
            )
            if row.scalar_one_or_none() is not None:
                errors.append({
                    "field": "registration_no",
                    "code": BUSINESS_CODE_SUPPLIER_ALREADY_REGISTERED,
                    "message": DUPLICATE_REGISTRATION_ERROR_MESSAGE,
                })

    # 邮箱重复(排除已停用账号)
    if "email" not in errored_fields:
        email = raw.get("email", "")
        if email:
            from app.db.models.user import User, UserStatus
            row = await db.execute(
                select(User.id).where(User.email == email, User.status != UserStatus.DISABLED)
            )
            if row.scalar_one_or_none() is not None:
                errors.append({
                    "field": "email",
                    "code": BUSINESS_CODE_EMAIL_ALREADY_REGISTERED,
                    "message": EMAIL_ALREADY_REGISTERED_MESSAGE,
                })

    # 手机号重复(排除已停用账号)
    if "phone" not in errored_fields:
        phone = raw.get("phone", "")
        if phone:
            from app.db.models.user import User, UserStatus
            row = await db.execute(
                select(User.id).where(User.phone == phone, User.status != UserStatus.DISABLED)
            )
            if row.scalar_one_or_none() is not None:
                errors.append({
                    "field": "phone",
                    "code": BUSINESS_CODE_PHONE_ALREADY_REGISTERED,
                    "message": PHONE_ALREADY_REGISTERED_MESSAGE,
                })

    return errors


router = APIRouter(prefix="/auth", tags=["auth"])


# ---- 验证码 Schemas ----

class SendCodeRequest(_BaseModel):
    email: str
    purpose: str  # REGISTER / RESET_PASSWORD


class SendCodeResponse(_BaseModel):
    message: str
    expires_in: int


class VerifyCodeRequest(_BaseModel):
    email: str
    code: str
    purpose: str


class VerifyCodeResponse(_BaseModel):
    verification_token: str
    expires_in: int


# ---- 验证码端点 ----

@router.post("/verification-code/send", summary="发送邮箱验证码")
async def send_verification_code(
    body: SendCodeRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    ip = request.client.host if request.client else None
    ua = request.headers.get("user-agent", "")[:255]
    try:
        _code, expires_in = await verification_service.send_code(
            db, body.email, body.purpose, ip, ua
        )
        await db.commit()
        return success(SendCodeResponse(message="Verification code sent", expires_in=expires_in).model_dump())
    except ValueError as e:
        msg = str(e)
        if msg.startswith("COOLDOWN:"):
            remaining = int(msg.split(":")[1])
            raise MultipleValidationError([{"field": "email", "code": 40104, "message": f"Please wait {remaining}s before resending"}])
        if msg == "IP_RATE_LIMIT":
            raise MultipleValidationError([{"field": "email", "code": 40105, "message": "Too many requests, please try again later"}])
        raise


@router.post("/verification-code/verify", summary="校验邮箱验证码")
async def verify_verification_code(
    body: VerifyCodeRequest,
    db: AsyncSession = Depends(get_db),
):
    try:
        token = await verification_service.verify_code(
            db, body.email, body.code, body.purpose
        )
        await db.commit()
        return success(VerifyCodeResponse(
            verification_token=token,
            expires_in=settings.VERIFICATION_TOKEN_EXPIRE_MINUTES * 60,
        ).model_dump())
    except ValueError as e:
        error_map = {
            "CODE_NOT_FOUND": (40101, "Invalid verification code"),
            "CODE_EXPIRED": (40102, "Verification code expired"),
            "MAX_ATTEMPTS": (40103, "Too many failed attempts"),
            "CODE_INVALID": (40101, "Invalid verification code"),
        }
        biz_code, biz_msg = error_map.get(str(e), (40100, "Verification failed"))
        raise MultipleValidationError([{"field": "code", "code": biz_code, "message": biz_msg}])


@router.post("/register/buyer", summary="BUYER 自助注册")
async def register_buyer(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
    # 文本字段
    verification_token: str = Form(...),           # 必填: 邮箱验证 token
    email: str = Form(...),
    whatsapp: str = Form(...),                     # 必填: WhatsApp 号码
    phone: str = Form(...),
    password: str = Form(...),
    name: str = Form(...),
    company_name: str = Form(""),                  # 可选，默认空
    address: str = Form(""),                       # 可选，默认空
    business_category_codes: list[str] = Form(default=[]),
    tin: str | None = Form(default=None),
    brela_no: str | None = Form(default=None),
    language_preference: str | None = Form(default=None),
    # 文件字段
    storefront_images: list[UploadFile] = File(default=[]),   # 可选，默认空
    license_images: list[UploadFile] | None = File(default=None),
):
    from app.services._buyer_utils import (
        validate_active_level1_categories,
        save_private_buyer_image,
        delete_private_buyer_image,
        ALLOWED_EXTENSIONS,
        MAX_IMAGE_SIZE,
    )
    from email_validator import validate_email as ev_validate_email, EmailNotValidError as EvNotValidError

    # ── 1. 先校验 verification_token ──
    try:
        verified_email = verification_service.consume_verification_token(verification_token)
    except ValueError:
        raise MultipleValidationError([{"field": "verification_token", "code": 40106, "message": "Email verification token invalid or expired"}])
    email = email.strip()
    if verified_email != email:
        raise MultipleValidationError([{"field": "email", "code": 40107, "message": "Email does not match verification token"}])

    # ── 2. 全量格式校验(一次性收集) ──
    errors: list[dict] = []

    # 邮箱格式
    if not email:
        errors.append({"field": "email", "code": 42200, "message": "请填写邮箱"})
    else:
        try:
            ev_validate_email(email)
        except EvNotValidError:
            errors.append({"field": "email", "code": 42200, "message": "邮箱格式不正确"})

    # 密码强度
    if not validate_password_strength(password):
        errors.append({"field": "password", "code": 42202, "message": PASSWORD_RULE_MESSAGE})

    # 地址有值时 strip（允许空，不强制）
    address = address.strip() if address else ""

    # 品类校验（选填，有值时才校验）
    if business_category_codes:
        try:
            await validate_active_level1_categories(db, business_category_codes)
        except Exception as e:
            code = getattr(e, "biz_code", 42204)
            errors.append({"field": "business_category_codes", "code": code, "message": str(e.detail) if hasattr(e, "detail") else str(e)})

    # 门店照片张数校验（0-10 张，不再强制至少 1 张）
    if len(storefront_images) > 10:
        errors.append({"field": "storefront_images", "code": 42205, "message": "门店照片最多 10 张"})

    # 图片格式预校验(门店)
    if storefront_images:
        for i, f in enumerate(storefront_images):
            ext = os.path.splitext(f.filename or "")[1].lower()
            if ext not in ALLOWED_EXTENSIONS:
                errors.append({"field": f"storefront_images[{i}]", "code": 42206, "message": f"图片格式不支持: {ext}"})

    if errors:
        raise MultipleValidationError(errors)

    # ── 3. 图片处理 + 落盘 ──
    saved_storefront: list[tuple[str, int, int, int]] = []
    saved_files: list[str] = []  # 回滚清理用

    try:
        for f in storefront_images:
            content = await f.read()
            if len(content) > MAX_IMAGE_SIZE:
                raise MultipleValidationError([{"field": "storefront_images", "code": 42207, "message": "图片超过 5MB"}])
            result = save_private_buyer_image(
                content,
                f.filename or "img.jpg",
                "buyer_orgs/storefront",
                square=False,
            )
            saved_storefront.append(result)
            saved_files.append(result[0])

        saved_license: list[tuple[str, int, int, int]] = []
        for f in (license_images or []):
            content = await f.read()
            if len(content) > MAX_IMAGE_SIZE:
                raise MultipleValidationError([{"field": "license_images", "code": 42207, "message": "图片超过 5MB"}])
            ext = os.path.splitext(f.filename or "")[1].lower()
            if ext not in ALLOWED_EXTENSIONS:
                raise MultipleValidationError([{"field": "license_images", "code": 42210, "message": f"证照图片格式不支持: {ext}"}])
            result = save_private_buyer_image(
                content,
                f.filename or "img.jpg",
                "buyer_orgs/licenses",
                square=False,
            )
            saved_license.append(result)
            saved_files.append(result[0])

        # ── 4. 业务写入 ──
        user, tokens = await auth_service.register_buyer(
            db,
            phone=phone,
            whatsapp=whatsapp,
            password=password,
            name=name.strip(),
            company_name=company_name.strip(),
            address=address,
            business_category_codes=business_category_codes,
            storefront_images=saved_storefront,
            email=email,
            tin=tin.strip() if tin else None,
            brela_no=brela_no.strip() if brela_no else None,
            license_images=saved_license if saved_license else None,
            language_preference=language_preference,
            request=request,
        )
    except Exception:
        # 事务失败:best-effort 清理已落盘图片
        for key in saved_files:
            try:
                delete_private_buyer_image(key)
            except Exception:
                pass
        raise

    # 注册即自动登录
    _set_refresh_cookie(response, tokens["refresh_token"])
    return success(TokenOut(
        access_token=tokens["access_token"],
        token_type=tokens["token_type"],
        expires_in=tokens["expires_in"],
    ).model_dump())


@router.post("/register/supplier", summary="SUPPLIER 自助注册")
async def register_supplier(
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    # 手动解析 + 全量校验(不依赖 Pydantic 自动 422 短路)
    # WHY:格式错误和业务错误(重复)要一次性返回,避免用户反复提交
    raw = await request.json()
    body, format_errors = _validate_supplier_register(raw)

    # 格式通过的字段继续跑业务校验(重复检查)
    business_errors = await _check_supplier_duplicates(db, raw, format_errors)

    all_errors = format_errors + business_errors
    if all_errors:
        raise MultipleValidationError(all_errors)

    user, supplier_org_id = await auth_service.register_supplier(
        db,
        email=body.email,
        name=body.name,
        phone=body.phone,
        password=body.password,
        company_name=body.company_name,
        country_code=body.country_code,
        registration_no=body.registration_no,
        language_preference=body.language_preference,
        request=request,
    )
    # 注册即评分:异步生成信用评分初始化(独立 session,失败不影响注册)
    background_tasks.add_task(
        initialize_credit_for_new_supplier, supplier_org_id=supplier_org_id
    )
    # Δ7:占位评分之后,链尾追加柬埔寨公开数据抓取(仅 KH 生效,内部自行判断)
    background_tasks.add_task(
        harvest_after_register, supplier_org_id=supplier_org_id
    )
    return success(RegisterOut(user_id=user.id, email=user.email).model_dump())


def _origin_allowed(origin_header: str | None, allowed: list[str]) -> bool:
    """Origin/Referer 白名单校验(CSRF 防御)。

    取 origin_header 的 scheme://host[:port],与 allowed 列表精确匹配。
    浏览器刷新页面不发 Origin/Referer，此时放行——
    CSRF 防护已由 SameSite=lax cookie 策略保证。
    """
    if not origin_header:
        return True
    parsed = urlparse(origin_header)
    if not parsed.scheme or not parsed.hostname:
        return False
    port = f":{parsed.port}" if parsed.port else ""
    normalized = f"{parsed.scheme}://{parsed.hostname}{port}"
    return normalized in allowed


def _set_refresh_cookie(response: Response, refresh_token: str) -> None:
    """统一封装:把 refresh token 写入 httpOnly cookie。"""
    response.set_cookie(
        key=settings.REFRESH_COOKIE_NAME,
        value=refresh_token,
        max_age=settings.REFRESH_COOKIE_MAX_AGE,
        path=settings.REFRESH_COOKIE_PATH,
        httponly=True,
        secure=settings.REFRESH_COOKIE_SECURE,
        samesite=settings.REFRESH_COOKIE_SAMESITE,
    )


@router.post("/login", summary="登录(access 在 body,refresh 在 httpOnly cookie)")
async def login(
    body: LoginIn,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    tokens = await auth_service.login(
        db,
        identifier=body.identifier,
        password=body.password,
        phone_region=body.phone_region,
        request=request,
    )
    # refresh 不入 body,通过 httpOnly cookie 下发
    _set_refresh_cookie(response, tokens["refresh_token"])
    return success(TokenOut(
        access_token=tokens["access_token"],
        token_type=tokens["token_type"],
        expires_in=tokens["expires_in"],
    ).model_dump())


@router.get("/me", summary="当前用户:roles + permissions + organization")
async def me(current: CurrentUser = Depends(get_current_user)):
    org = asdict(current.organization) if current.organization else None
    demo_set = {
        e.strip().lower()
        for e in settings.DEMO_EMAILS.split(",")
        if e.strip()
    }
    data = MeOut(
        id=current.id,
        email=current.email,
        username=current.username,
        name=current.name,
        phone=current.phone,
        status=current.status,
        must_change_password=current.must_change_password,
        language_preference=current.language_preference,
        roles=current.roles,
        permissions=current.permissions,
        organization=org,
        is_demo=(current.email or "").lower() in demo_set,
    ).model_dump()
    return success(data)


@router.post("/refresh", summary="用 httpOnly cookie 中的 refresh token 换新 access(并轮转 refresh)")
async def refresh(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    # 1. CSRF 防御:Origin/Referer 必须在白名单
    origin = request.headers.get("origin") or request.headers.get("referer")
    if not _origin_allowed(origin, settings.CORS_ORIGINS):
        raise NotAuthenticatedError("Invalid origin")

    # 2. 从 httpOnly cookie 读 refresh token
    refresh_token = request.cookies.get(settings.REFRESH_COOKIE_NAME)
    if not refresh_token:
        raise NotAuthenticatedError("No refresh token")

    # 3. 解码 + 校验(type 必须 refresh)
    try:
        payload = decode_token(refresh_token, expected_type="refresh")
    except JWTError:
        raise NotAuthenticatedError("Invalid refresh token")

    user_id_raw = payload.get("sub")
    if user_id_raw is None:
        raise NotAuthenticatedError("Invalid token payload")
    try:
        user_id = int(user_id_raw)
    except (TypeError, ValueError):
        raise NotAuthenticatedError("Invalid token payload")

    # 4. 用户必须 ACTIVE
    user = await db.get(User, user_id)
    if user is None or user.status != UserStatus.ACTIVE:
        raise NotAuthenticatedError("User unavailable")

    # 4.5 token_version 校验:refresh token 的 tv 必须匹配当前库值
    if int(payload.get("tv", -1)) != user.token_version:
        raise NotAuthenticatedError("Token revoked")

    # 5. 签新 access + 新 refresh(refresh 轮转,降低盗用窗口)
    new_access, expires_in = create_access_token(user.id, user.email, user.token_version)
    new_refresh = create_refresh_token(user.id, user.email, user.token_version)

    # 6. 新 refresh 写回 cookie
    _set_refresh_cookie(response, new_refresh)

    # 7. 返回新 access(refresh 静默,**不写 audit_logs** 避免噪音)
    return success({
        "access_token": new_access,
        "token_type": "Bearer",
        "expires_in": expires_in,
    })


@router.post("/logout", summary="登出(清 cookie + 写审计)")
async def logout(
    request: Request,
    response: Response,
    current: CurrentUser = Depends(require_permission(Permissions.AUTH_LOGOUT)),
    db: AsyncSession = Depends(get_db),
):
    await auth_service.logout(
        db, user_id=current.id, user_email=current.email, request=request
    )
    response.delete_cookie(
        key=settings.REFRESH_COOKIE_NAME,
        path=settings.REFRESH_COOKIE_PATH,
    )
    return success(None)


@router.post("/change-password", summary="修改自己密码(成功后自动签发新 token)")
async def change_password(
    body: ChangePasswordIn,
    request: Request,
    response: Response,
    current: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    tokens = await auth_service.change_password(
        db,
        user_id=current.id,
        old_password=body.old_password,
        new_password=body.new_password,
        request=request,
    )
    _set_refresh_cookie(response, tokens["refresh_token"])
    return success(TokenOut(
        access_token=tokens["access_token"],
        token_type=tokens["token_type"],
        expires_in=tokens["expires_in"],
    ).model_dump())


# ----- 自助资料管理 -----

def _me_payload(user) -> dict:
    """读取 User → 拼一份精简的资料返回(不含 roles/permissions)。"""
    return {
        "id": user.id,
        "email": user.email,
        "username": user.username,
        "name": user.name,
        "phone": user.phone,
        "status": user.status,
        "must_change_password": user.must_change_password,
    }


@router.patch(
    "/me/profile",
    summary="修改自己基础资料(无需密码)",
    dependencies=[Depends(block_if_must_change_password)],
)
async def update_my_profile(
    body: ProfileUpdateIn,
    request: Request,
    current: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    user = await me_service.update_profile(
        db,
        user_id=current.id,
        name=body.name,
        email=body.email,
        phone=body.phone,
        phone_region=body.phone_region,
        username=body.username,
        request=request,
    )
    return success(_me_payload(user))


@router.post(
    "/me/email",
    summary="修改自己登录邮箱(需当前密码)",
    dependencies=[Depends(block_if_must_change_password)],
)
async def change_my_email(
    body: ChangeEmailIn,
    request: Request,
    current: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    user = await me_service.change_email(
        db,
        user_id=current.id,
        new_email=body.new_email,
        current_password=body.current_password,
        request=request,
    )
    return success(_me_payload(user))


@router.post(
    "/me/username",
    summary="修改/清空自己登录用户名(需当前密码)",
    dependencies=[Depends(block_if_must_change_password)],
)
async def change_my_username(
    body: ChangeUsernameIn,
    request: Request,
    current: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    user = await me_service.change_username(
        db,
        user_id=current.id,
        new_username=body.new_username,
        current_password=body.current_password,
        request=request,
    )
    return success(_me_payload(user))


@router.post(
    "/me/phone",
    summary="修改/清空自己登录手机号(需当前密码)",
    dependencies=[Depends(block_if_must_change_password)],
)
async def change_my_phone(
    body: ChangePhoneIn,
    request: Request,
    current: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    user = await me_service.change_phone(
        db,
        user_id=current.id,
        new_phone=body.new_phone,
        current_password=body.current_password,
        phone_region=body.phone_region,
        request=request,
    )
    return success(_me_payload(user))


@router.patch(
    "/me/language",
    summary="切换语言偏好(写回 DB)",
    dependencies=[Depends(block_if_must_change_password)],
)
async def update_language_preference(
    body: dict,
    request: Request,
    current: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.constants.country_registration import LANGUAGE_CODES

    lang = body.get("language_preference", "")
    if lang not in LANGUAGE_CODES:
        from app.core.exceptions import ValidationFailedError
        raise ValidationFailedError(f"language_preference must be one of: {','.join(LANGUAGE_CODES)}")

    user = await db.get(User, current.id)
    old_lang = user.language_preference
    user.language_preference = lang

    from app.audit.constants import AuditAction, AuditResourceType
    from app.audit.logger import write_audit
    from app.db.models.audit_log import AuditStatus
    await write_audit(
        db,
        resource_type=AuditResourceType.USER,
        action=AuditAction.PROFILE_UPDATE,
        status=AuditStatus.SUCCESS,
        user_id=current.id,
        user_email=current.email,
        resource_id=current.id,
        request=request,
        extra={"changes": {"language_preference": {"old": old_lang, "new": lang}}},
        commit=False,
    )
    await db.commit()
    return success({"language_preference": lang})


# ===== 忘记密码（验证码模式，对齐阿里国际站） =====

# 内存存储验证码（MVP 单机；生产可改 Redis）
# key: email, value: {"code": "123456", "user_id": 1, "expires": timestamp}
import time as _time
_reset_codes: dict[str, dict] = {}


@router.post("/forgot-password", summary="忘记密码-发送验证码")
async def forgot_password(
    request: Request,
    db: AsyncSession = Depends(get_db),
    email: str = Form(...),
):
    """接收邮箱，校验是否已注册，发送6位验证码。"""
    import random
    from app.services.email_service import send_verification_code_email

    email = email.strip().lower()

    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if not user:
        raise MultipleValidationError([{
            "field": "email",
            "code": 40401,
            "message": "该邮箱未注册，请检查后重试",
        }])

    code = f"{random.randint(100000, 999999)}"
    _reset_codes[email] = {
        "code": code,
        "user_id": user.id,
        "expires": _time.time() + 600,  # 10 分钟有效
    }
    send_verification_code_email(email, code)

    return success(None, message="验证码已发送")


@router.post("/reset-password", summary="重置密码（验证码模式）")
async def reset_password(
    request: Request,
    db: AsyncSession = Depends(get_db),
    email: str = Form(...),
    code: str = Form(...),
    new_password: str = Form(...),
):
    """验证邮箱+验证码+设置新密码。"""
    from app.core.security import hash_password

    email = email.strip().lower()

    # 校验密码强度
    if not validate_password_strength(new_password):
        raise MultipleValidationError([{
            "field": "new_password",
            "code": 42202,
            "message": PASSWORD_RULE_MESSAGE,
        }])

    # 校验验证码
    entry = _reset_codes.get(email)
    if not entry or entry["code"] != code.strip():
        raise MultipleValidationError([{
            "field": "code",
            "code": 40101,
            "message": "验证码错误",
        }])
    if _time.time() > entry["expires"]:
        _reset_codes.pop(email, None)
        raise MultipleValidationError([{
            "field": "code",
            "code": 40102,
            "message": "验证码已过期，请重新获取",
        }])

    user_id = entry["user_id"]
    _reset_codes.pop(email, None)  # 一次性消费

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise MultipleValidationError([{
            "field": "email",
            "code": 40103,
            "message": "用户不存在",
        }])

    # 更新密码 + token_version（使旧 token 全部失效）
    user.password_hash = hash_password(new_password)
    user.token_version = (user.token_version or 0) + 1
    user.must_change_password = False
    await db.commit()

    return success(None, message="密码重置成功，请使用新密码登录")
