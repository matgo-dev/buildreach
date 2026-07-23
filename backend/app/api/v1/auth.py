"""认证路由 /api/v1/auth/*"""
from __future__ import annotations

from dataclasses import asdict

import os

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, Request, Response, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.dependencies import CurrentUser, get_current_user
from app.core.exceptions import BusinessError, MultipleValidationError, NotAuthenticatedError, success
from app.core.request_ip import get_client_ip
from app.core.security import create_access_token, create_refresh_token, decode_token, hash_password, verify_password
from app.db.models.user import User, UserStatus
from jose import JWTError
from urllib.parse import urlparse
from app.db.session import get_db
from app.rbac.guards import block_if_must_change_password
from app.schemas.auth import (
    BuyerRegisterIn,
    ChangePasswordIn,
    LoginIn,
    MeOut,
    RegisterOut,
    SupplierRegisterIn,
    TokenOut,
)
from app.schemas.me import ChangeEmailIn, ChangePhoneIn, ChangeUsernameIn, OrgUpdateIn, ProfileUpdateIn
from app.services import auth_service, me_service, session_service, verification_service
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
from app.db.models.buyer_member import BuyerMember
from app.db.models.zone import Zone, ZoneGrant


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
    # 买方注册邮箱验证关闭时,拒绝 REGISTER 发码(防御性:前端已隐藏该步骤)。
    # RESET_PASSWORD 不受影响 —— 密码找回本质上必须发邮件。
    if body.purpose == "REGISTER" and not settings.REQUIRE_EMAIL_VERIFICATION:
        raise BusinessError(
            status.HTTP_400_BAD_REQUEST,
            40008,
            "Email verification is disabled",
        )
    ip = get_client_ip(request)
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
        if msg == "EMAIL_SEND_FAILED":
            raise BusinessError(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                50301,
                "Email delivery failed, please try again later",
            )
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
        if str(e) == "CODE_INVALID":
            await db.commit()
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
    verification_token: str | None = Form(default=None),   # 邮箱验证 token(REQUIRE_EMAIL_VERIFICATION=false 时可空)
    email: str = Form(...),
    whatsapp: str = Form(""),                      # 与手机号二选一,至少填一个
    phone: str = Form(""),                         # 与 WhatsApp 二选一,至少填一个
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
        save_private_buyer_image_from_path,
        delete_private_buyer_image,
        ALLOWED_EXTENSIONS,
        MAX_IMAGE_SIZE,
    )
    from app.services.upload_pipeline import run_image_processing, stream_upload_file_to_temp
    from email_validator import validate_email as ev_validate_email, EmailNotValidError as EvNotValidError

    # ── 1. 邮箱验证(受 REQUIRE_EMAIL_VERIFICATION 门控）──
    email = email.strip()
    if settings.REQUIRE_EMAIL_VERIFICATION:
        # 校验 verification_token（同时标记 verification_code 为已使用）
        if not verification_token:
            raise MultipleValidationError([{"field": "verification_token", "code": 40106, "message": "Email verification token invalid or expired"}])
        try:
            verified_email = await verification_service.consume_verification_token(db, verification_token)
        except ValueError:
            raise MultipleValidationError([{"field": "verification_token", "code": 40106, "message": "Email verification token invalid or expired"}])
        if verified_email != email:
            raise MultipleValidationError([{"field": "email", "code": 40107, "message": "Email does not match verification token"}])
    # flag=false: 跳过邮箱验证(即使前端误传 token 也忽略)

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

    # 联系方式:手机号与 WhatsApp 二选一,至少填一个
    phone = phone.strip()
    whatsapp = whatsapp.strip()
    if not phone and not whatsapp:
        errors.append({"field": "phone", "code": 42211, "message": "手机号与 WhatsApp 至少填写一个"})

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

    def _raise_image_field_error(field: str, exc: BusinessError) -> None:
        message = getattr(exc, "biz_message", None) or str(exc.detail)
        raise MultipleValidationError([{
            "field": field,
            "code": getattr(exc, "biz_code", 42206),
            "message": message,
        }]) from exc

    try:
        for i, f in enumerate(storefront_images):
            try:
                temp_upload = await stream_upload_file_to_temp(
                    f,
                    max_size=MAX_IMAGE_SIZE,
                    suffix=os.path.splitext(f.filename or "")[1].lower(),
                )
            except ValueError:
                raise MultipleValidationError([{"field": f"storefront_images[{i}]", "code": 42207, "message": "图片超过 5MB"}])
            try:
                result = await run_image_processing(
                    save_private_buyer_image_from_path,
                    temp_upload.path,
                    f.filename or "img.jpg",
                    "buyer_orgs/storefront",
                    square=False,
                )
            except BusinessError as exc:
                _raise_image_field_error(f"storefront_images[{i}]", exc)
            finally:
                temp_upload.cleanup()
            saved_storefront.append(result)
            saved_files.append(result[0])

        saved_license: list[tuple[str, int, int, int]] = []
        for i, f in enumerate(license_images or []):
            ext = os.path.splitext(f.filename or "")[1].lower()
            if ext not in ALLOWED_EXTENSIONS:
                raise MultipleValidationError([{"field": f"license_images[{i}]", "code": 42210, "message": f"证照图片格式不支持: {ext}"}])
            try:
                temp_upload = await stream_upload_file_to_temp(
                    f,
                    max_size=MAX_IMAGE_SIZE,
                    suffix=ext,
                )
            except ValueError:
                raise MultipleValidationError([{"field": f"license_images[{i}]", "code": 42207, "message": "图片超过 5MB"}])
            try:
                result = await run_image_processing(
                    save_private_buyer_image_from_path,
                    temp_upload.path,
                    f.filename or "img.jpg",
                    "buyer_orgs/licenses",
                    square=False,
                )
            except BusinessError as exc:
                _raise_image_field_error(f"license_images[{i}]", exc)
            finally:
                temp_upload.cleanup()
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


