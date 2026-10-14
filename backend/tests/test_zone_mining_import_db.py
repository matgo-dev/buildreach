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
                visibility=ProductVisibility.ZONE_ONLY, moq=1, unit="PCS", source="IMPORT",
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
    old = await _product(db_session, "ORPHAN-OLD")
    keep = await _product(db_session, "ORPHAN-KEEP")
    await _product(db_session, "OTHER-BATCH", batch="something_else")
    orphans = await find_orphan_products(db_session, computed_spu_codes={"ORPHAN-KEEP", "ORPHAN-NEW"})
    assert [(o.spu_code, o.name_zh) for o in orphans] == [("ORPHAN-OLD", "ORPHAN-OLD")]


@pytest.mark.asyncio
async def test_soft_delete_orphans_removes_zone_rows_and_marks_deleted(db_session):
    from sqlalchemy import select
    from scripts.import_zone_mining import soft_delete_orphans
    zone, a, b = await _zone(db_session, "ZONE-MINING-ORPH")
    old = await _product(db_session, "ORPHAN-DEL")
    db_session.add(ZoneProduct(zone_id=zone.id, spu_id=old.id, zone_category_id=a.id, source="IMPORT", source_batch_id=BATCH_ID))
    await db_session.flush()
    n = await soft_delete_orphans(db_session, zone, [old])
    assert n == 1
    assert (await db_session.execute(select(ZoneProduct.id).where(ZoneProduct.spu_id == old.id))).scalars().all() == []
    await db_session.refresh(old)
    assert old.deleted_at is not None
