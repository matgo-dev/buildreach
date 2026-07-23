"""auth_sessions 会话账本:模型 + refresh 轮换 + logout 吊销 集成测试。

设计:docs/specs/2026-07-22-前台refresh会话吊销-设计.md
"""
from __future__ import annotations

from datetime import timedelta

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.db.base import _utcnow

SUPER_EMAIL = settings.SUPER_ADMIN_EMAIL
SUPER_PASS = settings.SUPER_ADMIN_INITIAL_PASSWORD
COOKIE_NAME = settings.REFRESH_COOKIE_NAME
ALLOWED_ORIGIN = "http://localhost:3000"


@pytest.mark.asyncio
async def test_auth_session_model_roundtrip(db_session):
    """模型可插可查,naive UTC 时间往返不变形。"""
    from app.db.models.auth_session import AuthSession
    from app.db.models.user import User
    from app.core.security import hash_password

    user = User(email="sess-model@test.local", name="t",
                password_hash=hash_password("abc12345"),
                status="ACTIVE", must_change_password=False)
    db_session.add(user)
    await db_session.flush()

    now = _utcnow()
    row = AuthSession(user_id=user.id, current_jti="jti-1", prev_jti=None,
                      rotated_at=now, expires_at=now + timedelta(days=7))
    db_session.add(row)
    await db_session.flush()

    got = (await db_session.execute(
        select(AuthSession).where(AuthSession.user_id == user.id)
    )).scalar_one()
    assert got.current_jti == "jti-1"
    assert got.prev_jti is None
    assert got.expires_at.tzinfo is None  # naive UTC 约定