@router.get("/me", summary="当前用户:roles + permissions + organization + zones")
async def me(
    current: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    org = asdict(current.organization) if current.organization else None
    demo_set = {
        e.strip().lower()
        for e in settings.DEMO_EMAILS.split(",")
        if e.strip()
    }

    # 当前用户可见的专区(经 buyer_members → zone_grants → zones,仅 ACTIVE 专区)。
    # 单条 JOIN 查询,避免 N+1。
    zone_rows = await db.execute(
        select(Zone.code, Zone.name_zh, Zone.name_en)
        .join(ZoneGrant, ZoneGrant.zone_id == Zone.id)
        .join(BuyerMember, BuyerMember.buyer_org_id == ZoneGrant.buyer_org_id)
        .where(BuyerMember.user_id == current.id, Zone.status == "ACTIVE")
    )
    zones = [
        {"code": row.code, "name_zh": row.name_zh, "name_en": row.name_en}
        for row in zone_rows
    ]

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
        zones=zones,
    ).model_dump()
    return success(data)


@router.post("/refresh", summary="用 httpOnly cookie 中的 refresh token 换新 access(CAS 轮换 + 重放检测)")
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

    # 5. 会话账本轮换(设计 §4)
    sid_raw = payload.get("sid")
    jti_raw = payload.get("jti")
    if sid_raw is None or jti_raw is None:
        # TODO(2026-07-29 后删除): 旧格式 refresh 兼容——现场建会话迁移,用户无感
        tokens = await session_service.issue_session_tokens(db, user)
        _set_refresh_cookie(response, tokens["refresh_token"])
        return success({
            "access_token": tokens["access_token"],
            "token_type": "Bearer",
            "expires_in": tokens["expires_in"],
        })

    try:
        sid = int(sid_raw)
    except (TypeError, ValueError):
        raise NotAuthenticatedError("Invalid token payload")

    status_, effective_jti = await session_service.rotate_or_resolve(
        db, sid=sid, user_id=user.id, presented_jti=str(jti_raw)
    )

    if status_ in ("ROTATED", "GRACE"):
        # 6. 新 refresh 写回 cookie(GRACE 幂等重发 current,不推进状态)
        new_access, expires_in = create_access_token(user.id, user.email, user.token_version)
        new_refresh = create_refresh_token(
            user.id, user.email, user.token_version, sid=sid, jti=effective_jti
        )
        _set_refresh_cookie(response, new_refresh)
        # 7. 正常轮换不写 audit_logs,避免噪音
        return success({
            "access_token": new_access,
            "token_type": "Bearer",
            "expires_in": expires_in,
        })

    if status_ == "KILLED":
        # 重放:罕见安全事件,值得记
        from app.audit.constants import AuditAction, AuditResourceType
        from app.audit.logger import write_audit
        from app.db.models.audit_log import AuditStatus
        await write_audit(
            db,
            resource_type=AuditResourceType.AUTH,
            action=AuditAction.REFRESH_REPLAY,
            status=AuditStatus.FAILED,
            user_id=user.id,
            user_email=user.email,
            request=request,
            error_message="refresh token replay detected, session revoked",
        )
    # KILLED / EXPIRED / MISSING 统一 401
    raise NotAuthenticatedError("Invalid refresh token")


