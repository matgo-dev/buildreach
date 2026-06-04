"""自助资料管理(/auth/me/*)测试。"""
from __future__ import annotations

import pytest
from sqlalchemy import select

from app.db.models.audit_log import AuditLog


REG_PAYLOAD = {
    "email": "alice@cscec3b.com",
    "username": "alice",
    "name": "Alice",
    "phone": "13800138000",
    "password": "Aa123456789",
    "company_name": "中建三局",
    "unified_social_credit_code": "91420100MA4KXXXX01",
}


async def _register_and_login(client) -> tuple[str, dict]:
    r = await client.post("/api/v1/auth/register/buyer", json=REG_PAYLOAD)
    assert r.status_code == 200, r.text
    login = await client.post(
        "/api/v1/auth/login",
        json={"identifier": REG_PAYLOAD["email"], "password": REG_PAYLOAD["password"]},
    )
    assert login.status_code == 200, login.text
    token = login.json()["data"]["access_token"]
    return token, {"Authorization": f"Bearer {token}"}


# ----- PATCH /me/profile -----

@pytest.mark.asyncio
async def test_update_profile_name_and_phone(client):
    _, h = await _register_and_login(client)
    r = await client.patch(
        "/api/v1/auth/me/profile",
        json={"name": "Alice Liu", "phone": "13911119999"},
        headers=h,
    )
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["name"] == "Alice Liu"
    assert data["phone"] == "13911119999"

    me = await client.get("/api/v1/auth/me", headers=h)
    assert me.json()["data"]["name"] == "Alice Liu"


@pytest.mark.asyncio
async def test_update_profile_partial(client):
    """只传 name 不传 phone,phone 不应被清空。"""
    _, h = await _register_and_login(client)
    r = await client.patch("/api/v1/auth/me/profile", json={"name": "New Name"}, headers=h)
    assert r.status_code == 200
    assert r.json()["data"]["phone"] == REG_PAYLOAD["phone"]  # 未动


@pytest.mark.asyncio
async def test_update_profile_clear_phone(client):
    """phone 传空字符串 → 清空。"""
    _, h = await _register_and_login(client)
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
    _, h = await _register_and_login(client)
    r = await client.post(
        "/api/v1/auth/me/email",
        json={"new_email": "alice2@cscec3b.com", "current_password": REG_PAYLOAD["password"]},
        headers=h,
    )
    assert r.status_code == 200
    assert r.json()["data"]["email"] == "alice2@cscec3b.com"

    # 老邮箱不能再登录
    bad = await client.post(
        "/api/v1/auth/login",
        json={"identifier": REG_PAYLOAD["email"], "password": REG_PAYLOAD["password"]},
    )
    assert bad.status_code == 401

    # 新邮箱可登录
    ok = await client.post(
        "/api/v1/auth/login",
        json={"identifier": "alice2@cscec3b.com", "password": REG_PAYLOAD["password"]},
    )
    assert ok.status_code == 200


@pytest.mark.asyncio
async def test_change_email_wrong_password(client):
    _, h = await _register_and_login(client)
    r = await client.post(
        "/api/v1/auth/me/email",
        json={"new_email": "alice2@cscec3b.com", "current_password": "WrongPass1"},
        headers=h,
    )
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_change_email_conflict(client):
    # 先注册第二个账号(phone 用不同号,避免撞 UNIQUE)
    other = {**REG_PAYLOAD, "email": "bob@cscec3b.com", "username": "bob", "phone": "13900139001"}
    await client.post("/api/v1/auth/register/buyer", json=other)

    _, h = await _register_and_login(client)
    r = await client.post(
        "/api/v1/auth/me/email",
        json={"new_email": "bob@cscec3b.com", "current_password": REG_PAYLOAD["password"]},
        headers=h,
    )
    assert r.status_code == 409


@pytest.mark.asyncio
async def test_change_email_invalid_format(client):
    _, h = await _register_and_login(client)
    r = await client.post(
        "/api/v1/auth/me/email",
        json={"new_email": "not-an-email", "current_password": REG_PAYLOAD["password"]},
        headers=h,
    )
    assert r.status_code == 422


