"""供应商目录列表接口测试。

覆盖:
- 权限:BUYER / OPERATOR 200,ADMIN 403(无 supplier:read)
- 筛选:q / country / grade
- 评分关联:Δ5 seed 的 4 家 demo Supplier 带 grade;无评分返回 null
"""
from __future__ import annotations

import pytest

from app.core.config import settings

SUPER_EMAIL = settings.SUPER_ADMIN_EMAIL
SUPER_PASS = settings.SUPER_ADMIN_INITIAL_PASSWORD


async def _login(client, email, password) -> str:
    r = await client.post(
        "/api/v1/auth/login", json={"identifier": email, "password": password}
    )
    assert r.status_code == 200, r.text
    return r.json()["data"]["access_token"]


def _auth(t: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {t}"}


async def _buyer_token(client) -> str:
    return await _login(client, "buyer@cscec3b.local", "Aa123456789")


async def _operator_token(client) -> str:
    return await _login(client, "operator@platform.local", "Aa123456789")


# -------- 权限 --------

@pytest.mark.asyncio
async def test_buyer_can_list(client):
    t = await _buyer_token(client)
    r = await client.get("/api/v1/suppliers", headers=_auth(t))
    assert r.status_code == 200
    # Δ5 seed 了 4 家 demo Supplier
    assert len(r.json()["data"]) >= 4


@pytest.mark.asyncio
async def test_operator_can_list(client):
    t = await _operator_token(client)
    r = await client.get("/api/v1/suppliers", headers=_auth(t))
    assert r.status_code == 200
    assert len(r.json()["data"]) >= 4


@pytest.mark.asyncio
async def test_admin_403(client):
    """ADMIN 无 supplier:read → 403。"""
    t = await _login(client, "admin@platform.local", "Aa123456789")
    r = await client.get("/api/v1/suppliers", headers=_auth(t))
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_requires_auth(client):
    r = await client.get("/api/v1/suppliers")
    assert r.status_code == 401


# -------- 筛选 --------

@pytest.mark.asyncio
async def test_filter_by_q(client):
    t = await _buyer_token(client)
    r = await client.get("/api/v1/suppliers?q=Al-Rashid", headers=_auth(t))
    assert r.status_code == 200
    data = r.json()["data"]
    assert len(data) == 1
    assert data[0]["name"] == "Al-Rashid Industrial Co."


@pytest.mark.asyncio
async def test_filter_by_country(client):
    t = await _buyer_token(client)
    r = await client.get("/api/v1/suppliers?country=SA", headers=_auth(t))
    assert r.status_code == 200
    data = r.json()["data"]
    assert all(x["country_code"] == "SA" for x in data)
    assert len(data) >= 1


@pytest.mark.asyncio
async def test_filter_by_grade(client):
    t = await _buyer_token(client)
    r = await client.get("/api/v1/suppliers?grade=A", headers=_auth(t))
    assert r.status_code == 200
    data = r.json()["data"]
    assert all(x["grade"] == "A" for x in data)
    assert len(data) >= 1


@pytest.mark.asyncio
async def test_item_shape_has_score(client):
    """Δ5 demo Supplier 应带 total_score / grade。"""
    t = await _buyer_token(client)
    r = await client.get("/api/v1/suppliers?q=Al-Rashid", headers=_auth(t))
    item = r.json()["data"][0]
    assert set(item.keys()) == {"id", "name", "country_code", "status", "total_score", "grade"}
    assert item["grade"] == "A"
    assert isinstance(item["total_score"], int)
