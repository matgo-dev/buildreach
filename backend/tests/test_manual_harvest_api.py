"""手动触发抓取 API 单测(Δ7 Step 12)。权限 + 参数校验 + 非 KH 拒绝。

monkeypatch manual_harvest 为 no-op,只验证 API 层(不真跑后台抓取)。
"""
from __future__ import annotations

import pytest

from app.db.models import CreditCompany


async def _login(client, email, password) -> str:
    r = await client.post("/api/v1/auth/login", json={"identifier": email, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["data"]["access_token"]


async def _operator_token(client) -> str:
    return await _login(client, "operator@platform.local", "Aa123456789")


async def _admin_token(client) -> str:
    return await _login(client, "admin@platform.local", "Aa123456789")


async def _register_supplier(client, email, phone) -> str:
    r = await client.post("/api/v1/auth/register/supplier", json={
        "email": email, "name": "S", "phone": phone, "password": "Aa123456789",
        "company_name": f"Co {phone}", "country_code": "CN",
        "registration_no": f"91110000{phone[1:6]}00001", "language_preference": "zh-CN"})
    assert r.status_code in (200, 201), r.text
    return await _login(client, email, "Aa123456789")


def _auth(t: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {t}"}


async def _make_company(db_session, country_code: str, regno: str) -> int:
    c = CreditCompany(name=f"{country_code} Co", country_code=country_code, registration_no=regno)
    db_session.add(c)
    await db_session.flush()
    return c.id


@pytest.fixture
def patched_harvest(monkeypatch):
    called: dict = {}

    async def fake(**kw):
        called.update(kw)

    monkeypatch.setattr("app.api.v1.credit.manual_harvest", fake)
    return called


async def test_operator_triggers_kh_company(client, db_session, patched_harvest):
    cid = await _make_company(db_session, "KH", "KH-API-1")
    t = await _operator_token(client)
    r = await client.post(f"/api/v1/credit/companies/{cid}/harvest", headers=_auth(t))
    assert r.status_code == 200, r.text
    assert r.json()["data"]["status"] == "queued"
    assert patched_harvest["company_id"] == cid
    assert patched_harvest["force_refresh"] is False


async def test_force_refresh_passed_through(client, db_session, patched_harvest):
    cid = await _make_company(db_session, "KH", "KH-API-2")
    t = await _operator_token(client)
    r = await client.post(
        f"/api/v1/credit/companies/{cid}/harvest?force_refresh=true", headers=_auth(t)
    )
    assert r.status_code == 200
    assert patched_harvest["force_refresh"] is True


async def test_non_kh_company_rejected(client, db_session, patched_harvest):
    cid = await _make_company(db_session, "CN", "CN-API-1")
    t = await _operator_token(client)
    r = await client.post(f"/api/v1/credit/companies/{cid}/harvest", headers=_auth(t))
    assert r.status_code == 400
    assert patched_harvest == {}  # 未排队


async def test_company_not_found(client, patched_harvest):
    t = await _operator_token(client)
    r = await client.post("/api/v1/credit/companies/999999/harvest", headers=_auth(t))
    assert r.status_code == 404


async def test_supplier_forbidden(client, patched_harvest):
    t = await _register_supplier(client, "harvest.sup@x.com", "13900140001")
    r = await client.post("/api/v1/credit/companies/1/harvest", headers=_auth(t))
    assert r.status_code == 403


async def test_admin_forbidden(client, patched_harvest):
    t = await _admin_token(client)
    r = await client.post("/api/v1/credit/companies/1/harvest", headers=_auth(t))
    assert r.status_code == 403
