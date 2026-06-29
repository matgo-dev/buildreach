"""邮箱验证码服务：发码、校验、签发 verification_token。"""
from __future__ import annotations

import hashlib
import logging
import secrets
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from jose.exceptions import ExpiredSignatureError
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models.verification_code import VerificationCode, VerificationPurpose
from app.services.email_service import send_verification_code_email

logger = logging.getLogger(__name__)


def _generate_code() -> str:
    """生成 N 位数字验证码。"""
    return "".join(secrets.choice("0123456789") for _ in range(settings.VERIFICATION_CODE_LENGTH))


def _hash(code: str) -> str:
    return hashlib.sha256(code.encode()).hexdigest()


async def send_code(
    db: AsyncSession,
    email: str,
    purpose: str,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> tuple[str, int]:
    """发送验证码。

    Returns:
        (明文code, expires_in秒)

    Raises:
        ValueError: "COOLDOWN:{remaining_seconds}" — 冷却中
        ValueError: "IP_RATE_LIMIT" — IP 小时内超限
    """
    now = datetime.utcnow()

    # 冷却检查：同邮箱+purpose N 秒内不能重发
    last = (await db.execute(
        select(VerificationCode)
        .where(
            VerificationCode.email == email,
            VerificationCode.purpose == purpose,
        )
        .order_by(VerificationCode.created_at.desc())
        .limit(1)
    )).scalar_one_or_none()

    if last:
        # created_at 统一为 naive UTC 比较
        last_created = last.created_at.replace(tzinfo=None) if last.created_at.tzinfo else last.created_at
        elapsed = (now - last_created).total_seconds()
        if elapsed < settings.VERIFICATION_CODE_COOLDOWN_SECONDS:
            remaining = settings.VERIFICATION_CODE_COOLDOWN_SECONDS - int(elapsed)
            raise ValueError(f"COOLDOWN:{remaining}")

    # IP 小时限制
    if ip_address:
        one_hour_ago = now - timedelta(hours=1)
        count_result = await db.execute(
            select(func.count()).select_from(VerificationCode).where(
                and_(
                    VerificationCode.ip_address == ip_address,
                    VerificationCode.created_at >= one_hour_ago,
                )
            )
        )
        if count_result.scalar() >= settings.VERIFICATION_CODE_IP_HOURLY_LIMIT:
            raise ValueError("IP_RATE_LIMIT")

    # 作废同邮箱+purpose 的未用旧验证码
    old_codes = (await db.execute(
        select(VerificationCode).where(
            VerificationCode.email == email,
            VerificationCode.purpose == purpose,
            VerificationCode.used == False,  # noqa: E712
        )
    )).scalars().all()
    for oc in old_codes:
        oc.used = True

    # 生成新验证码
    code = _generate_code()
    expires_at = now + timedelta(minutes=settings.VERIFICATION_CODE_EXPIRE_MINUTES)
    vc = VerificationCode(
        email=email,
        code_hash=_hash(code),
        purpose=purpose,
        ip_address=ip_address,
        user_agent=user_agent,
        expires_at=expires_at,
    )
    db.add(vc)
    await db.flush()

    # 发送邮件（SMTP 未配置时 graceful degrade：验证码已 log 到 warning）
    send_verification_code_email(to_email=email, code=code, purpose=purpose)

    return code, settings.VERIFICATION_CODE_EXPIRE_MINUTES * 60


async def verify_code(
    db: AsyncSession,
    email: str,
    code: str,
    purpose: str,
) -> str:
    """验证码校验。成功返回 verification_token (JWT)，不会 mark used（由注册/重置接口在业务完成后处理）。

    Raises:
        ValueError: CODE_NOT_FOUND / CODE_EXPIRED / MAX_ATTEMPTS / CODE_INVALID
    """
    now = datetime.utcnow()

    vc = (await db.execute(
        select(VerificationCode).where(
            VerificationCode.email == email,
            VerificationCode.purpose == purpose,
            VerificationCode.used == False,  # noqa: E712
        ).order_by(VerificationCode.created_at.desc()).limit(1)
    )).scalar_one_or_none()

    if not vc:
        raise ValueError("CODE_NOT_FOUND")

    expires_at = vc.expires_at.replace(tzinfo=None) if vc.expires_at.tzinfo else vc.expires_at
    if now > expires_at:
        raise ValueError("CODE_EXPIRED")

    if vc.attempts >= settings.VERIFICATION_CODE_MAX_ATTEMPTS:
        raise ValueError("MAX_ATTEMPTS")

    if _hash(code) != vc.code_hash:
        vc.attempts += 1
        await db.flush()
        raise ValueError("CODE_INVALID")

    # 签发 verification_token，有效期独立于验证码
    token = jwt.encode(
        {
            "sub": email,
            "purpose": purpose,
            "jti": str(vc.id),
            "type": "verification",
            "exp": now + timedelta(minutes=settings.VERIFICATION_TOKEN_EXPIRE_MINUTES),
        },
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )
    return token


async def consume_verification_token(db: AsyncSession, token: str) -> str:
    """解码 verification_token，返回 email，并将对应 VerificationCode 标记为已使用。

    token 无效/过期时抛 ValueError。
    """
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        if payload.get("type") != "verification":
            raise ValueError("INVALID_TOKEN_TYPE")

        # 标记验证码为已使用，防止同一 code 被二次 verify
        code_id = payload.get("jti")
        if code_id:
            vc = (await db.execute(
                select(VerificationCode).where(VerificationCode.id == int(code_id))
            )).scalar_one_or_none()
            if vc:
                vc.used = True

        return payload["sub"]
    except ExpiredSignatureError:
        raise ValueError("TOKEN_EXPIRED")
    except (JWTError, KeyError):
        raise ValueError("TOKEN_INVALID")
