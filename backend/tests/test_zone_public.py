"""公开专区(zones.is_public):所有人(含未登录)可进,非公开专区仍只认授权。

覆盖门禁三端点、GET /zones 导航列表、/me 的 zones、交易解析器,以及公开面不下发 SKU 价格。
"""
from __future__ import annotations

from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import update

from app.db.models.buyer_organization import BuyerOrganization
from app.db.models.product_sku import ProductSku
from app.db.models.zone import Zone
from app.services.purchase_target import ZoneAccessDeniedError, resolve_purchase_target
from tests.test_zone_isolation import (
    _login_default_buyer,
    _make_variant_product_in_zone,
    _make_zone_only_product_row,
    _make_zone_with_category,
    _make_zone_with_product,
)


async def _public_zone_with_product(db_session, code: str):
    zone, zcat = await _make_zone_with_category(db_session, zone_code=code)
    await db_session.execute(update(Zone).where(Zone.id == zone.id).values(is_public=True))
    product, sku = await _make_variant_product_in_zone(db_session, zone, zcat, spu_code=f"{code}-P")
    await db_session.flush()
    return zone, product, sku


@pytest.mark.asyncio
async def test_public_zone_open_to_anonymous(client: AsyncClient, db_session):
    zone, product, _ = await _public_zone_with_product(db_session, "ZONE-PUB-ANON")
    r1 = await client.get(f"/api/v1/zones/{zone.code}/categories")
    r2 = await client.get(f"/api/v1/zones/{zone.code}/products")
    r3 = await client.get(f"/api/v1/zones/{zone.code}/products/{product.id}")
    assert (r1.status_code, r2.status_code, r3.status_code) == (200, 200, 200), (r1.text, r2.text, r3.text)
    assert r2.json()["data"]["total"] == 1


@pytest.mark.asyncio
async def test_public_zone_open_to_logged_in_buyer_without_grant(client: AsyncClient, db_session):
    zone, _, _ = await _public_zone_with_product(db_session, "ZONE-PUB-BUYER")
    headers = await _login_default_buyer(client)
    r = await client.get(f"/api/v1/zones/{zone.code}/products", headers=headers)
    assert r.status_code == 200, r.text


@pytest.mark.asyncio
async def test_private_zone_anonymous_401_and_unknown_zone_401(client: AsyncClient, db_session):
    zone, _zcat = await _make_zone_with_category(db_session, zone_code="ZONE-PRIV-ANON")
    r = await client.get(f"/api/v1/zones/{zone.code}/products")
    assert r.status_code == 401, r.text
    # 不存在的专区与非公开专区对匿名表现一致,不泄露存在性
    r = await client.get("/api/v1/zones/NOPE-ZONE/products")
    assert r.status_code == 401, r.text


@pytest.mark.asyncio
async def test_inactive_public_zone_not_accessible(client: AsyncClient, db_session):
    zone, _, _ = await _public_zone_with_product(db_session, "ZONE-PUB-OFF")
    await db_session.execute(update(Zone).where(Zone.id == zone.id).values(status="INACTIVE"))
    await db_session.flush()
    r = await client.get(f"/api/v1/zones/{zone.code}/products")
    assert r.status_code == 401, r.text
    r = await client.get("/api/v1/zones")
    assert zone.code not in {z["code"] for z in r.json()["data"]}


@pytest.mark.asyncio
async def test_zone_list_anonymous_only_public(client: AsyncClient, db_session):
    pub, _, _ = await _public_zone_with_product(db_session, "ZONE-LIST-PUB")
    priv, _ = await _make_zone_with_category(db_session, zone_code="ZONE-LIST-PRIV")
    r = await client.get("/api/v1/zones")
    assert r.status_code == 200, r.text
    codes = {z["code"] for z in r.json()["data"]}
    assert pub.code in codes and priv.code not in codes


@pytest.mark.asyncio
async def test_me_and_zone_list_include_public_zones(client: AsyncClient, db_session):
    pub, _, _ = await _public_zone_with_product(db_session, "ZONE-ME-PUB")
    headers = await _login_default_buyer(client)
    me = await client.get("/api/v1/auth/me", headers=headers)
    listed = await client.get("/api/v1/zones", headers=headers)
    me_codes = {z["code"] for z in me.json()["data"]["zones"]}
    list_codes = {z["code"] for z in listed.json()["data"]}
    assert pub.code in me_codes
    assert me_codes == list_codes  # 同一口径


@pytest.mark.asyncio
async def test_public_zone_detail_does_not_expose_sku_price(client: AsyncClient, db_session):
    zone, product, sku = await _public_zone_with_product(db_session, "ZONE-PUB-PRICE")
    await db_session.execute(
        update(ProductSku).where(ProductSku.id == sku.id).values(price_min=Decimal("10"), price_max=Decimal("20"))
    )
    await db_session.flush()
    r = await client.get(f"/api/v1/zones/{zone.code}/products/{product.id}")
    assert r.status_code == 200, r.text
    s = r.json()["data"]["skus"][0]
    assert s["price_min"] is None and s["price_max"] is None


@pytest.mark.asyncio
async def test_resolve_purchase_target_zone_only_allowed_in_public_zone_without_grant(db_session):
    product = await _make_zone_only_product_row(db_session, spu_code="RPT-PUB-OK")
    zone = await _make_zone_with_product(db_session, zone_code="ZONE-RPT-PUB", zone_status="ACTIVE", product_id=product.id)
    await db_session.execute(update(Zone).where(Zone.id == zone.id).values(is_public=True))
    org = BuyerOrganization(name="公开专区买方组织")
    db_session.add(org)
    await db_session.flush()
    target = await resolve_purchase_target(db_session, product_id=product.id, buyer_org_id=org.id)
    assert target.product.id == product.id


@pytest.mark.asyncio
async def test_resolve_purchase_target_zone_only_public_zone_inactive_denied(db_session):
    product = await _make_zone_only_product_row(db_session, spu_code="RPT-PUB-OFF")
    zone = await _make_zone_with_product(db_session, zone_code="ZONE-RPT-PUB-OFF", zone_status="INACTIVE", product_id=product.id)
    await db_session.execute(update(Zone).where(Zone.id == zone.id).values(is_public=True))
    org = BuyerOrganization(name="停用公开专区买方组织")
    db_session.add(org)
    await db_session.flush()
    with pytest.raises(ZoneAccessDeniedError):
        await resolve_purchase_target(db_session, product_id=product.id, buyer_org_id=org.id)
