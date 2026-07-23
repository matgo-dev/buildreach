"""auth_sessions 会话账本:模型 + refresh 轮换 + logout 吊销 集成测试。

设计:docs/specs/2026-07-22-前台refresh会话吊销-设计.md
"""
from __future__ import annotations

from datetime import timedelta

import httpx
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


async def _login(client, *, email=SUPER_EMAIL, pwd=SUPER_PASS):
    return await client.post(
        "/api/v1/auth/login",
        json={"identifier": email, "password": pwd},
        headers={"Origin": ALLOWED_ORIGIN},
    )


async def _super_user_id(db_session):
    from app.db.models.user import User
    return (await db_session.execute(
        select(User.id).where(User.email == SUPER_EMAIL))).scalar_one()


@pytest.mark.asyncio
async def test_login_creates_session_row(client, db_session):
    """登录落会话行;cookie 里的 sid/jti 与行一致;响应形状不变。"""
    from app.core.security import decode_token
    from app.db.models.auth_session import AuthSession

    r = await _login(client)
    assert r.status_code == 200
    assert "refresh_token" not in r.json()["data"]  # 响应形状不变

    payload = decode_token(r.cookies.get(COOKIE_NAME), expected_type="refresh")
    uid = await _super_user_id(db_session)
    row = (await db_session.execute(
        select(AuthSession).where(AuthSession.user_id == uid)
    )).scalar_one()
    assert payload["sid"] == row.id
    assert payload["jti"] == row.current_jti


def _swap_refresh_cookie(client, value: str) -> None:
    """替换 client 的 refresh cookie(模拟另一个设备/旧 tab 的 cookie)。

    注:不显式传 domain——httpx 0.28 的 http.cookiejar 后端对无点号 host(测试用
    "test")的 domain 匹配会失真(eff_request_host 追加 ".local" 参与比对),
    显式传 domain="test" 反而匹配不上,cookie 发不出去。留空走隐式域名照样只
    对本 client 生效,足够模拟"换一个 cookie"。
    """
    jar = httpx.Cookies()
    jar.set(COOKIE_NAME, value, path=settings.REFRESH_COOKIE_PATH)
    client.cookies = jar


async def _refresh(client):
    return await client.post("/api/v1/auth/refresh", headers={"Origin": ALLOWED_ORIGIN})


@pytest.mark.asyncio
async def test_refresh_rotates_and_old_jti_grace_then_replay_kills(client, db_session):
    """轮换换代;宽限窗内旧 cookie 幂等重发且行不变;更老的代重放 → 杀会话。"""
    from app.core.security import decode_token
    from app.db.models.auth_session import AuthSession

    login_r = await _login(client)
    cookie_a = login_r.cookies.get(COOKIE_NAME)
    sid = decode_token(cookie_a, expected_type="refresh")["sid"]

    # 轮换:A → B
    r1 = await _refresh(client)
    assert r1.status_code == 200
    cookie_b = r1.cookies.get(COOKIE_NAME)
    jti_b = decode_token(cookie_b, expected_type="refresh")["jti"]

    # 宽限:旧 cookie A 再来 → 200,拿到 jti == current(B),行不变
    _swap_refresh_cookie(client, cookie_a)
    r2 = await _refresh(client)
    assert r2.status_code == 200
    jti_grace = decode_token(r2.cookies.get(COOKIE_NAME), expected_type="refresh")["jti"]
    assert jti_grace == jti_b
    row = (await db_session.execute(
        select(AuthSession).where(AuthSession.id == sid))).scalar_one()
    assert row.current_jti == jti_b  # 幂等:未推进状态

    # 再转一代:B → C,之后重放 A(更老的代)→ 401 且行被删
    _swap_refresh_cookie(client, cookie_b)
    r3 = await _refresh(client)
    assert r3.status_code == 200
    cookie_c = r3.cookies.get(COOKIE_NAME)

    _swap_refresh_cookie(client, cookie_a)
    r4 = await _refresh(client)
    assert r4.status_code == 401
    gone = (await db_session.execute(
        select(AuthSession).where(AuthSession.id == sid))).scalar_one_or_none()
    assert gone is None

    # 会话已死:最新 cookie C 也 401
    _swap_refresh_cookie(client, cookie_c)
    r5 = await _refresh(client)
    assert r5.status_code == 401