@router.post("/logout", summary="登出(按 refresh cookie 吊销本设备会话 + 清 cookie + 写审计)")
async def logout(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """以 refresh cookie 为准吊销服务端会话(设计 §5)。

    不依赖 access token:access 过期(15min)而 refresh 尚在时,
    logout 必须仍能吊销服务端会话。CSRF 由 Origin 白名单 + SameSite 覆盖。
    无/坏 cookie 时幂等:仅清 cookie 返回 200。
    """
    origin = request.headers.get("origin") or request.headers.get("referer")
    if not _origin_allowed(origin, settings.CORS_ORIGINS):
        raise NotAuthenticatedError("Invalid origin")

    refresh_cookie = request.cookies.get(settings.REFRESH_COOKIE_NAME)
    if refresh_cookie:
        try:
            payload = decode_token(refresh_cookie, expected_type="refresh")
            user_id = int(payload["sub"])
            sid_raw = payload.get("sid")
            if sid_raw is not None:
                # 删行即吊销;老格式 cookie 无 sid → 无行可删,只清 cookie
                await session_service.revoke_session(
                    db, sid=int(sid_raw), user_id=user_id
                )
            await auth_service.logout(
                db,
                user_id=user_id,
                user_email=payload.get("email") or "",
                request=request,
            )  # write_audit 默认 commit,顺带提交 revoke
        except (JWTError, KeyError, TypeError, ValueError):
            pass  # 坏 cookie:幂等登出,不暴露细节

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


@router.patch(
    "/me/organization",
    summary="修改自己所属买方组织信息(仅 owner)",
    dependencies=[Depends(block_if_must_change_password)],
)
async def update_my_organization(
    body: OrgUpdateIn,
    request: Request,
    current: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    org = await me_service.update_buyer_organization(
        db,
        user_id=current.id,
        user_email=current.email,
        name=body.name,
        unified_social_credit_code=body.unified_social_credit_code,
        request=request,
    )
    return success({
        "type": "BUYER_ORG",
        "id": org.id,
        "name": org.name,
        "unified_social_credit_code": org.unified_social_credit_code,
        "status": org.status,
        "is_owner": True,
    })


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


@router.post("/forgot-password", summary="忘记密码-发送验证码")
async def forgot_password(
    request: Request,
    db: AsyncSession = Depends(get_db),
    email: str = Form(...),
):
    """发送重置密码验证码。响应不暴露邮箱是否存在。"""
    email = email.strip().lower()
    ip = get_client_ip(request)
    ua = request.headers.get("user-agent", "")[:255]

    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    # 防枚举:不存在 / 非 ACTIVE 账号都返回同样文案,且不发邮件。
    if user is None or user.status != UserStatus.ACTIVE:
        return success(None, message="如果该邮箱已注册，验证码已发送")

    try:
        await verification_service.send_code(
            db,
            email=email,
            purpose="RESET_PASSWORD",
            ip_address=ip,
            user_agent=ua,
        )
        await db.commit()
    except ValueError as exc:
        msg = str(exc)
        if msg.startswith("COOLDOWN:"):
            return success(None, message="如果该邮箱已注册，验证码已发送")
        if msg == "IP_RATE_LIMIT":
            raise MultipleValidationError([{
                "field": "email",
                "code": 40105,
                "message": "请求过于频繁，请稍后再试",
            }])
        if msg == "EMAIL_SEND_FAILED":
            raise BusinessError(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                50301,
                "邮件发送失败，请稍后重试",
            )
        raise

    return success(None, message="如果该邮箱已注册，验证码已发送")


@router.post("/reset-password", summary="重置密码（验证码模式）")
async def reset_password(
    request: Request,
    db: AsyncSession = Depends(get_db),
    email: str = Form(...),
    code: str = Form(...),
    new_password: str = Form(...),
):
    """验证邮箱+验证码+设置新密码。"""
    email = email.strip().lower()

    # 校验密码强度
    if not validate_password_strength(new_password):
        raise MultipleValidationError([{
            "field": "new_password",
            "code": 42202,
            "message": PASSWORD_RULE_MESSAGE,
        }])

    try:
        verification_token = await verification_service.verify_code(
            db,
            email=email,
            purpose="RESET_PASSWORD",
            code=code.strip(),
        )
        verified_email = await verification_service.consume_verification_token(
            db,
            verification_token,
            expected_purpose="RESET_PASSWORD",
        )
    except ValueError as exc:
        msg = str(exc)
        if msg == "CODE_INVALID":
            await db.commit()
        error_map = {
            "CODE_NOT_FOUND": (40101, "验证码错误"),
            "CODE_EXPIRED": (40102, "验证码已过期，请重新获取"),
            "MAX_ATTEMPTS": (40103, "验证码尝试次数过多，请重新获取"),
            "CODE_INVALID": (40101, "验证码错误"),
            "TOKEN_USED": (40104, "验证码已使用，请重新获取"),
            "TOKEN_EXPIRED": (40102, "验证码已过期，请重新获取"),
            "TOKEN_INVALID": (40101, "验证码错误"),
            "INVALID_TOKEN_PURPOSE": (40101, "验证码错误"),
        }
        code_num, message = error_map.get(msg, (40101, "验证码错误"))
        raise MultipleValidationError([{
            "field": "code",
            "code": code_num,
            "message": message,
        }])

    if verified_email != email:
        raise MultipleValidationError([{
            "field": "code",
            "code": 40101,
            "message": "验证码错误",
        }])

    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if user is None or user.status != UserStatus.ACTIVE:
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


# ===== 账户注销 =====

class DeactivateRequest(_BaseModel):
    password: str


@router.post("/deactivate", summary="注销账户(需当前密码确认)")
async def deactivate_account(
    body: DeactivateRequest,
    current: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """用户主动注销账户。注销后 token 立即失效,登录时给出专属提示。"""
    # 从 DB 重新加载以获取 password_hash(CurrentUser dataclass 不含此字段)
    user = await db.get(User, current.id)
    if user is None:
        raise MultipleValidationError([{"field": "password", "code": 40301, "message": "Incorrect password"}])

    if not verify_password(body.password, user.password_hash):
        raise MultipleValidationError([{"field": "password", "code": 40301, "message": "Incorrect password"}])

    user.status = UserStatus.DEACTIVATED
    user.token_version += 1
    await db.commit()

    return success({"message": "Account deactivated successfully"})
