"""专区授权(zone_grants)运营管理 service。

只覆盖「买家组织 ↔ 专区」的授权关系(列出/新增/撤销);专区选品(zone_products)仍走导入脚本。
路由负责 commit,本模块只 flush + 返回 ORM/字典。
"""
from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.buyer_organization import BuyerOrganization
from app.db.models.zone import Zone, ZoneGrant


async def list_zones(db: AsyncSession) -> list[dict]:
    rows = (
        await db.execute(select(Zone).order_by(Zone.sort_order, Zone.id))
    ).scalars().all()
    return [
        {"id": z.id, "code": z.code, "name_zh": z.name_zh, "status": z.status}
        for z in rows
    ]


async def _get_zone(db: AsyncSession, zone_code: str) -> Zone | None:
    return (
        await db.execute(select(Zone).where(Zone.code == zone_code))
    ).scalar_one_or_none()


async def list_grants(db: AsyncSession, zone: Zone) -> list[dict]:
    """列出某专区已授权的买家组织(含组织名/编码/授权时间)。"""
    rows = (
        await db.execute(
            select(ZoneGrant, BuyerOrganization)
            .join(BuyerOrganization, BuyerOrganization.id == ZoneGrant.buyer_org_id)
            .where(ZoneGrant.zone_id == zone.id)
            .order_by(ZoneGrant.id.desc())
        )
    ).all()
    return [
        {
            "buyer_org_id": org.id,
            "name": org.name,
            "code": org.code,
            "granted_at": grant.created_at.isoformat() if grant.created_at else None,
        }
        for grant, org in rows
    ]


async def grant(
    db: AsyncSession, zone: Zone, buyer_org_id: int, granted_by: int
) -> tuple[dict | None, str]:
    """给买家组织授权某专区。幂等:已授权则原样返回。

    返回 (授权字典, 状态);状态 = created | exists | org_not_found。
    """
    org = (
        await db.execute(
            select(BuyerOrganization).where(BuyerOrganization.id == buyer_org_id)
        )
    ).scalar_one_or_none()
    if org is None:
        return None, "org_not_found"

    existing = (
        await db.execute(
            select(ZoneGrant).where(
                ZoneGrant.zone_id == zone.id,
                ZoneGrant.buyer_org_id == buyer_org_id,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        return _grant_dict(existing, org), "exists"

    row = ZoneGrant(zone_id=zone.id, buyer_org_id=buyer_org_id, granted_by=granted_by)
    db.add(row)
    await db.flush()
    return _grant_dict(row, org), "created"


async def revoke(db: AsyncSession, zone: Zone, buyer_org_id: int) -> bool:
    """撤销授权。返回是否有删除到(不存在返回 False)。"""
    result = await db.execute(
        delete(ZoneGrant).where(
            ZoneGrant.zone_id == zone.id,
            ZoneGrant.buyer_org_id == buyer_org_id,
        )
    )
    return (result.rowcount or 0) > 0


def _grant_dict(grant: ZoneGrant, org: BuyerOrganization) -> dict:
    return {
        "buyer_org_id": org.id,
        "name": org.name,
        "code": org.code,
        "granted_at": grant.created_at.isoformat() if grant.created_at else None,
    }
