"""内部路由 /api/v1/internal/*:只供履约后台(S2S 令牌)调用,反代层再按来源 IP 白名单。

契约 §5.1:履约做客户 ↔ 前台组织绑定时,按名搜索候选、保存前按 id 再查一次。
只回 {id, name, code, status};不回成员、联系方式。
名称包含匹配走 pg_trgm GIN 索引(迁移 portal_0001);q ≥ 2 字符与履约侧一致。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, success
from app.core.s2s_auth import require_fulfillment_caller
from app.db.models.buyer_organization import BuyerOrganization
from app.db.session import get_db

router = APIRouter(
    prefix="/internal",
    tags=["internal"],
    dependencies=[Depends(require_fulfillment_caller)],
)

SEARCH_LIMIT_MAX = 20


class BuyerOrgBrief(BaseModel):
    id: int
    name: str
    code: str | None
    status: str


def _escape_like(raw: str) -> str:
    """把用户输入里的 LIKE 通配符转义成字面量(escape 字符用反斜杠)。"""
    return raw.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


@router.get("/buyer-organizations", summary="按名称搜索前台买方组织(履约绑定用)")
async def search_buyer_organizations(
    q: str = Query(..., min_length=2, max_length=100),
    limit: int = Query(10, ge=1, le=SEARCH_LIMIT_MAX),
    db: AsyncSession = Depends(get_db),
):
    needle = q.strip()
    if not needle:
        return success([])
    rows = await db.execute(
        select(BuyerOrganization)
        .where(BuyerOrganization.name.ilike(f"%{_escape_like(needle)}%", escape="\\"))
        .order_by(BuyerOrganization.name, BuyerOrganization.id)
        .limit(limit)
    )
    return success([
        BuyerOrgBrief(id=o.id, name=o.name, code=o.code, status=o.status).model_dump()
        for o in rows.scalars()
    ])


@router.get("/buyer-organizations/{org_id}", summary="按 id 取前台买方组织(履约保存绑定前复核)")
async def get_buyer_organization(
    org_id: int,
    db: AsyncSession = Depends(get_db),
):
    org = await db.get(BuyerOrganization, org_id)
    if org is None:
        raise NotFoundError("Buyer organization not found")
    return success(BuyerOrgBrief(id=org.id, name=org.name, code=org.code, status=org.status).model_dump())
