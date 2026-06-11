"""报价 Service — 运营回填/重报/失效 + 买方接受/拒绝 + 报价读取。

所有写操作 SELECT rfq FOR UPDATE 串行化,杜绝竞态。
提交点唯一在本 service;route 不自行 commit。
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from decimal import Decimal

from app.core.datetime import to_naive_utc

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from fastapi import Request

from app.audit.constants import AuditAction, AuditResourceType
from app.audit.logger import write_audit
from app.core.dependencies import CurrentUser
from app.core.exceptions import (
    QuoteItemMismatchError,
    QuoteLineNoPriceError,
    QuoteLinesIncompleteError,
    QuoteRfqStateInvalidError,
    RfqNotFoundError,
    RfqStateInvalidError,
)
from app.db.models.rfq import Rfq, RfqStatus, QuoteStatus
from app.db.models.rfq_item import RfqItem
from app.db.models.rfq_quote import RfqQuote
from app.db.models.rfq_quote_item import RfqQuoteItem
from app.db.models.rfq_quote_item_cost import RfqQuoteItemCost
from app.db.models.rfq_quote_item_tier import RfqQuoteItemTier
from app.services._rfq_loader import load_rfq, lock_rfq, _resolve_buyer_org_id
from app.schemas.quote import (
    QuoteCreatePayload,
    QuoteCostView,
    QuoteItemBuyerPublic,
    QuoteItemOperatorView,
    QuoteTierPublic,
    RfqQuoteBuyerPublic,
    RfqQuoteOperatorView,
)

logger = logging.getLogger(__name__)

# quote_no 并发重试上限
_QUOTE_NO_MAX_RETRIES = 5


# ── 组织解析 ───────────────────────────────────────────


# ── quote_no 生成 ────────────────────────────────────────


async def _generate_quote_no(db: AsyncSession) -> str:
    """格式 Q-YYYYMMDD-####,对齐 _generate_spu_code 日序号。"""
    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    prefix = f"Q-{today}-"
    count_result = await db.execute(
        select(func.count()).select_from(RfqQuote).where(
            RfqQuote.quote_no.like(f"{prefix}%"),
        )
    )
    seq = (count_result.scalar() or 0) + 1
    return f"{prefix}{seq:04d}"


# ── 创建/重报 ───────────────────────────────────────────


