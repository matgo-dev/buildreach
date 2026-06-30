"""must_change_password 后端拦截 + Trace ID 信任开关测试。

覆盖工单 18 §六 全部 7 个验收场景。
"""
from __future__ import annotations

import uuid

import pytest

from app.core.config import settings


async def _login_bootstrap(client):
    """用引导管理员登录,返回 (token, headers)。"""
    r = await client.post(
        "/api/v1/auth/login",
        json={
            "identifier": settings.SUPER_ADMIN_EMAIL,
            "password": settings.SUPER_ADMIN_INITIAL_PASSWORD,
        },
    )
    assert r.status_code == 200
    token = r.json()["data"]["access_token"]
    return token, {"Authorization": f"Bearer {token}"}


# ── 场景 1: must_change=True 调业务 API → 403 / 40007 ──


@pytest.mark.asyncio
async def test_must_change_blocked_on_business_api(client):
    """引导管理员(must_change=True)调 GET /admin/users → 403, code=40007。"""
    _token, headers = await _login_bootstrap(client)
    r = await client.get("/api/v1/admin/users", headers=headers)
    assert r.status_code == 403
    assert r.json()["code"] == 40007


# ── 场景 2: 改密后 must_change 清零,再调业务 API → 200 ──


@pytest.mark.asyncio
async def test_must_change_cleared_after_password_change(client):
    """改密成功后,must_change=False,业务 API 放行。"""
    _token, headers = await _login_bootstrap(client)

    # 改密
    r = await client.post(
        "/api/v1/auth/change-password",
        headers=headers,
        json={
            "old_password": settings.SUPER_ADMIN_INITIAL_PASSWORD,
            "new_password": "NewPass999Aa",
        },
    )
    assert r.status_code == 200

    # 用新密码重新登录
    r2 = await client.post(
        "/api/v1/auth/login",
        json={"identifier": settings.SUPER_ADMIN_EMAIL, "password": "NewPass999Aa"},
    )
    assert r2.status_code == 200
    new_token = r2.json()["data"]["access_token"]
    new_headers = {"Authorization": f"Bearer {new_token}"}

    # 再调业务 API → 200
    r3 = await client.get("/api/v1/admin/users", headers=new_headers)
    assert r3.status_code == 200


# ── 场景 3: must_change token 调 GET /me 和 POST /logout → 豁免放行 ──


@pytest.mark.asyncio
async def test_must_change_exempt_me(client):
    """GET /me 在 must_change 期间放行。"""
    _token, headers = await _login_bootstrap(client)
    r = await client.get("/api/v1/auth/me", headers=headers)
    assert r.status_code == 200
    assert r.json()["data"]["must_change_password"] is True


@pytest.mark.asyncio
async def test_must_change_exempt_logout(client):
    """POST /logout 在 must_change 期间放行。"""
    _token, headers = await _login_bootstrap(client)
    r = await client.post("/api/v1/auth/logout", headers=headers)
    assert r.status_code == 200


# ── 场景 4: must_change token 调 PATCH /me/profile → 403 / 40007 ──


@pytest.mark.asyncio
async def test_must_change_blocked_on_profile(client):
    """PATCH /me/profile 在 must_change 期间被拦截。"""
    _token, headers = await _login_bootstrap(client)
    r = await client.patch(
        "/api/v1/auth/me/profile",
        headers=headers,
        json={"name": "New Name"},
    )
    assert r.status_code == 403
    assert r.json()["code"] == 40007


@pytest.mark.asyncio
async def test_must_change_blocked_on_email(client):
    """POST /me/email 在 must_change 期间被拦截。"""
    _token, headers = await _login_bootstrap(client)
    r = await client.post(
        "/api/v1/auth/me/email",
        headers=headers,
        json={"new_email": "new@test.com", "current_password": settings.SUPER_ADMIN_INITIAL_PASSWORD},
    )
    assert r.status_code == 403
    assert r.json()["code"] == 40007


@pytest.mark.asyncio
async def test_must_change_blocked_on_username(client):
    """POST /me/username 在 must_change 期间被拦截。"""
    _token, headers = await _login_bootstrap(client)
    r = await client.post(
        "/api/v1/auth/me/username",
        headers=headers,
        json={"new_username": "newuser", "current_password": settings.SUPER_ADMIN_INITIAL_PASSWORD},
    )
    assert r.status_code == 403
    assert r.json()["code"] == 40007


@pytest.mark.asyncio
async def test_must_change_blocked_on_phone(client):
    """POST /me/phone 在 must_change 期间被拦截。"""
    _token, headers = await _login_bootstrap(client)
    r = await client.post(
        "/api/v1/auth/me/phone",
        headers=headers,
        json={"new_phone": "13900001111", "current_password": settings.SUPER_ADMIN_INITIAL_PASSWORD},
    )
    assert r.status_code == 403
    assert r.json()["code"] == 40007


# ── 场景 5: TRUST_INBOUND_TRACE_ID=false,入站头被忽略 ──


@pytest.mark.asyncio
async def test_trace_id_untrusted_ignores_inbound(client, monkeypatch):
    """非信任模式:请求带 X-Trace-Id: foo → 响应头为服务端新生成 UUID(≠ foo)。"""
    monkeypatch.setattr(settings, "TRUST_INBOUND_TRACE_ID", False)
    r = await client.get("/healthz", headers={"X-Trace-Id": "foo"})
    trace = r.headers.get("X-Trace-Id")
    assert trace != "foo"
    # 应为合法 UUID
    uuid.UUID(trace)


# ── 场景 6: TRUST_INBOUND_TRACE_ID=true,合法 UUID 沿用 ──


@pytest.mark.asyncio
async def test_trace_id_trusted_valid_uuid(client, monkeypatch):
    """信任模式:合法 UUID 沿用。"""
    monkeypatch.setattr(settings, "TRUST_INBOUND_TRACE_ID", True)
    custom_id = str(uuid.uuid4())
    r = await client.get("/healthz", headers={"X-Trace-Id": custom_id})
    assert r.headers.get("X-Trace-Id") == custom_id


# ── 场景 7: TRUST_INBOUND_TRACE_ID=true,非法值被丢弃 ──


@pytest.mark.asyncio
async def test_trace_id_trusted_rejects_invalid(client, monkeypatch):
    """信任模式:非法值(含 <script> / 超短 / 超长)→ 重新生成。"""
    monkeypatch.setattr(settings, "TRUST_INBOUND_TRACE_ID", True)

    # <script> 注入
    r1 = await client.get("/healthz", headers={"X-Trace-Id": "<script>alert(1)</script>"})
    trace1 = r1.headers.get("X-Trace-Id")
    assert trace1 != "<script>alert(1)</script>"
    uuid.UUID(trace1)  # 应为合法 UUID

    # 过短(< 8 字符)
    r2 = await client.get("/healthz", headers={"X-Trace-Id": "abc"})
    trace2 = r2.headers.get("X-Trace-Id")
    assert trace2 != "abc"
    uuid.UUID(trace2)

    # 超长(> 128 字符)
    long_val = "a" * 200
    r3 = await client.get("/healthz", headers={"X-Trace-Id": long_val})
    trace3 = r3.headers.get("X-Trace-Id")
    assert trace3 != long_val
    uuid.UUID(trace3)