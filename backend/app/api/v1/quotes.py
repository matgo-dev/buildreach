"""报价路由 — 回填/重报/失效/接受/拒绝/读取 + 产物管理。

挂在 /rfqs/{rfq_id}/ 下,共用 rfqs 前缀。
审计:由 service 在唯一 commit 前 write_audit(commit=False) 同事务;route 不自行 commit。
"""
from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import CurrentUser
from app.core.exceptions import success
from app.db.session import get_db
from app.rbac.constants import Permissions
from app.rbac.guards import require_any_role, require_permission
from app.schemas.quote import QuoteCreatePayload
from app.services import quote as quote_svc
from app.services.quote_export import (
    generate_quote_documents,
    get_quote_documents_status,
    retry_failed_documents,
)

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
    background_tasks: BackgroundTasks,
    current: CurrentUser = Depends(require_permission(Permissions.QUOTE_WRITE)),
    db: AsyncSession = Depends(get_db),
):
    result = await quote_svc.create_quote(db, current, rfq_id, data, request=request)

    # 提交/重报成功后异步预生成所有语言的 PDF 产物
    background_tasks.add_task(
        generate_quote_documents,
        quote_id=result.id,
        version=result.version,
        rfq_id=rfq_id,
    )

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


# ── 报价单文档产物管理 ─────────────────────────────────────────


@router.get("/{rfq_id}/quote-documents", summary="报价单文档状态")
async def list_quote_documents(
    rfq_id: int,
    current: CurrentUser = Depends(require_permission(Permissions.QUOTE_READ)),
    db: AsyncSession = Depends(get_db),
):
    """列出 ACTIVE 报价所有 locale 的产物状态。"""
    active_quote = await quote_svc.get_active_quote(db, rfq_id)
    if active_quote is None:
        return success([])

    docs = await get_quote_documents_status(db, active_quote.id, active_quote.version)
    return success([
        {
            "id": d.id,
            "locale": d.locale,
            "status": d.status,
            "file_size": d.file_size,
            "error_message": d.error_message,
            "retry_count": d.retry_count,
            "generated_at": d.generated_at.isoformat() if d.generated_at else None,
        }
        for d in docs
    ])


@router.post("/{rfq_id}/quote-documents/retry", summary="重试失败的文档生成")
async def retry_quote_documents(
    rfq_id: int,
    background_tasks: BackgroundTasks,
    current: CurrentUser = Depends(require_permission(Permissions.QUOTE_WRITE)),
    db: AsyncSession = Depends(get_db),
):
    """重试所有 FAILED 的产物生成。"""
    active_quote = await quote_svc.get_active_quote(db, rfq_id)
    if active_quote is None:
        return success({"retried": 0})

    count = await retry_failed_documents(
        db, active_quote.id, active_quote.version, rfq_id,
    )

    if count > 0:
        background_tasks.add_task(
            generate_quote_documents,
            quote_id=active_quote.id,
            version=active_quote.version,
            rfq_id=rfq_id,
        )

    return success({"retried": count})