async def create_quote(
    db: AsyncSession, user: CurrentUser, rfq_id: int,
    payload: QuoteCreatePayload,
    *, request: Request | None = None,
) -> RfqQuoteOperatorView:
    """回填(首报)或重报。运营专用。"""
    rfq = await lock_rfq(db, rfq_id, user=user)

    # 状态守卫:首报 PROCESSING（运营需先受理）,重报 QUOTED
    is_first = rfq.status == RfqStatus.PROCESSING
    is_requote = rfq.status == RfqStatus.QUOTED
    if not is_first and not is_requote:
        raise QuoteRfqStateInvalidError(rfq.status)

    # 一次性加载 rfq_items
    items_result = await db.execute(
        select(RfqItem).where(
            RfqItem.rfq_id == rfq.id,
            RfqItem.deleted_at.is_(None),
        )
    )
    rfq_items = items_result.scalars().all()
    rfq_item_map = {it.id: it for it in rfq_items}

    # 校验 lines
    seen_ids: set[int] = set()
    for line in payload.lines:
        if line.rfq_item_id not in rfq_item_map:
            raise QuoteItemMismatchError()
        if line.rfq_item_id in seen_ids:
            raise QuoteItemMismatchError()
        seen_ids.add(line.rfq_item_id)
        # 非跳过行必须有 unit_price
        if not line.skipped and line.unit_price is None:
            raise QuoteLineNoPriceError()

    # 必须覆盖全部未删 rfq_items（包括 skipped 行）
    if seen_ids != set(rfq_item_map.keys()):
        raise QuoteLinesIncompleteError()

    # 不能全部跳过
    if all(line.skipped for line in payload.lines):
        raise QuoteLinesIncompleteError()

    # 计算金额——只汇总非 skipped 行
    total_amount = Decimal(0)
    line_amounts: dict[int, Decimal | None] = {}
    for line in payload.lines:
        if line.skipped:
            line_amounts[line.rfq_item_id] = None
            continue
        rfq_item = rfq_item_map[line.rfq_item_id]
        amt = line.unit_price * rfq_item.quantity  # type: ignore[operator]
        line_amounts[line.rfq_item_id] = amt
        total_amount += amt

    # 版本号
    if is_first:
        next_version = 1
    else:
        max_ver_result = await db.execute(
            select(func.max(RfqQuote.version)).where(
                RfqQuote.rfq_id == rfq.id,
                RfqQuote.deleted_at.is_(None),
            )
        )
        next_version = (max_ver_result.scalar() or 0) + 1

    # 旧 ACTIVE → SUPERSEDED
    if is_requote:
        await db.execute(
            update(RfqQuote)
            .where(
                RfqQuote.rfq_id == rfq.id,
                RfqQuote.quote_status == QuoteStatus.ACTIVE,
            )
            .values(quote_status=QuoteStatus.SUPERSEDED)
        )
        await db.flush()

    # 币种:header 缺省继承 RFQ 目标币种
    currency = payload.header.currency or rfq.target_currency or "USD"

    valid_until = to_naive_utc(payload.header.valid_until)

    # quote_no 生成 + SAVEPOINT 插入
    quote_no = await _generate_quote_no(db)
    quote: RfqQuote | None = None

    for attempt in range(_QUOTE_NO_MAX_RETRIES):
        nested = await db.begin_nested()
        try:
            quote = RfqQuote(
                rfq_id=rfq.id,
                quote_no=quote_no,
                version=next_version,
                quote_status=QuoteStatus.ACTIVE,
                trade_term=payload.header.trade_term,
                named_place=payload.header.named_place,
                currency=currency,
                valid_until=valid_until,
                lead_time_days=payload.header.lead_time_days,
                eta_days=payload.header.eta_days,
                total_amount=total_amount,
                quoted_by_user_id=user.id,
                quoted_at=datetime.now(timezone.utc).replace(tzinfo=None),
            )
            db.add(quote)
            await db.flush()
        except IntegrityError:
            await nested.rollback()
            # 回查确认是 quote_no 冲突
            existing = await db.execute(
                select(RfqQuote.id).where(RfqQuote.quote_no == quote_no)
            )
            if existing.scalar_one_or_none() is None:
                raise  # 非 quote_no 冲突,不误吞
            quote_no = await _generate_quote_no(db)
            quote = None
            continue
        except BaseException:
            await nested.rollback()
            raise
        else:
            await nested.commit()
            break

    if quote is None:
        raise QuoteRfqStateInvalidError()  # 极端:重试耗尽

    # 插入报价行 + tiers + costs
    for line in payload.lines:
        qi = RfqQuoteItem(
            quote_id=quote.id,
            rfq_item_id=line.rfq_item_id,
            skipped=line.skipped,
            skip_reason=line.skip_reason if line.skipped else None,
            unit_price=None if line.skipped else line.unit_price,
            moq=None if line.skipped else line.moq,
            cbm_per_unit=None if line.skipped else line.cbm_per_unit,
            gross_weight_per_unit=None if line.skipped else line.gross_weight_per_unit,
            line_amount=line_amounts[line.rfq_item_id],
        )
        db.add(qi)
        await db.flush()  # 获取 qi.id

        # tiers
        if line.tiers:
            for tier in line.tiers:
                db.add(RfqQuoteItemTier(
                    quote_item_id=qi.id,
                    min_qty=tier.min_qty,
                    unit_price=tier.unit_price,
                ))

        # cost(运营内部)
        if line.cost:
            db.add(RfqQuoteItemCost(
                quote_item_id=qi.id,
                supplier_org_id=line.cost.supplier_org_id,
                supplier_unit_price=line.cost.supplier_unit_price,
                freight_cost_alloc=line.cost.freight_cost_alloc,
                insurance_cost=line.cost.insurance_cost,
                export_clearance_cost=line.cost.export_clearance_cost,
                consolidation_cost=line.cost.consolidation_cost,
                gross_margin=line.cost.gross_margin,
            ))

    # 首报:SUBMITTED → QUOTED
    if is_first:
        if not RfqStatus.can_transition(rfq.status, RfqStatus.QUOTED):
            raise RfqStateInvalidError(rfq.status)
        rfq.status = RfqStatus.QUOTED

    # 审计
    audit_action = AuditAction.BACKFILL if is_first else AuditAction.REQUOTE
    await write_audit(
        db,
        resource_type=AuditResourceType.QUOTE,
        action=audit_action,
        user_id=user.id,
        user_email=user.email,
        resource_id=quote.id,
        request=request,
        extra={
            "quote_no": quote.quote_no,
            "version": next_version,
            "rfq_id": rfq.id,
            "rfq_no": rfq.rfq_no,
            "total_amount": str(total_amount),
        },
        commit=False,
    )
    await db.commit()

    return await _load_and_serialize_quote(db, quote.id)


