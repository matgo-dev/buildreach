"""T3 · 手机号作登录凭证 + 改号接口。"""
from __future__ import annotations

import pytest


def _buyer_payload(*, email, phone=None, usc="91110000PHONETEST1"):
    p = {
        "email": email,
        "name": "P",
        "password": "Aa123456789",
        "company_name": "Phone 测试公司",
        "unified_social_credit_code": usc,
    }
    if phone is not None:
        p["phone"] = phone
    return p


async def _register(client, **overrides):
    p = _buyer_payload(**overrides)
    r = await client.post("/api/v1/auth/register/buyer", json=p)
    assert r.status_code == 200, r.text
    return p


async def _login(client, identifier, password="Aa123456789"):
    return await client.post(
        "/api/v1/auth/login", json={"identifier": identifier, "password": password}
    )


# ---------- 注册阶段:phone 格式 + 唯一 ----------

@pytest.mark.asyncio
async def test_register_phone_invalid_format(client):
    cases = ["1234567890", "12345678901", "1380013800", "abcdefghijk", "23800138000"]
    for bad in cases:
        r = await client.post(
            "/api/v1/auth/register/buyer",
            json=_buyer_payload(email=f"x{hash(bad)}@x.com", phone=bad, usc="91110000PHONEBAD01"),
        )
        assert r.status_code == 422, f"{bad!r} 应被拒,实际 {r.status_code}"


@pytest.mark.asyncio
async def test_register_duplicate_phone(client):
    await _register(client, email="first@p.com", phone="13955550001")
    r = await client.post(
        "/api/v1/auth/register/buyer",
        json=_buyer_payload(email="second@p.com", phone="13955550001", usc="91110000PHONEDUP01"),
    )
    assert r.status_code == 409


# ---------- 登录阶段:phone 作 identifier ----------

@pytest.mark.asyncio
async def test_login_by_phone_success(client):
    await _register(client, email="pl@x.com", phone="13955550002")
    r = await _login(client, "13955550002")
    assert r.status_code == 200, r.text
    assert r.json()["data"]["access_token"]


@pytest.mark.asyncio
async def test_login_by_phone_wrong_password(client):
    await _register(client, email="pl@x.com", phone="13955550003")
    r = await _login(client, "13955550003", password="WrongPass1")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_login_phone_not_found(client):
    r = await _login(client, "13900000000")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_login_audit_marks_phone_identifier(client, db_session):
    from sqlalchemy import select
    from app.db.models.audit_log import AuditLog

    await _register(client, email="pa@x.com", phone="13955550004")
    r = await _login(client, "13955550004")
    assert r.status_code == 200

    row = await db_session.execute(
        select(AuditLog).where(AuditLog.action == "LOGIN_SUCCESS").order_by(AuditLog.id.desc())
    )
    log = row.scalars().first()
    assert log is not None
    assert log.extra.get("identifier_used") == "phone"


# ---------- 改手机号 POST /auth/me/phone ----------

async def _login_token(client, identifier, password="Aa123456789"):
    r = await _login(client, identifier, password)
    assert r.status_code == 200
    return r.json()["data"]["access_token"]


@pytest.mark.asyncio
async def test_change_phone_success(client):
    await _register(client, email="cp@x.com", phone="13955550010")
    token = await _login_token(client, "cp@x.com")
    h = {"Authorization": f"Bearer {token}"}

    r = await client.post(
        "/api/v1/auth/me/phone",
        json={"new_phone": "13955550011", "current_password": "Aa123456789"},
        headers=h,
    )
    assert r.status_code == 200, r.text
    assert r.json()["data"]["phone"] == "13955550011"

    # 新号能登录
    r2 = await _login(client, "13955550011")
    assert r2.status_code == 200
    # 旧号不能再登录
    r3 = await _login(client, "13955550010")
    assert r3.status_code == 401


@pytest.mark.asyncio
async def test_change_phone_wrong_password(client):
    await _register(client, email="cp@x.com", phone="13955550012")
    token = await _login_token(client, "cp@x.com")
    r = await client.post(
        "/api/v1/auth/me/phone",
        json={"new_phone": "13955550013", "current_password": "WrongPass1"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_change_phone_conflict(client):
    await _register(client, email="a@x.com", phone="13955550020")
    await _register(client, email="b@x.com", phone="13955550021", usc="91110000PHONEOTH01")

    token = await _login_token(client, "a@x.com")
    r = await client.post(
        "/api/v1/auth/me/phone",
        json={"new_phone": "13955550021", "current_password": "Aa123456789"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 409


@pytest.mark.asyncio
async def test_change_phone_clear_then_cannot_login_by_phone(client):
    await _register(client, email="clr@x.com", phone="13955550030")
    token = await _login_token(client, "clr@x.com")
    r = await client.post(
        "/api/v1/auth/me/phone",
        json={"new_phone": None, "current_password": "Aa123456789"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    assert r.json()["data"]["phone"] is None

    bad = await _login(client, "13955550030")
    assert bad.status_code == 401


@pytest.mark.asyncio
async def test_change_phone_invalid_format(client):
    await _register(client, email="cpf@x.com", phone="13955550040")
    token = await _login_token(client, "cpf@x.com")
    r = await client.post(
        "/api/v1/auth/me/phone",
        json={"new_phone": "1234", "current_password": "Aa123456789"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_change_phone_audit_recorded(client, db_session):
    from sqlalchemy import select
    from app.db.models.audit_log import AuditLog

    await _register(client, email="cpa@x.com", phone="13955550050")
    token = await _login_token(client, "cpa@x.com")
    await client.post(
        "/api/v1/auth/me/phone",
        json={"new_phone": "13955550051", "current_password": "Aa123456789"},
        headers={"Authorization": f"Bearer {token}"},
    )
    row = await db_session.execute(
        select(AuditLog).where(AuditLog.action == "PHONE_CHANGE")
    )
    logs = row.scalars().all()
    assert len(logs) == 1
    assert logs[0].extra["old_phone"] == "13955550050"
    assert logs[0].extra["new_phone"] == "13955550051"
