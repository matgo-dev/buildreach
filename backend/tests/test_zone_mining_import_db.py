"""矿业导入脚本里两个需要 DB 的幂等守卫:规则改动后清陈旧挂载;合并表改名后检测孤儿商品。"""
from __future__ import annotations

import pytest

from app.db.models.product import Product, ProductStatus, ProductVisibility
from app.db.models.zone import ZONE_CATEGORY_KIND_CATEGORY, Zone, ZoneCategory, ZoneProduct
from scripts.import_zone_mining import BATCH_ID, find_orphan_products, prune_stale_zone_products


async def _zone(db_session, code="ZONE-MINING-T"):
    zone = Zone(code=code, name_zh="t", status="ACTIVE")
    db_session.add(zone)
    await db_session.flush()
    a = ZoneCategory(zone_id=zone.id, code="A", name_zh="A", kind=ZONE_CATEGORY_KIND_CATEGORY)
    b = ZoneCategory(zone_id=zone.id, code="B", name_zh="B", kind=ZONE_CATEGORY_KIND_CATEGORY)
    db_session.add_all([a, b])
    await db_session.flush()
    return zone, a, b


async def _product(db_session, spu_code, batch=BATCH_ID):
    p = Product(spu_code=spu_code, name_zh=spu_code, category_code="04.001", status=ProductStatus.ACTIVE,
                visibility=ProductVisibility.PUBLIC, moq=1, unit="PCS", source="IMPORT",
                source_meta={"batch": batch})
    db_session.add(p)
    await db_session.flush()
    return p


@pytest.mark.asyncio
async def test_prune_removes_batch_rows_not_in_expected_set_and_keeps_manual(db_session):
    zone, a, b = await _zone(db_session)
    p = await _product(db_session, "PRUNE-1")
    db_session.add(ZoneProduct(zone_id=zone.id, spu_id=p.id, zone_category_id=a.id, source="IMPORT", source_batch_id=BATCH_ID))
    db_session.add(ZoneProduct(zone_id=zone.id, spu_id=p.id, zone_category_id=b.id, source="MANUAL", source_batch_id=None))
    await db_session.flush()

    removed = await prune_stale_zone_products(db_session, zone, p, expected_category_ids={b.id})
    assert removed == 1
    from sqlalchemy import select
    left = (await db_session.execute(select(ZoneProduct.zone_category_id).where(ZoneProduct.spu_id == p.id))).scalars().all()
    assert left == [b.id]  # 本批次的 A 被清,手工挂的 B 保留


@pytest.mark.asyncio
async def test_find_orphan_products_reports_batch_products_missing_from_computed_set(db_session):
    zone, a, _b = await _zone(db_session, "ZONE-MINING-FIND")
    old = await _product(db_session, "ORPHAN-OLD")
    keep = await _product(db_session, "ORPHAN-KEEP")
    other = await _product(db_session, "OTHER-BATCH", batch="something_else")
    for p in (old, keep, other):
        db_session.add(ZoneProduct(zone_id=zone.id, spu_id=p.id, zone_category_id=a.id, source="IMPORT", source_batch_id=BATCH_ID))
    await db_session.flush()
    orphans = await find_orphan_products(db_session, zone, computed_spu_codes={"ORPHAN-KEEP", "ORPHAN-NEW"})
    assert [(o.id, o.spu_code, o.name_zh) for o in orphans] == [(old.id, "ORPHAN-OLD", "ORPHAN-OLD")]


@pytest.mark.asyncio
async def test_soft_delete_orphans_removes_zone_rows_and_soft_deletes_product_and_skus(db_session):
    """孤儿软删必须连 SKU 一起:sku_code 由 spu_code+规格确定,活 SKU 留着会让改回品名后的重导撞唯一索引。"""
    from sqlalchemy import select
    from app.db.models.product_sku import ProductSku, SkuStatus
    from scripts.import_zone_mining import find_orphan_products, mining_sku_code, soft_delete_orphans

    zone, a, b = await _zone(db_session, "ZONE-MINING-ORPH")
    old = await _product(db_session, "ORPHAN-DEL")
    sku_code = mining_sku_code("ORPHAN-DEL", None)
    db_session.add(ProductSku(product_id=old.id, sku_code=sku_code, name_zh="x", moq=1, is_default=True, status=SkuStatus.ACTIVE))
    db_session.add(ZoneProduct(zone_id=zone.id, spu_id=old.id, zone_category_id=a.id, source="IMPORT", source_batch_id=BATCH_ID))
    await db_session.flush()

    orphans = await find_orphan_products(db_session, zone, computed_spu_codes=set())
    n = await soft_delete_orphans(db_session, zone, orphans)
    assert n == 1
    assert (await db_session.execute(select(ZoneProduct.id).where(ZoneProduct.spu_id == old.id))).scalars().all() == []
    await db_session.refresh(old)
    assert old.deleted_at is not None
    sku = (await db_session.execute(select(ProductSku).where(ProductSku.product_id == old.id))).scalar_one()
    assert sku.deleted_at is not None

    # 改回品名后重导:同 spu_code/sku_code 再建一条活的,不撞 uq_product_skus_sku_code_active / uq_products_spu_code_active
    again = await _product(db_session, "ORPHAN-DEL")
    db_session.add(ProductSku(product_id=again.id, sku_code=sku_code, name_zh="x", moq=1, is_default=True, status=SkuStatus.ACTIVE))
    await db_session.flush()


@pytest.mark.asyncio
async def test_find_orphans_ignores_unmounted_and_non_import_products(db_session):
    """候选先按本专区挂载收口:没挂在本专区的、或非 IMPORT 的商品,即便 batch 相同也不算本脚本的孤儿。"""
    zone, a, _b = await _zone(db_session, "ZONE-MINING-IGN")
    await _product(db_session, "ORPHAN-UNMOUNTED")
    q = await _product(db_session, "ORPHAN-MANUAL")
    q.source = "MANUAL"
    db_session.add(ZoneProduct(zone_id=zone.id, spu_id=q.id, zone_category_id=a.id, source="MANUAL", source_batch_id=None))
    await db_session.flush()
    assert await find_orphan_products(db_session, zone, computed_spu_codes=set()) == []