# ── 接受 ────────────────────────────────────────────────


async def accept_rfq(
    db: AsyncSession, user: CurrentUser, rfq_id: int,
    *, request: Request | None = None,
) -> dict:
    """QUOTED→ACCEPTED,钉 accepted_quote_id。"""
    rfq = await lock_rfq(db, rfq_id, user=user)

    # 幂等:已 ACCEPTED 且 accepted_quote_id 有值
    if rfq.status == RfqStatus.ACCEPTED and rfq.accepted_quote_id is not None:
        return {"rfq_id": rfq.id, "status": rfq.status, "accepted_quote_id": rfq.accepted_quote_id}

    # 守卫
    if not RfqStatus.can_transition(rfq.status, RfqStatus.ACCEPTED):
        raise RfqStateInvalidError(rfq.status)

    # 锁内读当前 ACTIVE quote
    active_result = await db.execute(
        select(RfqQuote).where(
            RfqQuote.rfq_id == rfq.id,
            RfqQuote.quote_status == QuoteStatus.ACTIVE,
            RfqQuote.deleted_at.is_(None),
        )
    )
    active_quote = active_result.scalar_one_or_none()
    if not active_quote:
        raise QuoteRfqStateInvalidError(rfq.status)

    rfq.status = RfqStatus.ACCEPTED
    rfq.accepted_quote_id = active_quote.id

    is_operator = "OPERATOR" in user.roles
    extra: dict = {"rfq_no": rfq.rfq_no, "accepted_quote_id": active_quote.id}
    if is_operator:
        extra["acted_by_operator"] = True
        extra["buyer_org_id"] = rfq.buyer_org_id

    await write_audit(
        db,
        resource_type=AuditResourceType.RFQ,
        action=AuditAction.ACCEPT,
        user_id=user.id,
        user_email=user.email,
        resource_id=rfq.id,
        request=request,
        extra=extra,
        commit=False,
    )
    await db.commit()

    return {"rfq_id": rfq.id, "status": rfq.status, "accepted_quote_id": rfq.accepted_quote_id}


# ── 拒绝 ────────────────────────────────────────────────


async def reject_rfq(
    db: AsyncSession, user: CurrentUser, rfq_id: int,
    *, request: Request | None = None,
) -> dict:
    """QUOTED→REJECTED。"""
    rfq = await lock_rfq(db, rfq_id, user=user)

    # 幂等
    if rfq.status == RfqStatus.REJECTED:
        return {"rfq_id": rfq.id, "status": rfq.status}

    if not RfqStatus.can_transition(rfq.status, RfqStatus.REJECTED):
        raise RfqStateInvalidError(rfq.status)

    rfq.status = RfqStatus.REJECTED

    is_operator = "OPERATOR" in user.roles
    extra: dict = {"rfq_no": rfq.rfq_no}
    if is_operator:
        extra["acted_by_operator"] = True
        extra["buyer_org_id"] = rfq.buyer_org_id
    # 读 ACTIVE quote id 留痕
    active_result = await db.execute(
        select(RfqQuote.id).where(
            RfqQuote.rfq_id == rfq.id,
            RfqQuote.quote_status == QuoteStatus.ACTIVE,
            RfqQuote.deleted_at.is_(None),
        )
    )
    active_qid = active_result.scalar_one_or_none()
    if active_qid:
        extra["active_quote_id"] = active_qid

    await write_audit(
        db,
        resource_type=AuditResourceType.RFQ,
        action=AuditAction.REJECT,
        user_id=user.id,
        user_email=user.email,
        resource_id=rfq.id,
        request=request,
        extra=extra,
        commit=False,
    )
    await db.commit()

    return {"rfq_id": rfq.id, "status": rfq.status}


