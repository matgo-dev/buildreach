"""自助资料管理 service。

行业惯例:
- 改 name/phone 等低风险字段 → 不要求密码
- 改 email/username/password 等"登录凭证" → 要求 current_password 二次确认
- 每次变更写审计日志,old/new 入 extra 字段
- 唯一性字段(email/username)冲突 → 409
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request

from app.audit.constants import AuditAction, AuditResourceType
from app.audit.logger import write_audit
from app.core.exceptions import (
    ConflictError,
    InvalidCredentialsError,
    NotFoundError,
)
from app.core.phone import normalize_phone_to_e164, try_normalize_phone
from app.core.security import verify_password
from app.db.models.audit_log import AuditStatus
from app.db.models.user import User


async def _load_user(db: AsyncSession, user_id: int) -> User:
    user = await db.get(User, user_id)
    if user is None:
        raise NotFoundError("User not found")
    return user


async def _ensure_current_password(
    db: AsyncSession,
    user: User,
    current_password: str,
    *,
    audit_action: AuditAction,
    request: Request | None,
) -> None:
    """二次密码校验失败 → 写审计 + 401。"""
    if not verify_password(current_password, user.password_hash):
        await write_audit(
            db,
            resource_type=AuditResourceType.USER,
            action=audit_action,
            status=AuditStatus.FAILED,
            user_id=user.id,
            user_email=user.email,
            resource_id=user.id,
            request=request,
            error_message="current password incorrect",
        )
        raise InvalidCredentialsError("当前密码错误")


async def update_profile(
    db: AsyncSession,
    *,
    user_id: int,
    name: str | None,
    email: str | None = None,
    phone: str | None,
    phone_region: str | None = None,
    username: str | None = None,
    request: Request | None = None,
) -> User:
    """改基础资料。PATCH 语义:None=不动,空字符串=清空(phone/username)。"""
    user = await _load_user(db, user_id)

    changes: dict[str, dict[str, str | None]] = {}

    if name is not None and name != user.name:
        changes["name"] = {"old": user.name, "new": name}
        user.name = name

    if email is not None and email != user.email:
        row = await db.execute(
            select(User.id).where(User.email == email, User.id != user.id)
        )
        if row.scalar_one_or_none() is not None:
            raise ConflictError("该邮箱已被其他账号使用")
        changes["email"] = {"old": user.email, "new": email}
        user.email = email

    if phone is not None:
        new_phone = phone if phone != "" else None
        if new_phone is not None:
            new_phone = normalize_phone_to_e164(new_phone, phone_region)
            row = await db.execute(
                select(User.id).where(User.phone == new_phone, User.id != user.id)
            )
            if row.scalar_one_or_none() is not None:
                raise ConflictError("该手机号已被其他账号使用")
        if new_phone != user.phone:
            changes["phone"] = {"old": user.phone, "new": new_phone}
            user.phone = new_phone

    if username is not None:
        new_username = username if username != "" else None
        if new_username is not None:
            row = await db.execute(
                select(User.id).where(User.username == new_username, User.id != user.id)
            )
            if row.scalar_one_or_none() is not None:
                raise ConflictError("该用户名已被其他账号使用")
        if new_username != user.username:
            changes["username"] = {"old": user.username, "new": new_username}
            user.username = new_username

    if not changes:
        return user

    await write_audit(
        db,
        resource_type=AuditResourceType.USER,
        action=AuditAction.PROFILE_UPDATE,
        user_id=user.id,
        user_email=user.email,
        resource_id=user.id,
        request=request,
        extra={"changes": changes},
        commit=False,
    )
    await db.commit()
    await db.refresh(user)
    return user


async def change_email(
    db: AsyncSession,
    *,
    user_id: int,
    new_email: str,
    current_password: str,
    request: Request | None = None,
) -> User:
    """改登录邮箱。

    TODO(MVP 后续): 行业标准做法是发验证邮件到新邮箱确认后才生效。
    本项目 MVP 不引入邮件服务,简化为"密码二次确认 + 立即生效"。
    """
    user = await _load_user(db, user_id)

    if new_email == user.email:
        return user  # 无变更,幂等

    await _ensure_current_password(
        db, user, current_password,
        audit_action=AuditAction.EMAIL_CHANGE, request=request,
    )

    # 唯一性校验(防并发用 DB 唯一约束兜底)
    row = await db.execute(select(User.id).where(User.email == new_email, User.id != user.id))
    if row.scalar_one_or_none() is not None:
        raise ConflictError("该邮箱已被其他账号使用")

    old_email = user.email
    user.email = new_email

    await write_audit(
        db,
        resource_type=AuditResourceType.USER,
        action=AuditAction.EMAIL_CHANGE,
        user_id=user.id,
        user_email=new_email,  # 记新邮箱便于检索
        resource_id=user.id,
        request=request,
        extra={"old_email": old_email, "new_email": new_email},
        commit=False,
    )
    await db.commit()
    await db.refresh(user)
    return user


async def change_phone(
    db: AsyncSession,
    *,
    user_id: int,
    new_phone: str | None,
    current_password: str,
    phone_region: str | None = None,
    request: Request | None = None,
) -> User:
    """改/清空登录手机号。new_phone=None 或空字符串表示清空。"""
    user = await _load_user(db, user_id)

    new_value: str | None = new_phone if new_phone else None
    # 归一化为 E.164,与注册/登录保持一致
    if new_value is not None:
        new_value = normalize_phone_to_e164(new_value, phone_region)

    if new_value == user.phone:
        return user  # 无变更,幂等

    await _ensure_current_password(
        db, user, current_password,
        audit_action=AuditAction.PHONE_CHANGE, request=request,
    )

    if new_value is not None:
        row = await db.execute(
            select(User.id).where(User.phone == new_value, User.id != user.id)
        )
        if row.scalar_one_or_none() is not None:
            raise ConflictError("该手机号已被其他账号使用")

    old_phone = user.phone
    user.phone = new_value

    await write_audit(
        db,
        resource_type=AuditResourceType.USER,
        action=AuditAction.PHONE_CHANGE,
        user_id=user.id,
        user_email=user.email,
        resource_id=user.id,
        request=request,
        extra={"old_phone": old_phone, "new_phone": new_value},
        commit=False,
    )
    await db.commit()
    await db.refresh(user)
    return user


async def change_username(
    db: AsyncSession,
    *,
    user_id: int,
    new_username: str | None,
    current_password: str,
    request: Request | None = None,
) -> User:
    """改/清空登录用户名。new_username=None 表示清空。"""
    user = await _load_user(db, user_id)

    if new_username == user.username:
        return user

    await _ensure_current_password(
        db, user, current_password,
        audit_action=AuditAction.USERNAME_CHANGE, request=request,
    )

    if new_username is not None:
        row = await db.execute(
            select(User.id).where(User.username == new_username, User.id != user.id)
        )
        if row.scalar_one_or_none() is not None:
            raise ConflictError("该用户名已被其他账号使用")

    old_username = user.username
    user.username = new_username

    await write_audit(
        db,
        resource_type=AuditResourceType.USER,
        action=AuditAction.USERNAME_CHANGE,
        user_id=user.id,
        user_email=user.email,
        resource_id=user.id,
        request=request,
        extra={"old_username": old_username, "new_username": new_username},
        commit=False,
    )
    await db.commit()
    await db.refresh(user)
    return user
