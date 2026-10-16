"""专区访问口径(单一源头):ACTIVE 且(公开 或 当前用户所属买方机构持有授权)。

`GET /zones`(导航,可匿名)、`GET /me` 的 zones、专区路由门禁 `require_zone_access` 共用,
避免"导航能看到但进不去"之类的口径分叉。
"""
from __future__ import annotations

from sqlalchemy import exists, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from app.db.models.buyer_member import BuyerMember
from app.db.models.zone import Zone, ZoneGrant


def zone_accessible_clause(user_id: int | None) -> ColumnElement[bool]:
    """Zone 行的可访问条件。user_id=None(匿名)时只剩公开专区。"""
    if user_id is None:
        return (Zone.status == "ACTIVE") & Zone.is_public.is_(True)
    granted = exists().where(
        ZoneGrant.zone_id == Zone.id,
        BuyerMember.buyer_org_id == ZoneGrant.buyer_org_id,
        BuyerMember.user_id == user_id,
    )
    return (Zone.status == "ACTIVE") & or_(Zone.is_public.is_(True), granted)


async def list_accessible_zones(db: AsyncSession, user_id: int | None) -> list[dict]:
    rows = await db.execute(
        select(Zone.code, Zone.name_zh, Zone.name_en)
        .where(zone_accessible_clause(user_id))
        .order_by(Zone.sort_order, Zone.id)
    )
    return [{"code": r.code, "name_zh": r.name_zh, "name_en": r.name_en} for r in rows]
