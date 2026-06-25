"""验证码业务逻辑:生成、校验、token签发与消费。"""
from __future__ import annotations

import hashlib
import logging
import secrets
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from sqlalchemy import and_, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import (
    EmailAlreadyRegisteredError,
    VerificationCodeExhaustedError,
    VerificationCodeExpiredError,
    VerificationCodeInvalidError,
    VerificationCooldownError,
    VerificationIpLimitError,
    VerificationTokenInvalidError,
    VerificationTokenUsedError,
)
from app.db.models.verification_code import VerificationCode, VerificationPurpose

logger = logging.getLogger(__name__)


def _now_utc() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _hash_code(code: str) -> str:
    return hashlib.sha256(code.encode()).hexdigest()


def _generate_code() -> str:
    """生成 N 位纯数字验证码。"""
    length = settings.VERIFICATION_CODE_LENGTH
    # 不用 randint 避免前导零丢失
    return "".join(secrets.choice("0123456789") for _ in range(length))


async def check_email_registered(db: AsyncSession, email: str) -> bool:
    from app.db.models.user import User
    result = await db.execute(
        select(User.id).where(func.lower(User.email) == email.lower()).limit(1)
    )
    return result.scalar_one_or_none() is not None


async def send_code(
    db: AsyncSession,
    *,
    email: str,
    purpose: str,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> tuple[str, int]:
    """生成验证码并存库。返回 (明文验证码, expires_in秒)。

    调用方负责实际发送邮件。
    """
    email_lower = email.lower()

    # 业务校验
    email_exists = await check_email_registered(db, email_lower)

    if purpose == VerificationPurpose.REGISTER and email_exists:
        raise EmailAlreadyRegisteredError()

    if purpose == VerificationPurpose.RESET_PASSWORD and not email_exists:
        # 防枚举:不暴露邮箱是否存在，但不实际发送
        # 返回假数据，调用方不发邮件
        return "", settings.VERIFICATION_CODE_EXPIRE_MINUTES * 60

    # 冷却检查:同一邮箱+purpose 60秒内不能重复发送
    cooldown_cutoff = _now_utc() - timedelta(seconds=settings.VERIFICATION_CODE_COOLDOWN_SECONDS)
    recent = await db.execute(
        select(VerificationCode.id).where(
            and_(
                func.lower(VerificationCode.email) == email_lower,
                VerificationCode.purpose == purpose,
                VerificationCode.created_at > cooldown_cutoff,
            )
        ).limit(1)
    )
    if recent.scalar_one_or_none() is not None:
        raise VerificationCooldownError()

    # IP 限频:同一IP每小时最多N次
    if ip_address:
        hour_ago = _now_utc() - timedelta(hours=1)
        ip_count_result = await db.execute(
            select(func.count()).where(
                and_(
                    VerificationCode.ip_address == ip_address,
                    VerificationCode.purpose == purpose,
                    VerificationCode.created_at > hour_ago,
                )
            )
        )
        ip_count = ip_count_result.scalar() or 0
        if ip_count >= settings.VERIFICATION_CODE_IP_HOURLY_LIMIT:
            raise VerificationIpLimitError()

    # 作废旧验证码
    await db.execute(
        update(VerificationCode)
        .where(
            and_(
                func.lower(VerificationCode.email) == email_lower,
                VerificationCode.purpose == purpose,
                VerificationCode.used == False,  # noqa: E712
            )
        )
        .values(used=True)
    )

    # 生成新验证码
    code = _generate_code()
    expires_at = _now_utc() + timedelta(minutes=settings.VERIFICATION_CODE_EXPIRE_MINUTES)

    record = VerificationCode(
        email=email_lower,
        code_hash=_hash_code(code),
        purpose=purpose,
        expires_at=expires_at,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    db.add(record)
    await db.flush()

    expires_in = settings.VERIFICATION_CODE_EXPIRE_MINUTES * 60
    return code, expires_in


async def verify_code(
    db: AsyncSession,
    *,
    email: str,
    code: str,
    purpose: str,
) -> str:
    """校验验证码，成功返回 verification_token (JWT)。"""
    email_lower = email.lower()
    now = _now_utc()

    # 查最近一条未使用、未过期的记录
    result = await db.execute(
        select(VerificationCode).where(
            and_(
                func.lower(VerificationCode.email) == email_lower,
                VerificationCode.purpose == purpose,
                VerificationCode.used == False,  # noqa: E712
            )
        ).order_by(VerificationCode.created_at.desc()).limit(1)
    )
    record = result.scalar_one_or_none()

    if record is None:
        raise VerificationCodeExpiredError()

    # 过期检查
    if record.expires_at < now:
        raise VerificationCodeExpiredError()

    # 尝试次数检查
    if record.attempts >= settings.VERIFICATION_CODE_MAX_ATTEMPTS:
        raise VerificationCodeExhaustedError()

    # 验证码比对
    if _hash_code(code) != record.code_hash:
        record.attempts += 1
        await db.flush()
        if record.attempts >= settings.VERIFICATION_CODE_MAX_ATTEMPTS:
            raise VerificationCodeExhaustedError()
        raise VerificationCodeInvalidError()

    # 验证成功:签发 verification_token (不标记 used，等消费时标记)
    token = _create_verification_token(
        email=email_lower,
        purpose=purpose,
        verification_code_id=record.id,
    )

    return token


def _create_verification_token(
    email: str,
    purpose: str,
    verification_code_id: int,
) -> str:
    """签发一次性 verification_token JWT。"""
    now = datetime.now(timezone.utc)
    exp = now + timedelta(minutes=settings.VERIFICATION_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": email,
        "purpose": purpose,
        "jti": str(verification_code_id),
        "type": "verification",
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_verification_token(token: str, expected_purpose: str) -> dict:
    """解码并校验 verification_token。返回 payload。"""
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    except JWTError:
        raise VerificationTokenInvalidError()

    if payload.get("type") != "verification":
        raise VerificationTokenInvalidError()
    if payload.get("purpose") != expected_purpose:
        raise VerificationTokenInvalidError()

    return payload


async def consume_verification_token(
    db: AsyncSession,
    token: str,
    expected_purpose: str,
) -> str:
    """解码 token 并标记验证码为已使用(事务内调用)。返回 email。"""
    payload = decode_verification_token(token, expected_purpose)
    email = payload["sub"]
    jti = int(payload["jti"])

    # 检查验证码是否已被消费
    result = await db.execute(
        select(VerificationCode).where(VerificationCode.id == jti)
    )
    record = result.scalar_one_or_none()
    if record is None:
        raise VerificationTokenInvalidError()
    if record.used:
        raise VerificationTokenUsedError()

    # 标记已使用
    record.used = True
    await db.flush()

    return email
