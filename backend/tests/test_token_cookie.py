"""Token 存储重构测试:refresh 走 httpOnly cookie,access 留在 body。"""
from __future__ import annotations

import pytest

from app.core.config import settings

SUPER_EMAIL = settings.SUPER_ADMIN_EMAIL
SUPER_PASS = settings.SUPER_ADMIN_INITIAL_PASSWORD
COOKIE_NAME = settings.REFRESH_COOKIE_NAME
# 默认前端 origin
ALLOWED_ORIGIN = "http://localhost:3000"


async def _login(client, *, origin: str = ALLOWED_ORIGIN, email=SUPER_EMAIL, pwd=SUPER_PASS):
    return await client.post(
        "/api/v1/auth/login",
        json={"identifier": email, "password": pwd},
        headers={"Origin": origin},
    )


# ----- /auth/login -----

@pytest.mark.asyncio
async def test_login_no_refresh_in_body(client):
    """登录响应 body **不应**含 refresh_token。"""
    r = await _login(client)
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["access_token"]
    assert "refresh_token" not in data


@pytest.mark.asyncio
async def test_login_sets_refresh_cookie_httponly(client):
    """登录响应 Set-Cookie 应含 refresh_token,HttpOnly + Path 正确。"""
    r = await _login(client)
    assert r.status_code == 200
    set_cookie = r.headers.get("set-cookie", "")
    assert f"{COOKIE_NAME}=" in set_cookie
    assert "HttpOnly" in set_cookie or "httponly" in set_cookie.lower()
    assert f"Path={settings.REFRESH_COOKIE_PATH}" in set_cookie
    # httpx 会自动把 cookie 存入 jar
    assert COOKIE_NAME in r.cookies


# ----- /auth/refresh -----

@pytest.mark.asyncio
async def test_refresh_success_returns_new_access_and_rotates_cookie(client):
    """登录后调 refresh:返回新 access + Set-Cookie 写新 refresh(轮转)。"""
    login_r = await _login(client)
    old_cookie = login_r.cookies.get(COOKIE_NAME)
    assert old_cookie

    r = await client.post(
        "/api/v1/auth/refresh",
        headers={"Origin": ALLOWED_ORIGIN},
    )
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["access_token"]
    assert "refresh_token" not in data
    # 新 cookie 应已写入
    new_cookie = r.cookies.get(COOKIE_NAME)
    assert new_cookie


@pytest.mark.asyncio
async def test_refresh_without_cookie_returns_401(client):
    """无 cookie 直接调 refresh → 401。"""
    r = await client.post(
        "/api/v1/auth/refresh",
        headers={"Origin": ALLOWED_ORIGIN},
    )
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_refresh_with_invalid_origin_returns_401(client):
    """有合法 cookie 但 Origin 不在白名单 → 401。"""
    await _login(client)
    r = await client.post(
        "/api/v1/auth/refresh",
        headers={"Origin": "https://evil.example.com"},
    )
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_refresh_with_missing_origin_returns_401(client):
    """没有 Origin/Referer 头 → 401。"""
    await _login(client)
    r = await client.post("/api/v1/auth/refresh")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_refresh_with_forged_cookie_returns_401(client):
    """cookie 被伪造(JWT 签名错)→ 401。"""
    await _login(client)
    # 替换 cookie jar 中的值为垃圾
    client.cookies.set(COOKIE_NAME, "not-a-valid-jwt", path=settings.REFRESH_COOKIE_PATH)
    r = await client.post(
        "/api/v1/auth/refresh",
        headers={"Origin": ALLOWED_ORIGIN},
    )
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_refresh_rejects_access_token_in_cookie(client):
    """如果 cookie 里塞的是 access token(type=access)而非 refresh → 401。"""
    login_r = await _login(client)
    access = login_r.json()["data"]["access_token"]
    client.cookies.set(COOKIE_NAME, access, path=settings.REFRESH_COOKIE_PATH)
    r = await client.post(
        "/api/v1/auth/refresh",
        headers={"Origin": ALLOWED_ORIGIN},
    )
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_refresh_does_not_write_audit_log(client, db_session):
    """refresh 是静默动作,不应写 audit_logs(避免噪音爆炸)。"""
    from sqlalchemy import select
    from app.db.models.audit_log import AuditLog

    await _login(client)
    # 记 login 后已有的审计行数
    before = (await db_session.execute(select(AuditLog))).scalars().all()
    before_count = len(before)

    r = await client.post(
        "/api/v1/auth/refresh",
        headers={"Origin": ALLOWED_ORIGIN},
    )
    assert r.status_code == 200

    after = (await db_session.execute(select(AuditLog))).scalars().all()
    assert len(after) == before_count, "refresh 不应写新审计"


# ----- /auth/logout 清 cookie -----

@pytest.mark.asyncio
async def test_logout_deletes_refresh_cookie(client):
    """登出响应应有 Set-Cookie: refresh_token=; Max-Age=0(或 expires 过去)。"""
    login_r = await _login(client)
    token = login_r.json()["data"]["access_token"]

    r = await client.post(
        "/api/v1/auth/logout",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    set_cookie = r.headers.get("set-cookie", "")
    assert f"{COOKIE_NAME}=" in set_cookie
    # 应有 Max-Age=0 或 expires 过期
    assert "Max-Age=0" in set_cookie or "max-age=0" in set_cookie.lower() or "expires" in set_cookie.lower()


# ----- 端到端 -----

@pytest.mark.asyncio
async def test_login_refresh_use_new_access_works(client):
    """完整链路:登录 → refresh → 用新 access 调 /me 成功。"""
    await _login(client)
    refresh_r = await client.post(
        "/api/v1/auth/refresh",
        headers={"Origin": ALLOWED_ORIGIN},
    )
    new_access = refresh_r.json()["data"]["access_token"]
    me = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {new_access}"},
    )
    assert me.status_code == 200
    assert me.json()["data"]["email"] == SUPER_EMAIL
