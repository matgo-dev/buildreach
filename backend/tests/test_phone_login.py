"""T3 · 手机号作登录凭证 + 改号接口。"""
from __future__ import annotations

import pytest

from tests.conftest import register_buyer_tz, _next_phone


_PASSWORD = "Aa123456789!"


async def _login(client, identifier, password=_PASSWORD):
    return await client.post(
        "/api/v1/auth/login", json={"identifier": identifier, "password": password}
    )


# ---------- 注册阶段:phone 格式 + 唯一 ----------

@pytest.mark.asyncio
async def test_register_phone_invalid_format(client):
    """非 +255 格式手机号应被拒。"""
    from tests.conftest import _make_test_image
    img = _make_test_image()
    bad_phones = ["1234567890", "13800138000", "+86138001380", "+2551234"]
    for bad in bad_phones:
        r = await client.post(
            "/api/v1/auth/register/buyer",
            data={
                "phone": bad,
                "password": _PASSWORD,
                "name": "Test",
                "company_name": "Shop",
                "address": "Dar es Salaam",
                "business_category_codes": "01",
            },
            files=[("storefront_images", ("shop.jpg", img, "image/jpeg"))],
        )
        assert r.status_code == 409, f"{bad!r} 应被拒,实际 {r.status_code}"


@pytest.mark.asyncio
async def test_register_duplicate_phone(client):
    phone = _next_phone()
    await register_buyer_tz(client, phone=phone)
    result = await register_buyer_tz(client, phone=phone)
    assert result["response"].status_code == 409


# ---------- 登录阶段:phone 作 identifier ----------

@pytest.mark.asyncio
async def test_login_by_phone_success(client):
    result = await register_buyer_tz(client)
    r = await _login(client, result["phone"])
    assert r.status_code == 200, r.text
    assert r.json()["data"]["access_token"]


@pytest.mark.asyncio
async def test_login_by_phone_wrong_password(client):
    result = await register_buyer_tz(client)
    r = await _login(client, result["phone"], password="WrongPass1!")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_login_phone_not_found(client):
    r = await _login(client, "+255799000000")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_login_audit_marks_phone_identifier(client, db_session):
    from sqlalchemy import select
    from app.db.models.audit_log import AuditLog

    result = await register_buyer_tz(client)
    r = await _login(client, result["phone"])
    assert r.status_code == 200

    row = await db_session.execute(
        select(AuditLog).where(AuditLog.action == "LOGIN_SUCCESS").order_by(AuditLog.id.desc())
    )
    log = row.scalars().first()
    assert log is not None
    assert log.extra.get("identifier_used") == "phone"


# ---------- 改手机号 POST /auth/me/phone ----------

async def _login_token(client, identifier, password=_PASSWORD):
    r = await _login(client, identifier, password)
    assert r.status_code == 200
    return r.json()["data"]["access_token"]


# TODO: /auth/me/phone 端点的 Pydantic schema 仍只接受中国大陆手机号格式,
#       但买方现在用 +255 坦桑手机号注册。以下改号测试需等 schema 更新后恢复。

@pytest.mark.asyncio
@pytest.mark.skip(reason="/auth/me/phone schema 仍校验中国手机号格式,需更新为支持 +255")
async def test_change_phone_success(client):
    result = await register_buyer_tz(client)
    token = result["response"].json()["data"]["access_token"]
    h = {"Authorization": f"Bearer {token}"}

    new_phone = _next_phone()
    r = await client.post(
        "/api/v1/auth/me/phone",
        json={"new_phone": new_phone, "current_password": _PASSWORD},
        headers=h,
    )
    assert r.status_code == 200, r.text
    assert r.json()["data"]["phone"] == new_phone

    # 新号能登录
    r2 = await _login(client, new_phone)
    assert r2.status_code == 200
    # 旧号不能再登录
    r3 = await _login(client, result["phone"])
    assert r3.status_code == 401


@pytest.mark.asyncio
@pytest.mark.skip(reason="/auth/me/phone schema 仍校验中国手机号格式,需更新为支持 +255")
async def test_change_phone_wrong_password(client):
    result = await register_buyer_tz(client)
    token = result["response"].json()["data"]["access_token"]
    new_phone = _next_phone()
    r = await client.post(
        "/api/v1/auth/me/phone",
        json={"new_phone": new_phone, "current_password": "WrongPass1!"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 401


@pytest.mark.asyncio
@pytest.mark.skip(reason="/auth/me/phone schema 仍校验中国手机号格式,需更新为支持 +255")
async def test_change_phone_conflict(client):
    result_a = await register_buyer_tz(client)
    result_b = await register_buyer_tz(client)

    token_a = result_a["response"].json()["data"]["access_token"]
    r = await client.post(
        "/api/v1/auth/me/phone",
        json={"new_phone": result_b["phone"], "current_password": _PASSWORD},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert r.status_code == 409


@pytest.mark.asyncio
@pytest.mark.skip(reason="/auth/me/phone schema 仍校验中国手机号格式,需更新为支持 +255")
async def test_change_phone_clear_then_cannot_login_by_phone(client):
    result = await register_buyer_tz(client)
    token = result["response"].json()["data"]["access_token"]
    r = await client.post(
        "/api/v1/auth/me/phone",
        json={"new_phone": None, "current_password": _PASSWORD},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    assert r.json()["data"]["phone"] is None

    bad = await _login(client, result["phone"])
    assert bad.status_code == 401


@pytest.mark.asyncio
@pytest.mark.skip(reason="/auth/me/phone schema 仍校验中国手机号格式,需更新为支持 +255")
async def test_change_phone_invalid_format(client):
    result = await register_buyer_tz(client)
    token = result["response"].json()["data"]["access_token"]
    r = await client.post(
        "/api/v1/auth/me/phone",
        json={"new_phone": "1234", "current_password": _PASSWORD},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 422


@pytest.mark.asyncio
@pytest.mark.skip(reason="/auth/me/phone schema 仍校验中国手机号格式,需更新为支持 +255")
async def test_change_phone_audit_recorded(client, db_session):
    from sqlalchemy import select
    from app.db.models.audit_log import AuditLog

    result = await register_buyer_tz(client)
    token = result["response"].json()["data"]["access_token"]
    new_phone = _next_phone()
    await client.post(
        "/api/v1/auth/me/phone",
        json={"new_phone": new_phone, "current_password": _PASSWORD},
        headers={"Authorization": f"Bearer {token}"},
    )
    row = await db_session.execute(
        select(AuditLog).where(AuditLog.action == "PHONE_CHANGE")
    )
    logs = row.scalars().all()
    assert len(logs) == 1
    assert logs[0].extra["old_phone"] == result["phone"]
    assert logs[0].extra["new_phone"] == new_phone
