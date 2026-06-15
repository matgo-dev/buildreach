"""RFQ 公共加载器 — 收敛 id + 软删过滤 + 可选行锁 + 可选 items 加载。

rfq.py / quote.py 共用,避免规则漂移。
角色 scope 通过 resolve_rfq_scope() 统一判断,杜绝散落的 if "BUYER" in。
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.dependencies import CurrentUser
from app.core.exceptions import RfqNotFoundError
from app.db.models.buyer_member import BuyerMember
from app.db.models.buyer_organization import BuyerOrgStatus, BuyerOrganization
from app.db.models.rfq import Rfq


# ── 角色 scope 判定 ──────────────────────────────────────


@dataclass(frozen=True, slots=True)
class RfqScope:
    """角色作用域：is_operator 决定数据可见范围和序列化 DTO。"""
    is_buyer: bool
    is_operator: bool


def resolve_rfq_scope(user: CurrentUser) -> RfqScope:
    """统一角色 → scope 映射，所有 rfq/quote 路径复用。"""
    return RfqScope(
        is_buyer="BUYER" in user.roles,
        is_operator="OPERATOR" in user.roles,
    )


async def load_rfq(
    db: AsyncSession,
    rfq_id: int,
    *,
    for_update: bool = False,
    with_items: bool = True,
    buyer_org_id: int | None = None,
) -> Rfq | None:
    """Load a non-deleted RFQ.

    for_update=True: used by write paths that need to serialize RFQ state changes.
    with_items=True: used by detail/list serialization paths that need rfq.items.
    buyer_org_id: optional data-level filter; service decides when to pass it.
    """
    q = select(Rfq).where(
        Rfq.id == rfq_id,
        Rfq.deleted_at.is_(None),
    )

    if buyer_org_id is not None:
        q = q.where(Rfq.buyer_org_id == buyer_org_id)

    if with_items:
        q = q.options(selectinload(Rfq.items))

    if for_update:
        q = q.with_for_update()

    row = await db.execute(q)
    return row.scalar_one_or_none()


async def _resolve_buyer_org_id(db: AsyncSession, user: CurrentUser) -> int:
    """BUYER 用户 → buyer_org_id。无组织返回时抛 RfqNotFoundError(隐藏存在性)。"""
    row = await db.execute(
        select(BuyerOrganization.id)
        .join(BuyerMember, BuyerMember.buyer_org_id == BuyerOrganization.id)
        .where(
            BuyerMember.user_id == user.id,
            BuyerOrganization.status == BuyerOrgStatus.ACTIVE,
        )
        .limit(1)
    )
    org_id = row.scalar_one_or_none()
    if not org_id:
        raise RfqNotFoundError()
    return org_id


async def lock_rfq(
    db: AsyncSession, rfq_id: int, *, user: CurrentUser,
    with_items: bool = False,
) -> Rfq:
    """SELECT rfq FOR UPDATE + 角色 scope 过滤。返回锁定的 Rfq 或抛 RfqNotFoundError。

    所有 RFQ 状态变更路径统一入口,保证行锁串行化。
    """
    scope = resolve_rfq_scope(user)

    buyer_org_id = None
    if scope.is_buyer and not scope.is_operator:
        buyer_org_id = await _resolve_buyer_org_id(db, user)

    rfq = await load_rfq(
        db, rfq_id,
        for_update=True,
        with_items=with_items,
        buyer_org_id=buyer_org_id,
    )
    if not rfq:
        raise RfqNotFoundError()
    return rfq