@pytest.mark.asyncio
async def test_refresh_old_format_token_migrates(client, db_session):
    """旧格式(无 sid/jti)refresh:过 tv 校验后现场建会话行,签新格式。"""
    from jose import jwt as jose_jwt
    from datetime import datetime, timezone, timedelta as td
    from app.core.security import decode_token
    from app.db.models.auth_session import AuthSession
    from app.db.models.user import User

    uid = await _super_user_id(db_session)
    tv = (await db_session.execute(
        select(User.token_version).where(User.id == uid))).scalar_one()
    now = datetime.now(timezone.utc)
    old_token = jose_jwt.encode(
        {"sub": str(uid), "email": SUPER_EMAIL, "type": "refresh", "tv": tv,
         "iat": int(now.timestamp()), "exp": int((now + td(days=7)).timestamp())},
        settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

    _swap_refresh_cookie(client, old_token)
    r = await _refresh(client)
    assert r.status_code == 200
    new_payload = decode_token(r.cookies.get(COOKIE_NAME), expected_type="refresh")
    assert "sid" in new_payload and "jti" in new_payload
    row = (await db_session.execute(
        select(AuthSession).where(AuthSession.id == new_payload["sid"]))).scalar_one()
    assert row.current_jti == new_payload["jti"]


@pytest.mark.asyncio
async def test_logout_revokes_only_own_device(client, db_session):
    """设备1 logout:自己的行被删、refresh 401;设备2 不受影响(多端刚需)。"""
    from app.db.models.auth_session import AuthSession

    r1 = await _login(client)
    cookie_dev1 = r1.cookies.get(COOKIE_NAME)
    r2 = await _login(client)
    cookie_dev2 = r2.cookies.get(COOKIE_NAME)
    uid = await _super_user_id(db_session)

    # 设备1 登出(不带 Authorization:模拟 access 已过期)
    _swap_refresh_cookie(client, cookie_dev1)
    r = await client.post("/api/v1/auth/logout", headers={"Origin": ALLOWED_ORIGIN})
    assert r.status_code == 200
    set_cookie = r.headers.get("set-cookie", "")
    assert f"{COOKIE_NAME}=" in set_cookie  # 清 cookie

    rows = (await db_session.execute(
        select(AuthSession).where(AuthSession.user_id == uid))).scalars().all()
    assert len(rows) == 1  # 只剩设备2

    # 设备1 的 refresh 已死
    _swap_refresh_cookie(client, cookie_dev1)
    assert (await _refresh(client)).status_code == 401
    # 设备2 不受影响
    _swap_refresh_cookie(client, cookie_dev2)
    assert (await _refresh(client)).status_code == 200


@pytest.mark.asyncio
async def test_logout_without_cookie_is_idempotent(client):
    """无 cookie 的 logout:200 + 清 cookie,不报错。"""
    client.cookies = httpx.Cookies()
    r = await client.post("/api/v1/auth/logout", headers={"Origin": ALLOWED_ORIGIN})
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_deactivate_clears_all_sessions(client, db_session):
    """注销账户:tv bump + 全部会话行清空。"""
    from tests.conftest import register_buyer_tz
    from app.db.models.auth_session import AuthSession
    from app.db.models.user import User

    result = await register_buyer_tz(client, phone="+255766000111")
    access = result["response"].json()["data"]["access_token"]
    uid = (await db_session.execute(
        select(User.id).where(User.phone == "+255766000111"))).scalar_one()

    r = await client.post(
        "/api/v1/auth/deactivate",
        json={"password": result["password"]},
        headers={"Authorization": f"Bearer {access}"},
    )
    assert r.status_code == 200
    rows = (await db_session.execute(
        select(AuthSession).where(AuthSession.user_id == uid))).scalars().all()
    assert rows == []


@pytest.mark.asyncio
async def test_force_logout_clears_all_sessions(client, superadmin_headers, db_session):
    """管理员强下:目标用户会话行清空 + 其 refresh 401。"""
    from tests.conftest import register_buyer_tz
    from app.db.models.auth_session import AuthSession
    from app.db.models.user import User

    result = await register_buyer_tz(client, phone="+255766000222")
    buyer_refresh = client.cookies.get(COOKIE_NAME)
    uid = (await db_session.execute(
        select(User.id).where(User.phone == "+255766000222"))).scalar_one()

    r = await client.post(
        f"/api/v1/admin/users/{uid}/force-logout", headers=superadmin_headers
    )
    assert r.status_code == 200
    rows = (await db_session.execute(
        select(AuthSession).where(AuthSession.user_id == uid))).scalars().all()
    assert rows == []

    _swap_refresh_cookie(client, buyer_refresh)
    assert (await _refresh(client)).status_code == 401


@pytest.mark.asyncio
async def test_change_password_clears_old_sessions_and_issues_new(client, db_session):
    """改密:旧会话行全清,只留新签发的一行;旧 refresh 401。"""
    from tests.conftest import register_buyer_tz
    from app.db.models.auth_session import AuthSession
    from app.db.models.user import User

    result = await register_buyer_tz(client, phone="+255766000333")
    old_refresh = client.cookies.get(COOKIE_NAME)
    access = result["response"].json()["data"]["access_token"]
    uid = (await db_session.execute(
        select(User.id).where(User.phone == "+255766000333"))).scalar_one()

    r = await client.post(
        "/api/v1/auth/change-password",
        json={"old_password": result["password"], "new_password": "newpass123"},
        headers={"Authorization": f"Bearer {access}",
                 "Origin": ALLOWED_ORIGIN},
    )
    assert r.status_code == 200
    rows = (await db_session.execute(
        select(AuthSession).where(AuthSession.user_id == uid))).scalars().all()
    assert len(rows) == 1  # 只剩改密后新签的一行

    _swap_refresh_cookie(client, old_refresh)
    assert (await _refresh(client)).status_code == 401
