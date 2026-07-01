"""自助资料管理(/auth/me/*)测试。"""
from __future__ import annotations

import pytest
from sqlalchemy import select

from app.db.models.audit_log import AuditLog
from tests.conftest import register_buyer_tz, _next_phone


# 固定密码
_PASSWORD = "Aa123456789"


async def _register_and_login(client) -> tuple[str, dict, str]:
    """注册买方并获取 token。返回 (token, headers, phone)。"""
    result = await register_buyer_tz(client, password=_PASSWORD, name="Alice")
    assert result["response"].status_code == 200, result["response"].text
    token = result["response"].json()["data"]["access_token"]
    return token, {"Authorization": f"Bearer {token}"}, result["phone"]


# ----- PATCH /me/profile -----

@pytest.mark.asyncio
async def test_update_profile_name_and_phone(client):
    _, h, _ = await _register_and_login(client)
    new_phone = _next_phone()
    r = await client.patch(
        "/api/v1/auth/me/profile",
        json={"name": "Alice Liu", "phone": new_phone},
        headers=h,
    )
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["name"] == "Alice Liu"
    assert data["phone"] == new_phone

    me = await client.get("/api/v1/auth/me", headers=h)
    assert me.json()["data"]["name"] == "Alice Liu"


@pytest.mark.asyncio
async def test_update_profile_partial(client):
    """只传 name 不传 phone,phone 不应被清空。"""
    _, h, phone = await _register_and_login(client)
    r = await client.patch("/api/v1/auth/me/profile", json={"name": "New Name"}, headers=h)
    assert r.status_code == 200
    assert r.json()["data"]["phone"] == phone  # 未动


@pytest.mark.asyncio
async def test_update_profile_clear_phone(client):
    """phone 传空字符串 → 清空。"""
    _, h, _ = await _register_and_login(client)
    r = await client.patch("/api/v1/auth/me/profile", json={"phone": ""}, headers=h)
    assert r.status_code == 200
    assert r.json()["data"]["phone"] is None


@pytest.mark.asyncio
async def test_update_profile_requires_auth(client):
    r = await client.patch("/api/v1/auth/me/profile", json={"name": "X"})
    assert r.status_code == 401


# ----- POST /me/email -----

@pytest.mark.asyncio
async def test_change_email_success_and_new_email_can_login(client):
    _, h, _ = await _register_and_login(client)
    new_email = f"alice2_{_next_phone().replace('+', '')}@test.com"
    r = await client.post(
        "/api/v1/auth/me/email",
        json={"new_email": new_email, "current_password": _PASSWORD},
        headers=h,
    )
    assert r.status_code == 200
    assert r.json()["data"]["email"] == new_email

    # 新邮箱可登录
    ok = await client.post(
        "/api/v1/auth/login",
        json={"identifier": new_email, "password": _PASSWORD},
    )
    assert ok.status_code == 200


@pytest.mark.asyncio
async def test_change_email_wrong_password(client):
    _, h, _ = await _register_and_login(client)
    r = await client.post(
        "/api/v1/auth/me/email",
        json={"new_email": "alice2@test.com", "current_password": "WrongPass1!"},
        headers=h,
    )
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_change_email_conflict(client):
    # 先注册第二个账号
    bob_email = f"bob{_next_phone().replace('+', '')}@gmail.com"
    result2 = await register_buyer_tz(client, email=bob_email)
    assert result2["response"].status_code == 200

    _, h, _ = await _register_and_login(client)
    r = await client.post(
        "/api/v1/auth/me/email",
        json={"new_email": bob_email, "current_password": _PASSWORD},
        headers=h,
    )
    assert r.status_code == 409


@pytest.mark.asyncio
async def test_change_email_invalid_format(client):
    _, h, _ = await _register_and_login(client)
    r = await client.post(
        "/api/v1/auth/me/email",
        json={"new_email": "not-an-email", "current_password": _PASSWORD},
        headers=h,
    )
    assert r.status_code == 422


# ----- POST /me/username -----

@pytest.mark.asyncio
async def test_change_username_success(client):
    _, h, _ = await _register_and_login(client)
    r = await client.post(
        "/api/v1/auth/me/username",
        json={"new_username": "alice_new", "current_password": _PASSWORD},
        headers=h,
    )
    assert r.status_code == 200
    assert r.json()["data"]["username"] == "alice_new"

    # 新 username 可登录
    ok = await client.post(
        "/api/v1/auth/login",
        json={"identifier": "alice_new", "password": _PASSWORD},
    )
    assert ok.status_code == 200


@pytest.mark.asyncio
async def test_change_username_clear(client):
    """new_username 为 null → 清空。"""
    _, h, _ = await _register_and_login(client)
    r = await client.post(
        "/api/v1/auth/me/username",
        json={"new_username": None, "current_password": _PASSWORD},
        headers=h,
    )
    assert r.status_code == 200
    assert r.json()["data"]["username"] is None


@pytest.mark.asyncio
async def test_change_username_wrong_password(client):
    _, h, _ = await _register_and_login(client)
    r = await client.post(
        "/api/v1/auth/me/username",
        json={"new_username": "alice_new", "current_password": "WrongPass1!"},
        headers=h,
    )
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_change_username_conflict(client):
    # 先注册第二个账号,设置 username
    result2 = await register_buyer_tz(client)
    token2 = result2["response"].json()["data"]["access_token"]
    await client.post(
        "/api/v1/auth/me/username",
        json={"new_username": "bob_user", "current_password": result2["password"]},
        headers={"Authorization": f"Bearer {token2}"},
    )

    _, h, _ = await _register_and_login(client)
    r = await client.post(
        "/api/v1/auth/me/username",
        json={"new_username": "bob_user", "current_password": _PASSWORD},
        headers=h,
    )
    assert r.status_code == 409


@pytest.mark.asyncio
async def test_change_username_invalid_format(client):
    _, h, _ = await _register_and_login(client)
    r = await client.post(
        "/api/v1/auth/me/username",
        json={"new_username": "ab", "current_password": _PASSWORD},
        headers=h,
    )
    assert r.status_code == 422


# ----- 审计 -----

@pytest.mark.asyncio
async def test_audit_for_profile_changes(client, db_session):
    _, h, _ = await _register_and_login(client)

    await client.patch("/api/v1/auth/me/profile", json={"name": "X"}, headers=h)
    new_email = f"audit_{_next_phone().replace('+', '')}@test.com"
    await client.post(
        "/api/v1/auth/me/email",
        json={"new_email": new_email, "current_password": _PASSWORD},
        headers=h,
    )
    await client.post(
        "/api/v1/auth/me/username",
        json={"new_username": "alice_audit", "current_password": _PASSWORD},
        headers=h,
    )

    rows = (await db_session.execute(select(AuditLog))).scalars().all()
    actions = {r.action for r in rows}
    assert "PROFILE_UPDATE" in actions
    assert "EMAIL_CHANGE" in actions
    assert "USERNAME_CHANGE" in actions


@pytest.mark.asyncio
async def test_audit_for_failed_password_attempt(client, db_session):
    _, h, _ = await _register_and_login(client)
    await client.post(
        "/api/v1/auth/me/email",
        json={"new_email": "x@x.com", "current_password": "BadPass1!"},
        headers=h,
    )
    rows = (await db_session.execute(
        select(AuditLog).where(AuditLog.action == "EMAIL_CHANGE", AuditLog.status == "FAILED")
    )).scalars().all()
    assert len(rows) >= 1