# ── 失效 ────────────────────────────────────────────────


async def expire_rfq(
    db: AsyncSession, user: CurrentUser, rfq_id: int,
    *, request: Request | None = None,
) -> dict:
    """QUOTED→EXPIRED。"""
    rfq = await lock_rfq(db, rfq_id, user=user)

    # 幂等
    if rfq.status == RfqStatus.EXPIRED:
        return {"rfq_id": rfq.id, "status": rfq.status}

    if not RfqStatus.can_transition(rfq.status, RfqStatus.EXPIRED):
        raise RfqStateInvalidError(rfq.status)

    rfq.status = RfqStatus.EXPIRED

    await write_audit(
        db,
        resource_type=AuditResourceType.QUOTE,
        action=AuditAction.EXPIRE,
        user_id=user.id,
        user_email=user.email,
        resource_id=rfq.id,
        request=request,
        extra={"rfq_no": rfq.rfq_no},
        commit=False,
    )
    await db.commit()

    return {"rfq_id": rfq.id, "status": rfq.status}


# ── 报价列表 ────────────────────────────────────────────


async def get_quotes(
    db: AsyncSession, user: CurrentUser, rfq_id: int,
) -> list[RfqQuoteBuyerPublic] | list[RfqQuoteOperatorView]:
    """BUYER 仅 ACTIVE(买方 DTO),OPERATOR 全版本(运营 DTO + 成本层)。"""
    is_buyer = "BUYER" in user.roles
    is_operator = "OPERATOR" in user.roles

    # scope 校验(不锁,GET 不需要)
    buyer_org_id = None
    if is_buyer and not is_operator:
        buyer_org_id = await _resolve_buyer_org_id(db, user)

    rfq = await load_rfq(
        db,
        rfq_id,
        with_items=False,
        buyer_org_id=buyer_org_id,
    )
    if not rfq:
        raise RfqNotFoundError()

    # 加载报价
    quote_q = (
        select(RfqQuote)
        .where(RfqQuote.rfq_id == rfq_id, RfqQuote.deleted_at.is_(None))
        .options(
            selectinload(RfqQuote.items).selectinload(RfqQuoteItem.tiers),
            selectinload(RfqQuote.items).selectinload(RfqQuoteItem.cost),
        )
        .order_by(RfqQuote.version.desc())
    )
    if is_buyer and not is_operator:
        quote_q = quote_q.where(RfqQuote.quote_status == QuoteStatus.ACTIVE)

    quotes = (await db.execute(quote_q)).scalars().all()

    if is_operator:
        return [_serialize_quote_operator(q) for q in quotes]
    return [_serialize_quote_buyer(q) for q in quotes]


# ── 加载并序列化单个报价(运营) ─────────────────────────────


async def _load_and_serialize_quote(
    db: AsyncSession, quote_id: int,
) -> RfqQuoteOperatorView:
    """重新加载并序列化(运营全量)。"""
    row = await db.execute(
        select(RfqQuote)
        .where(RfqQuote.id == quote_id)
        .options(
            selectinload(RfqQuote.items).selectinload(RfqQuoteItem.tiers),
            selectinload(RfqQuote.items).selectinload(RfqQuoteItem.cost),
        )
    )
    quote = row.scalar_one()
    return _serialize_quote_operator(quote)


# ── 序列化 ──────────────────────────────────────────────


