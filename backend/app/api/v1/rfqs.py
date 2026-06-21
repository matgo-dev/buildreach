"""询价单路由 — 买方需求侧。

审计:由 service 在唯一 commit 前 write_audit(commit=False) 同事务;route 不自行 commit。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Header, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import CurrentUser
from app.core.exceptions import success
from app.db.session import get_db
from app.rbac.constants import Permissions
from app.rbac.guards import require_any_role, require_permission
from app.schemas.rfq import (
    RfqCancelRequest, RfqCreate, RfqItemEdit, RfqItemInput, RfqItemUpdate, RfqUpdate,
)
from app.services import rfq as rfq_svc
from app.services.quote_export import build_content_disposition, generate_quote_pdf

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
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    result = await rfq_svc.create_rfq(
        db, current, data, idempotency_key=idempotency_key, request=request,
    )
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


@router.patch("/{rfq_id}", summary="草稿态整单更新")
async def update_rfq(
    rfq_id: int,
    data: RfqUpdate,
    request: Request,
    current: CurrentUser = Depends(require_permission(Permissions.RFQ_UPDATE)),
    db: AsyncSession = Depends(get_db),
):
    result = await rfq_svc.update_rfq(
        db, current, rfq_id, data, request=request,
    )
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


@router.patch("/{rfq_id}/submit", summary="提交草稿询价单")
async def submit_rfq(
    rfq_id: int,
    request: Request,
    current: CurrentUser = Depends(require_permission(Permissions.RFQ_UPDATE)),
    db: AsyncSession = Depends(get_db),
):
    result = await rfq_svc.submit_rfq(db, current, rfq_id, request=request)
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


@router.patch("/{rfq_id}/items/{item_id}", summary="编辑行项数量")
async def update_rfq_item(
    rfq_id: int,
    item_id: int,
    data: RfqItemUpdate,
    request: Request,
    current: CurrentUser = Depends(require_any_role("BUYER", "OPERATOR")),
    db: AsyncSession = Depends(get_db),
):
    """DRAFT 态买方可改，PROCESSING 态受理人可改。权限在 service 层按状态校验。"""
    result = await rfq_svc.update_rfq_item_qty(
        db, current, rfq_id, item_id, data.quantity, request=request,
    )
    return success(result.model_dump())


# ── 运营行项增删改（PROCESSING 态） ──────────────────────


@router.post("/{rfq_id}/items", summary="添加询价行项（运营）")
async def add_rfq_item(
    rfq_id: int,
    data: RfqItemInput,
    request: Request,
    current: CurrentUser = Depends(require_permission(Permissions.RFQ_CLAIM)),
    db: AsyncSession = Depends(get_db),
):
    result = await rfq_svc.add_rfq_item(
        db, current, rfq_id, data, request=request,
    )
    return success(result.model_dump())


@router.put("/{rfq_id}/items/{item_id}", summary="编辑询价行项（运营）")
async def edit_rfq_item(
    rfq_id: int,
    item_id: int,
    data: RfqItemEdit,
    request: Request,
    current: CurrentUser = Depends(require_permission(Permissions.RFQ_CLAIM)),
    db: AsyncSession = Depends(get_db),
):
    result = await rfq_svc.edit_rfq_item(
        db, current, rfq_id, item_id, data, request=request,
    )
    return success(result.model_dump())


@router.delete("/{rfq_id}/items/{item_id}", summary="删除询价行项（运营）")
async def delete_rfq_item(
    rfq_id: int,
    item_id: int,
    request: Request,
    current: CurrentUser = Depends(require_permission(Permissions.RFQ_CLAIM)),
    db: AsyncSession = Depends(get_db),
):
    result = await rfq_svc.delete_rfq_item(
        db, current, rfq_id, item_id, request=request,
    )
    return success(result.model_dump())


# ── 报价导出 ──────────────────────────────────────────────


@router.get("/{rfq_id}/quote/export", summary="导出报价单 PDF")
async def export_quote_pdf(
    rfq_id: int,
    request: Request,
    current: CurrentUser = Depends(require_permission(Permissions.RFQ_READ)),
    db: AsyncSession = Depends(get_db),
):
    """买方/运营下载买方版报价单 PDF。

    优先查产物表返回预生成文件；GENERATING 返回 202 JSON；
    FAILED 返回 422 JSON；无记录兜底现场生成（过渡期）。
    """
    from fastapi.responses import JSONResponse, Response
    from pathlib import Path

    from app.db.models.quote_document import QuoteDocument
    from app.services.quote import get_active_quote
    from app.services.quote_export import _get_document, _UPLOADS_DIR

    locale = getattr(request.state, "locale", "en")

    # 查 ACTIVE 报价的预生成产物
    active_quote = await get_active_quote(db, rfq_id)
    if active_quote is not None:
        doc = await _get_document(db, active_quote.id, active_quote.version, locale)

        if doc is not None and doc.status == "READY" and doc.storage_key:
            file_path = _UPLOADS_DIR / doc.storage_key
            if file_path.is_file():
                pdf_bytes = file_path.read_bytes()
                rfq = await _load_rfq_for_filename(db, rfq_id)
                filename = _make_filename(rfq, locale)
                return Response(
                    content=pdf_bytes,
                    media_type="application/pdf",
                    headers={
                        "Content-Disposition": build_content_disposition(filename),
                    },
                )

        if doc is not None and doc.status in ("PENDING", "GENERATING"):
            return JSONResponse(
                status_code=202,
                content={"code": 20201, "message": "quote_document_generating"},
            )

        if doc is not None and doc.status == "FAILED":
            return JSONResponse(
                status_code=422,
                content={"code": 42210, "message": "quote_document_failed"},
            )

    # 兜底：产物记录不存在（历史数据 / 迁移过渡期）→ 现场生成
    pdf_bytes, filename = await generate_quote_pdf(db, rfq_id, current, locale)

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": build_content_disposition(filename),
        },
    )


async def _load_rfq_for_filename(db: AsyncSession, rfq_id: int):
    """轻量加载 RFQ 用于构建文件名。"""
    from app.services._rfq_loader import load_rfq
    return await load_rfq(db, rfq_id)


def _make_filename(rfq, locale: str) -> str:
    """根据 RFQ 信息构建下载文件名。"""
    from datetime import datetime
    rfq_no = getattr(rfq, "rfq_no", "quotation") if rfq else "quotation"
    now = datetime.utcnow()
    return f"{rfq_no}_{now.strftime('%Y-%m-%d')}.pdf"
