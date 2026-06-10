"""询价单路由 — 买方需求侧。

审计:由 service 在唯一 commit 前 write_audit(commit=False) 同事务;route 不自行 commit。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import CurrentUser
from app.core.exceptions import success
from app.db.session import get_db
from app.rbac.constants import Permissions
from app.rbac.guards import require_any_role, require_permission
from app.schemas.rfq import RfqCancelRequest, RfqCreate, RfqItemUpdate
from app.services import rfq as rfq_svc

router = APIRouter(
    prefix="/rfqs",
    tags=["rfq"],
    dependencies=[Depends(require_any_role("BUYER", "OPERATOR"))],
)


@router.post("", summary="创建询价单")
async def create_rfq(
    request: Request,
    data: RfqCreate,
    current: CurrentUser = Depends(require_permission(Permissions.RFQ_CREATE)),
    db: AsyncSession = Depends(get_db),
):
    result = await rfq_svc.create_rfq(db, current, data, request=request)
    return success(result.model_dump())


@router.get("", summary="询价单列表")
async def list_rfqs(
    current: CurrentUser = Depends(require_permission(Permissions.RFQ_READ)),
    db: AsyncSession = Depends(get_db),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status: str | None = Query(default=None),
    buyer_org_id: int | None = Query(default=None),
    mine: bool = Query(default=False),
):
    result = await rfq_svc.list_rfqs(
        db, current,
        page=page, page_size=page_size,
        status_filter=status,
        buyer_org_id_filter=buyer_org_id,
        mine=mine,
    )
    return success(result)


@router.get("/{rfq_id}", summary="询价单详情")
async def get_rfq(
    rfq_id: int,
    current: CurrentUser = Depends(require_permission(Permissions.RFQ_READ)),
    db: AsyncSession = Depends(get_db),
):
    result = await rfq_svc.get_rfq(db, current, rfq_id)
    return success(result.model_dump())


@router.patch("/{rfq_id}/cancel", summary="撤销询价单")
async def cancel_rfq(
    rfq_id: int,
    request: Request,
    data: RfqCancelRequest | None = None,
    current: CurrentUser = Depends(require_permission(Permissions.RFQ_CANCEL)),
    db: AsyncSession = Depends(get_db),
):
    cancel_reason = data.cancel_reason if data else None
    result = await rfq_svc.cancel_rfq(
        db, current, rfq_id, cancel_reason, request=request,
    )
    return success(result.model_dump())


@router.patch("/{rfq_id}/claim", summary="受理询价单")
async def claim_rfq(
    rfq_id: int,
    request: Request,
    current: CurrentUser = Depends(require_permission(Permissions.RFQ_CLAIM)),
    db: AsyncSession = Depends(get_db),
):
    result = await rfq_svc.claim_rfq(db, current, rfq_id, request=request)
    return success(result.model_dump())


@router.patch("/{rfq_id}/withdraw", summary="撤回改单")
async def withdraw_rfq(
    rfq_id: int,
    request: Request,
    current: CurrentUser = Depends(require_permission(Permissions.RFQ_UPDATE)),
    db: AsyncSession = Depends(get_db),
):
    result = await rfq_svc.withdraw_rfq(db, current, rfq_id, request=request)
    return success(result.model_dump())


@router.patch("/{rfq_id}/items/{item_id}", summary="草稿态编辑行项数量")
async def update_rfq_item(
    rfq_id: int,
    item_id: int,
    data: RfqItemUpdate,
    request: Request,
    current: CurrentUser = Depends(require_permission(Permissions.RFQ_UPDATE)),
    db: AsyncSession = Depends(get_db),
):
    result = await rfq_svc.update_rfq_item_qty(
        db, current, rfq_id, item_id, data.quantity, request=request,
    )
    return success(result.model_dump())
