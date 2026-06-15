"""运营端 — 买方组织查询（代录询价时选择买方）。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import CurrentUser
from app.core.exceptions import success
from app.db.models.buyer_organization import BuyerOrgStatus, BuyerOrganization
from app.db.session import get_db
from app.rbac.constants import Permissions
from app.rbac.guards import require_any_role, require_permission

from pydantic import BaseModel

router = APIRouter(
    prefix="/operator/buyer-orgs",
    tags=["operator-buyers"],
    dependencies=[Depends(require_any_role("OPERATOR"))],
)


class BuyerOrgBrief(BaseModel):
    id: int
    name: str
    code: str | None = None


@router.get("", summary="搜索买方组织")
async def list_buyer_orgs(
    q: str = Query(default="", max_length=100),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=50),
    current: CurrentUser = Depends(require_permission(Permissions.RFQ_CLAIM)),
    db: AsyncSession = Depends(get_db),
):
    """按组织名模糊搜索 ACTIVE 买方组织。运营代录询价时选择买方。"""
    base = select(BuyerOrganization).where(
        BuyerOrganization.status == BuyerOrgStatus.ACTIVE,
    )
    if q.strip():
        base = base.where(BuyerOrganization.name.ilike(f"%{q.strip()}%"))

    # 总数
    count_q = select(func.count()).select_from(base.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    # 分页
    rows = await db.execute(
        base.order_by(BuyerOrganization.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = [
        BuyerOrgBrief(id=org.id, name=org.name, code=org.code).model_dump()
        for org in rows.scalars().all()
    ]

    return success({
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
    })