def _serialize_quote_buyer(quote: RfqQuote) -> RfqQuoteBuyerPublic:
    """买方 DTO:无 cost/supplier/quoted_by/版本。"""
    items = [
        QuoteItemBuyerPublic(
            id=qi.id,
            rfq_item_id=qi.rfq_item_id,
            skipped=qi.skipped,
            skip_reason=qi.skip_reason,
            unit_price=qi.unit_price,
            moq=qi.moq,
            cbm_per_unit=qi.cbm_per_unit,
            gross_weight_per_unit=qi.gross_weight_per_unit,
            line_amount=qi.line_amount,
            tiers=[
                QuoteTierPublic(min_qty=t.min_qty, unit_price=t.unit_price)
                for t in (qi.tiers or [])
            ],
        )
        for qi in quote.items
        if getattr(qi, "deleted_at", None) is None
    ]
    return RfqQuoteBuyerPublic(
        id=quote.id,
        quote_no=quote.quote_no,
        trade_term=quote.trade_term,
        named_place=quote.named_place,
        currency=quote.currency,
        valid_until=quote.valid_until,
        lead_time_days=quote.lead_time_days,
        eta_days=quote.eta_days,
        total_amount=quote.total_amount,
        items=items,
    )


def _serialize_quote_operator(quote: RfqQuote) -> RfqQuoteOperatorView:
    """运营 DTO:全量含成本层。"""
    items = []
    for qi in quote.items:
        if getattr(qi, "deleted_at", None) is not None:
            continue
        cost_view = None
        if qi.cost and getattr(qi.cost, "deleted_at", None) is None:
            cost_view = QuoteCostView(
                supplier_org_id=qi.cost.supplier_org_id,
                supplier_unit_price=qi.cost.supplier_unit_price,
                freight_cost_alloc=qi.cost.freight_cost_alloc,
                insurance_cost=qi.cost.insurance_cost,
                export_clearance_cost=qi.cost.export_clearance_cost,
                consolidation_cost=qi.cost.consolidation_cost,
                gross_margin=qi.cost.gross_margin,
            )
        items.append(QuoteItemOperatorView(
            id=qi.id,
            rfq_item_id=qi.rfq_item_id,
            skipped=qi.skipped,
            skip_reason=qi.skip_reason,
            unit_price=qi.unit_price,
            moq=qi.moq,
            cbm_per_unit=qi.cbm_per_unit,
            gross_weight_per_unit=qi.gross_weight_per_unit,
            line_amount=qi.line_amount,
            tiers=[
                QuoteTierPublic(min_qty=t.min_qty, unit_price=t.unit_price)
                for t in (qi.tiers or [])
            ],
            cost=cost_view,
        ))
    return RfqQuoteOperatorView(
        id=quote.id,
        quote_no=quote.quote_no,
        version=quote.version,
        quote_status=quote.quote_status,
        quoted_by_user_id=quote.quoted_by_user_id,
        quoted_at=quote.quoted_at,
        trade_term=quote.trade_term,
        named_place=quote.named_place,
        currency=quote.currency,
        valid_until=quote.valid_until,
        lead_time_days=quote.lead_time_days,
        eta_days=quote.eta_days,
        total_amount=quote.total_amount,
        created_at=quote.created_at,
        items=items,
    )


# ── 详情层叠辅助(供 rfq service 调用)───────────────────


async def load_quote_for_rfq_detail(
    db: AsyncSession, rfq_id: int, *, is_operator: bool,
) -> RfqQuoteBuyerPublic | RfqQuoteOperatorView | list[RfqQuoteOperatorView] | None:
    """供 RFQ 详情层叠:买方返回 ACTIVE 的 BuyerPublic(或 None),运营返回全版本列表。"""
    quote_q = (
        select(RfqQuote)
        .where(RfqQuote.rfq_id == rfq_id, RfqQuote.deleted_at.is_(None))
        .options(
            selectinload(RfqQuote.items).selectinload(RfqQuoteItem.tiers),
            selectinload(RfqQuote.items).selectinload(RfqQuoteItem.cost),
        )
        .order_by(RfqQuote.version.desc())
    )
    if not is_operator:
        quote_q = quote_q.where(RfqQuote.quote_status == QuoteStatus.ACTIVE)

    quotes = (await db.execute(quote_q)).scalars().all()

    if is_operator:
        return [_serialize_quote_operator(q) for q in quotes] if quotes else []

    # 买方:仅 ACTIVE 单条
    if quotes:
        return _serialize_quote_buyer(quotes[0])
    return None
