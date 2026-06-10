"""RFQ 公共加载器 — 收敛 id + 软删过滤 + 可选行锁 + 可选 items 加载。

rfq.py / quote.py 共用,避免规则漂移。
不做角色判断;buyer_org_id 只是可选 WHERE 过滤参数。
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models.rfq import Rfq


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
