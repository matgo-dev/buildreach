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


async def _make_user(db_session, email: str):
    from app.core.security import hash_password
    from app.db.models.user import User
    user = User(email=email, name="t", password_hash=hash_password("abc12345"),
                status="ACTIVE", must_change_password=False)
    db_session.add(user)
    await db_session.flush()
    return user


@pytest.mark.asyncio
async def test_issue_session_tokens_creates_row_and_binds_sid_jti(db_session):
    """签发落一行;token 里 sid=行id、jti=current_jti。"""
    from app.core.security import decode_token
    from app.db.models.auth_session import AuthSession
    from app.services import session_service

    user = await _make_user(db_session, "sess-issue@test.local")
    tokens = await session_service.issue_session_tokens(db_session, user)

    payload = decode_token(tokens["refresh_token"], expected_type="refresh")
    row = (await db_session.execute(
        select(AuthSession).where(AuthSession.user_id == user.id)
    )).scalar_one()
    assert payload["sid"] == row.id
    assert payload["jti"] == row.current_jti
    assert tokens["access_token"] and tokens["token_type"] == "Bearer"


@pytest.mark.asyncio
async def test_rotate_success_then_replay_kills(db_session):
    """CAS 轮换成功换代;宽限外重放老 jti → KILLED 且行被删。"""
    from unittest.mock import patch
    from app.db.models.auth_session import AuthSession
    from app.services import session_service

    user = await _make_user(db_session, "sess-rotate@test.local")
    tokens = await session_service.issue_session_tokens(db_session, user)
    from app.core.security import decode_token
    p = decode_token(tokens["refresh_token"], expected_type="refresh")
    sid, jti0 = p["sid"], p["jti"]

    status1, jti1 = await session_service.rotate_or_resolve(
        db_session, sid=sid, user_id=user.id, presented_jti=jti0)
    assert status1 == "ROTATED" and jti1 != jti0

    # 立刻重放 jti0:是 prev 且在宽限窗内 → GRACE,幂等返回 current(=jti1),行不变
    status2, jti2 = await session_service.rotate_or_resolve(
        db_session, sid=sid, user_id=user.id, presented_jti=jti0)
    assert (status2, jti2) == ("GRACE", jti1)
    row = (await db_session.execute(
        select(AuthSession).where(AuthSession.id == sid))).scalar_one()
    assert row.current_jti == jti1  # 幂等:未推进状态

    # 再转一代后,jti0 变成"更老的代" → KILL
    status3, jti3 = await session_service.rotate_or_resolve(
        db_session, sid=sid, user_id=user.id, presented_jti=jti1)
    assert status3 == "ROTATED"
    status4, _ = await session_service.rotate_or_resolve(
        db_session, sid=sid, user_id=user.id, presented_jti=jti0)
    assert status4 == "KILLED"
    gone = (await db_session.execute(
        select(AuthSession).where(AuthSession.id == sid))).scalar_one_or_none()
    assert gone is None


@pytest.mark.asyncio
async def test_rotate_missing_session(db_session):
    from app.services import session_service
    user = await _make_user(db_session, "sess-missing@test.local")
    status, _ = await session_service.rotate_or_resolve(
        db_session, sid=999999, user_id=user.id, presented_jti="x")
    assert status == "MISSING"


@pytest.mark.asyncio
async def test_cleanup_on_login_caps_sessions(db_session):
    """会话数达上限时删最旧,保留 MAX-1 条给新会话腾位。"""
    from app.db.models.auth_session import AuthSession
    from app.services import session_service

    user = await _make_user(db_session, "sess-cap@test.local")
    for _ in range(session_service.MAX_SESSIONS_PER_USER + 3):
        await session_service.issue_session_tokens(db_session, user)

    await session_service.cleanup_on_login(db_session, user_id=user.id)
    count = len((await db_session.execute(
        select(AuthSession.id).where(AuthSession.user_id == user.id)
    )).scalars().all())
    assert count == session_service.MAX_SESSIONS_PER_USER - 1


@pytest.mark.asyncio
async def test_cleanup_on_login_purges_expired(db_session):
    from datetime import timedelta
    from app.db.models.auth_session import AuthSession
    from app.services import session_service

    user = await _make_user(db_session, "sess-expire@test.local")
    now = _utcnow()
    db_session.add(AuthSession(user_id=user.id, current_jti="dead", prev_jti=None,
                               rotated_at=now - timedelta(days=8),
                               expires_at=now - timedelta(days=1)))
    await db_session.flush()
    await session_service.cleanup_on_login(db_session, user_id=user.id)
    left = (await db_session.execute(
        select(AuthSession).where(AuthSession.user_id == user.id)
    )).scalars().all()
    assert left == []