# ----- POST /me/username -----

@pytest.mark.asyncio
async def test_change_username_success(client):
    _, h = await _register_and_login(client)
    r = await client.post(
        "/api/v1/auth/me/username",
        json={"new_username": "alice_new", "current_password": REG_PAYLOAD["password"]},
        headers=h,
    )
    assert r.status_code == 200
    assert r.json()["data"]["username"] == "alice_new"

    # 新 username 可登录
    ok = await client.post(
        "/api/v1/auth/login",
        json={"identifier": "alice_new", "password": REG_PAYLOAD["password"]},
    )
    assert ok.status_code == 200


@pytest.mark.asyncio
async def test_change_username_clear(client):
    """new_username 为 null → 清空,此后只能用邮箱登录。"""
    _, h = await _register_and_login(client)
    r = await client.post(
        "/api/v1/auth/me/username",
        json={"new_username": None, "current_password": REG_PAYLOAD["password"]},
        headers=h,
    )
    assert r.status_code == 200
    assert r.json()["data"]["username"] is None

    # 用原 username 登录 → 401
    bad = await client.post(
        "/api/v1/auth/login",
        json={"identifier": REG_PAYLOAD["username"], "password": REG_PAYLOAD["password"]},
    )
    assert bad.status_code == 401


@pytest.mark.asyncio
async def test_change_username_wrong_password(client):
    _, h = await _register_and_login(client)
    r = await client.post(
        "/api/v1/auth/me/username",
        json={"new_username": "alice_new", "current_password": "WrongPass1"},
        headers=h,
    )
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_change_username_conflict(client):
    other = {**REG_PAYLOAD, "email": "bob@cscec3b.com", "username": "bob", "phone": "13900139002"}
    await client.post("/api/v1/auth/register/buyer", json=other)

    _, h = await _register_and_login(client)
    r = await client.post(
        "/api/v1/auth/me/username",
        json={"new_username": "bob", "current_password": REG_PAYLOAD["password"]},
        headers=h,
    )
    assert r.status_code == 409


@pytest.mark.asyncio
async def test_change_username_invalid_format(client):
    _, h = await _register_and_login(client)
    r = await client.post(
        "/api/v1/auth/me/username",
        json={"new_username": "ab", "current_password": REG_PAYLOAD["password"]},
        headers=h,
    )
    assert r.status_code == 422


# ----- 审计 -----

@pytest.mark.asyncio
async def test_audit_for_profile_changes(client, db_session):
    _, h = await _register_and_login(client)

    await client.patch("/api/v1/auth/me/profile", json={"name": "X"}, headers=h)
    await client.post(
        "/api/v1/auth/me/email",
        json={"new_email": "alice2@cscec3b.com", "current_password": REG_PAYLOAD["password"]},
        headers=h,
    )
    await client.post(
        "/api/v1/auth/me/username",
        json={"new_username": "alice_new", "current_password": REG_PAYLOAD["password"]},
        headers=h,
    )

    rows = (await db_session.execute(select(AuditLog))).scalars().all()
    actions = {r.action for r in rows}
    assert "PROFILE_UPDATE" in actions
    assert "EMAIL_CHANGE" in actions
    assert "USERNAME_CHANGE" in actions

    email_rows = [r for r in rows if r.action == "EMAIL_CHANGE"]
    assert email_rows[0].extra["old_email"] == REG_PAYLOAD["email"]
    assert email_rows[0].extra["new_email"] == "alice2@cscec3b.com"


@pytest.mark.asyncio
async def test_audit_for_failed_password_attempt(client, db_session):
    _, h = await _register_and_login(client)
    await client.post(
        "/api/v1/auth/me/email",
        json={"new_email": "x@x.com", "current_password": "BadPass1"},
        headers=h,
    )
    rows = (await db_session.execute(
        select(AuditLog).where(AuditLog.action == "EMAIL_CHANGE", AuditLog.status == "FAILED")
    )).scalars().all()
    assert len(rows) >= 1
