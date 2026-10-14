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


async def _scene_fixture(client: AsyncClient, db_session, zone_code: str):
    """1 大类 C01 + 2 场景 S01/S02;商品 A 挂 C01+S01+S02,商品 B 挂 C01+S02。"""
    zone = await _make_zone(db_session, zone_code)
    c01 = await _make_zc(db_session, zone, "C01", ZONE_CATEGORY_KIND_CATEGORY, "劳保", 0)
    s01 = await _make_zc(db_session, zone, "S01", ZONE_CATEGORY_KIND_SCENE, "浮选厂", 1)
    s02 = await _make_zc(db_session, zone, "S02", ZONE_CATEGORY_KIND_SCENE, "井下", 2)
    a = await _make_product(db_session, f"{zone_code}-A", "帆布手套")
    b = await _make_product(db_session, f"{zone_code}-B", "安全帽")
    for zc in (c01, s01, s02):
        await _attach(db_session, zone, zc, a)
    for zc in (c01, s02):
        await _attach(db_session, zone, zc, b)
    headers = await _grant(client, db_session, zone)
    return zone, headers, a, b


@pytest.mark.asyncio
async def test_zone_products_multi_attach_listed_once(client: AsyncClient, db_session):
    """多挂商品在无筛选列表里只出现一次,total 也只计一次。"""
    zone, headers, a, b = await _scene_fixture(client, db_session, "ZONE-SC-ONCE")
    r = await client.get(f"/api/v1/zones/{zone.code}/products", headers=headers)
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["total"] == 2
    assert sorted(i["id"] for i in data["items"]) == sorted([a.id, b.id])


@pytest.mark.asyncio
async def test_zone_products_scene_filter(client: AsyncClient, db_session):
    zone, headers, a, b = await _scene_fixture(client, db_session, "ZONE-SC-FILTER")
    r = await client.get(f"/api/v1/zones/{zone.code}/products?scene_code=S01", headers=headers)
    assert [i["id"] for i in r.json()["data"]["items"]] == [a.id]
    assert r.json()["data"]["total"] == 1


@pytest.mark.asyncio
async def test_zone_products_scene_and_category_stack(client: AsyncClient, db_session):
    zone, headers, a, b = await _scene_fixture(client, db_session, "ZONE-SC-STACK")
    r = await client.get(
        f"/api/v1/zones/{zone.code}/products?scene_code=S02&zone_category_code=C01", headers=headers,
    )
    assert sorted(i["id"] for i in r.json()["data"]["items"]) == sorted([a.id, b.id])
    assert r.json()["data"]["total"] == 2


@pytest.mark.asyncio
async def test_zone_products_scene_code_wrong_kind_is_empty(client: AsyncClient, db_session):
    """scene_code 给了大类 code(kind 不对)或不存在的 code → 空列表,不是 500。"""
    zone, headers, a, b = await _scene_fixture(client, db_session, "ZONE-SC-WRONG")
    for bad in ("C01", "S99"):
        r = await client.get(f"/api/v1/zones/{zone.code}/products?scene_code={bad}", headers=headers)
        assert r.status_code == 200, r.text
        assert r.json()["data"] == {"items": [], "total": 0, "page": 1, "size": 20, "pages": 0}


@pytest.mark.asyncio
async def test_zone_products_category_code_wrong_kind_is_empty(client: AsyncClient, db_session):
    """zone_category_code 给了场景 code → 空列表(两轴参数各自只认自己的 kind)。"""
    zone, headers, a, b = await _scene_fixture(client, db_session, "ZONE-SC-WRONG2")
    r = await client.get(f"/api/v1/zones/{zone.code}/products?zone_category_code=S01", headers=headers)
    assert r.json()["data"]["total"] == 0


@pytest.mark.asyncio
async def test_zone_product_detail_returns_zone_categories(client: AsyncClient, db_session):
    zone, headers, a, b = await _scene_fixture(client, db_session, "ZONE-SC-DETAIL")
    r = await client.get(f"/api/v1/zones/{zone.code}/products/{a.id}", headers=headers)
    assert r.status_code == 200, r.text
    zcs = r.json()["data"]["zone_categories"]
    assert [(z["kind"], z["code"]) for z in zcs] == [("CATEGORY", "C01"), ("SCENE", "S01"), ("SCENE", "S02")]
    assert zcs[1]["name"] == "浮选厂"
