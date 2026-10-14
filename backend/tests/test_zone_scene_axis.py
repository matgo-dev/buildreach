"""专区「应用场景」轴(zone_categories.kind)集成测试。"""
from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.db.models.product import Product, ProductStatus, ProductVisibility
from app.db.models.zone import (
    ZONE_CATEGORY_KIND_CATEGORY,
    ZONE_CATEGORY_KIND_SCENE,
    Zone,
    ZoneCategory,
    ZoneGrant,
    ZoneProduct,
)

_DEFAULT_BUYER_EMAIL = "buyer@cscec3b.local"
_DEFAULT_BUYER_PASSWORD = "Aa123456789"


async def _login_default_buyer(client: AsyncClient) -> dict[str, str]:
    r = await client.post(
        "/api/v1/auth/login",
        json={"identifier": _DEFAULT_BUYER_EMAIL, "password": _DEFAULT_BUYER_PASSWORD},
    )
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['data']['access_token']}"}


async def _default_buyer_org_id(client: AsyncClient, headers: dict) -> int:
    r = await client.get("/api/v1/auth/me", headers=headers)
    assert r.status_code == 200, r.text
    return r.json()["data"]["organization"]["id"]


async def _grant(client: AsyncClient, db_session, zone: Zone) -> dict:
    headers = await _login_default_buyer(client)
    org_id = await _default_buyer_org_id(client, headers)
    db_session.add(ZoneGrant(zone_id=zone.id, buyer_org_id=org_id))
    await db_session.commit()
    return headers


async def _make_zone(db_session, code: str) -> Zone:
    zone = Zone(code=code, name_zh=f"{code} 专区", status="ACTIVE")
    db_session.add(zone)
    await db_session.flush()
    return zone


async def _make_zc(db_session, zone: Zone, code: str, kind: str, name: str, sort: int = 0) -> ZoneCategory:
    zc = ZoneCategory(zone_id=zone.id, code=code, name_zh=name, kind=kind, sort_order=sort)
    db_session.add(zc)
    await db_session.flush()
    return zc


async def _make_product(db_session, spu_code: str, name: str = "测试商品") -> Product:
    p = Product(
        spu_code=spu_code, name_zh=name, category_code="04.001",
        status=ProductStatus.ACTIVE, visibility=ProductVisibility.ZONE_ONLY, moq=1, unit="PCS",
    )
    db_session.add(p)
    await db_session.flush()
    return p


async def _attach(db_session, zone: Zone, zc: ZoneCategory, product: Product) -> None:
    db_session.add(ZoneProduct(zone_id=zone.id, spu_id=product.id, zone_category_id=zc.id))
    await db_session.flush()


@pytest.mark.asyncio
async def test_zone_categories_default_kind_category(client: AsyncClient, db_session):
    """未显式给 kind 的类目(常用材料现状)返回 kind=CATEGORY。"""
    zone = await _make_zone(db_session, "ZONE-KIND-DEFAULT")
    zc = ZoneCategory(zone_id=zone.id, code="01", name_zh="默认类目")
    db_session.add(zc)
    await db_session.flush()
    headers = await _grant(client, db_session, zone)

    r = await client.get(f"/api/v1/zones/{zone.code}/categories", headers=headers)
    assert r.status_code == 200, r.text
    items = r.json()["data"]
    assert len(items) == 1
    assert items[0]["code"] == "01"
    assert items[0]["kind"] == ZONE_CATEGORY_KIND_CATEGORY


@pytest.mark.asyncio
async def test_zone_categories_returns_scene_kind(client: AsyncClient, db_session):
    zone = await _make_zone(db_session, "ZONE-KIND-SCENE")
    await _make_zc(db_session, zone, "C01", ZONE_CATEGORY_KIND_CATEGORY, "大类", 0)
    await _make_zc(db_session, zone, "S01", ZONE_CATEGORY_KIND_SCENE, "场景", 1)
    headers = await _grant(client, db_session, zone)

    r = await client.get(f"/api/v1/zones/{zone.code}/categories", headers=headers)
    kinds = {i["code"]: i["kind"] for i in r.json()["data"]}
    assert kinds == {"C01": "CATEGORY", "S01": "SCENE"}
