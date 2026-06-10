"""报价路由 — 回填/重报/失效/接受/拒绝/读取。

挂在 /rfqs/{rfq_id}/ 下,共用 rfqs 前缀。
审计:由 service 在唯一 commit 前 write_audit(commit=False) 同事务;route 不自行 commit。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import CurrentUser
from app.core.exceptions import success
from app.db.session import get_db
from app.rbac.constants import Permissions
from app.rbac.guards import require_any_role, require_permission
from app.schemas.quote import QuoteCreatePayload
from app.services import quote as quote_svc

router = APIRouter(
    prefix="/rfqs",
    tags=["quote"],
    dependencies=[Depends(require_any_role("BUYER", "OPERATOR"))],
)


@router.post("/{rfq_id}/quotes", summary="回填/重报报价")
async def create_quote(
    rfq_id: int,
    request: Request,
    data: QuoteCreatePayload,
    current: CurrentUser = Depends(require_permission(Permissions.QUOTE_WRITE)),
    db: AsyncSession = Depends(get_db),
):
    result = await quote_svc.create_quote(db, current, rfq_id, data, request=request)
    return success(result.model_dump())


@router.patch("/{rfq_id}/expire", summary="失效报价")
async def expire_rfq(
    rfq_id: int,
    request: Request,
    current: CurrentUser = Depends(require_permission(Permissions.QUOTE_WRITE)),
    db: AsyncSession = Depends(get_db),
):
    result = await quote_svc.expire_rfq(db, current, rfq_id, request=request)
    return success(result)


@router.patch("/{rfq_id}/accept", summary="接受报价")
async def accept_rfq(
    rfq_id: int,
    request: Request,
    current: CurrentUser = Depends(require_permission(Permissions.RFQ_DECIDE)),
    db: AsyncSession = Depends(get_db),
):
    result = await quote_svc.accept_rfq(db, current, rfq_id, request=request)
    return success(result)


@router.patch("/{rfq_id}/reject", summary="拒绝报价")
async def reject_rfq(
    rfq_id: int,
    request: Request,
    current: CurrentUser = Depends(require_permission(Permissions.RFQ_DECIDE)),
    db: AsyncSession = Depends(get_db),
):
    result = await quote_svc.reject_rfq(db, current, rfq_id, request=request)
    return success(result)


@router.get("/{rfq_id}/quotes", summary="报价列表")
async def get_quotes(
    rfq_id: int,
    current: CurrentUser = Depends(require_permission(Permissions.QUOTE_READ)),
    db: AsyncSession = Depends(get_db),
):
    result = await quote_svc.get_quotes(db, current, rfq_id)
    return success([r.model_dump() for r in result])
