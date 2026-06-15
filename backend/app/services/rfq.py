"""询价单 Service — 买方需求侧,单边模型。

创建(统一 items 入参/代客)、列表、详情、撤销。
报价由《报价回填后端》工单层叠。
提交点唯一在本 service;route 不自行 commit。

ADR-0006: 询价行引用 SPU(product_id) + variant_snapshot，不再依赖 SKU。
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from decimal import Decimal

from app.core.datetime import to_naive_utc

from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from fastapi import Request

from app.audit.constants import AuditAction, AuditResourceType
from app.audit.logger import write_audit
from app.core.dependencies import CurrentUser
from app.core.exceptions import (
    BuyerOrgRequiredError,
    RfqAlreadyClaimedError,
    RfqDuplicateItemError,
    RfqItemNotFoundError,
    RfqMinOneItemError,
    RfqNotAssignedToYouError,
    RfqProductNotAvailableError,
    RfqNoGenerationFailedError,
    RfqNoValidItemsError,
    RfqNotFoundError,
    RfqStateInvalidError,
)
from app.core.i18n import get_localized
from app.db.models.buyer_member import BuyerMember
from app.db.models.buyer_organization import BuyerOrgStatus, BuyerOrganization
from app.db.models.product import Product, ProductStatus
from app.db.models.rfq import Rfq, RfqSource, RfqStatus
from app.db.models.rfq_item import RfqItem
from app.schemas.rfq import (
    RfqBuyerPublic,
    RfqCreate,
    RfqItemEdit,
    RfqItemInput,
    RfqItemPublic,
    RfqOperatorView,
    RfqUpdate,
)
from app.services import quote as quote_svc
from app.services._rfq_loader import load_rfq, lock_rfq, resolve_rfq_scope
from app.services._variant_utils import normalize_variants_to_en

logger = logging.getLogger(__name__)

# rfq_no 并发重试上限
_RFQ_NO_MAX_RETRIES = 5


# ── 组织解析 ───────────────────────────────────────────

async def _resolve_active_buyer_org(
    db: AsyncSession, user: CurrentUser,
) -> BuyerOrganization:
    """复用购物车口径:经 buyer_members 解析当前用户买方组织。"""
    row = await db.execute(
        select(BuyerOrganization)
        .join(BuyerMember, BuyerMember.buyer_org_id == BuyerOrganization.id)
        .where(
            BuyerMember.user_id == user.id,
            BuyerOrganization.status == BuyerOrgStatus.ACTIVE,
        )
        .limit(1)
    )
    org = row.scalar_one_or_none()
    if not org:
        raise BuyerOrgRequiredError()
    return org


async def _validate_buyer_org_by_id(
    db: AsyncSession, org_id: int,
) -> BuyerOrganization:
    """运营代客:校验目标买方组织存在且 ACTIVE。"""
    row = await db.execute(
        select(BuyerOrganization).where(
            BuyerOrganization.id == org_id,
            BuyerOrganization.status == BuyerOrgStatus.ACTIVE,
        )
    )
    org = row.scalar_one_or_none()
    if not org:
        raise BuyerOrgRequiredError()
    return org


# ── rfq_no 生成 ────────────────────────────────────────

async def _generate_rfq_no(db: AsyncSession) -> str:
    """格式 RFQ-YYYYMMDD-####,对齐 _generate_spu_code 日序号。"""
    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    prefix = f"RFQ-{today}-"

    count_result = await db.execute(
        select(func.count()).select_from(Rfq).where(
            Rfq.rfq_no.like(f"{prefix}%"),
        )
    )
    seq = (count_result.scalar() or 0) + 1
    return f"{prefix}{seq:04d}"


# ── SPU 可用性校验 ────────────────────────────────────

async def _get_viewable_product(db: AsyncSession, product_id: int) -> Product | None:
    """校验 SPU 是否 ACTIVE + 未软删。"""
    row = await db.execute(
        select(Product).where(
            Product.id == product_id,
            Product.status == ProductStatus.ACTIVE,
            Product.deleted_at.is_(None),
        )
    )
    return row.scalar_one_or_none()


# ── 变体快照动态拼接（序列化时用，不入库）──────────────

def _variant_snapshot_to_display(snapshot: list[dict], locale: str = "zh") -> str | None:
    """将 variant_snapshot 拼接为人类可读文本。

    MVP: 直接用英文原值拼接。后续可按 locale 反查 product_attrs 翻译。
    """
    if not snapshot:
        return None
    parts = [f"{s.get('attr_name', '')}: {s.get('value', '')}" for s in snapshot]
    return " / ".join(parts)


# ── 去重校验 ──────────────────────────────────────────

def _check_duplicate_items(items: list) -> None:
    """按 (product_id, selected_variants) 去重，数组先排序避免顺序不同误判。"""
    seen: set[tuple] = set()
    for it in items:
        normalized = sorted(
            it.selected_variants,
            key=lambda x: (x.get("attr_name", x.get("key", "")), x.get("value", "")),
        )
        key = (it.product_id, json.dumps(normalized, sort_keys=True, ensure_ascii=False))
        if key in seen:
            raise RfqDuplicateItemError()
        seen.add(key)


# ── 创建询价单 ─────────────────────────────────────────

async def create_rfq(
    db: AsyncSession, user: CurrentUser, payload: RfqCreate,
    *, idempotency_key: str | None = None, request: Request | None = None,
) -> RfqBuyerPublic | RfqOperatorView:
    """单聚合事务创建询价单。"""
    scope = resolve_rfq_scope(user)

    # ── 角色与来源约束 ──
    if scope.is_buyer:
        org = await _resolve_active_buyer_org(db, user)
        buyer_org_id = org.id
        buyer_user_id = user.id
        created_by_user_id = user.id
        source = RfqSource.BUYER_SELF
    elif scope.is_operator:
        if not payload.buyer_org_id:
            raise BuyerOrgRequiredError()
        await _validate_buyer_org_by_id(db, payload.buyer_org_id)
        buyer_org_id = payload.buyer_org_id
        buyer_user_id = None
        created_by_user_id = user.id
        source = RfqSource.OPERATOR_PROXY
    else:
        raise BuyerOrgRequiredError()

    # ── 幂等预检:顺序重试命中既有单,短路返回 ──
    if idempotency_key:
        existing = await db.execute(
            select(Rfq.id).where(
                Rfq.created_by_user_id == created_by_user_id,
                Rfq.idempotency_key == idempotency_key,
                Rfq.deleted_at.is_(None),
            )
        )
        existing_id = existing.scalar_one_or_none()
        if existing_id is not None:
            return await _load_and_serialize(db, existing_id, is_operator=scope.is_operator)

    # ── 1. 行项解析 ──
    if not payload.items:
        raise RfqNoValidItemsError()
    _check_duplicate_items(payload.items)
    item_rows = _resolve_direct_items(payload.items)

    # ── 2. SPU 可用性校验 + 快照数据 ──
    offending: list[int] = []
    for row in item_rows:
        product = await _get_viewable_product(db, row["product_id"])
        if not product:
            offending.append(row["product_id"])
        else:
            row["product_name_snapshot_zh"] = product.name_zh
            row["product_name_snapshot_en"] = product.name_en
            row["uom_snapshot"] = product.unit
            row["variant_snapshot"] = await normalize_variants_to_en(
                db, product.id, row["selected_variants"],
            )
    if offending:
        raise RfqProductNotAvailableError(offending)

    # ── 3. 生成 rfq_no ──
    rfq_no = await _generate_rfq_no(db)

    # ── 4. SAVEPOINT 内只插 Rfq ──
    rfq: Rfq | None = None
    for attempt in range(_RFQ_NO_MAX_RETRIES):
        nested = await db.begin_nested()
        try:
            rfq = Rfq(
                rfq_no=rfq_no,
                buyer_org_id=buyer_org_id,
                buyer_user_id=buyer_user_id,
                created_by_user_id=created_by_user_id,
                source=source,
                status=RfqStatus.DRAFT if payload.as_draft else RfqStatus.SUBMITTED,
                idempotency_key=idempotency_key,
                contact_name=payload.contact_name,
                contact_phone=payload.contact_phone,
                contact_email=payload.contact_email,
                remark=payload.remark,
                requested_delivery_place=payload.requested_delivery_place,
                expected_delivery_date=to_naive_utc(payload.expected_delivery_date),
                target_currency=payload.target_currency,
                required_certifications=payload.required_certifications or [],
                attachment_urls=payload.attachment_urls or [],
            )
            db.add(rfq)
            await db.flush()
        except IntegrityError:
            await nested.rollback()
            if idempotency_key:
                idem_hit = await db.execute(
                    select(Rfq.id).where(
                        Rfq.created_by_user_id == created_by_user_id,
                        Rfq.idempotency_key == idempotency_key,
                        Rfq.deleted_at.is_(None),
                    )
                )
                idem_id = idem_hit.scalar_one_or_none()
                if idem_id is not None:
                    return await _load_and_serialize(db, idem_id, is_operator=scope.is_operator)
            existing = await db.execute(
                select(Rfq.id).where(Rfq.rfq_no == rfq_no)
            )
            if existing.scalar_one_or_none() is None:
                raise
            rfq_no = await _generate_rfq_no(db)
            rfq = None
            continue
        except BaseException:
            await nested.rollback()
            raise
        else:
            await nested.commit()
            break

    if rfq is None:
        raise RfqNoGenerationFailedError()

    # ── 5. SAVEPOINT 成功后 add RfqItem ──
    for row in item_rows:
        db.add(RfqItem(
            rfq_id=rfq.id,
            product_id=row["product_id"],
            variant_snapshot=row["variant_snapshot"],
            product_name_snapshot_zh=row.get("product_name_snapshot_zh"),
            product_name_snapshot_en=row.get("product_name_snapshot_en"),
            uom_snapshot=row.get("uom_snapshot"),
            quantity=row["quantity"],
            target_unit_price=row.get("target_unit_price"),
            remark=row.get("remark"),
        ))

    # ── 6. 审计 + 单次 commit ──
    if source == RfqSource.OPERATOR_PROXY:
        audit_action = AuditAction.PROXY_CREATE
    elif payload.as_draft:
        audit_action = AuditAction.CREATE
    else:
        audit_action = AuditAction.SUBMIT
    await write_audit(
        db,
        resource_type=AuditResourceType.RFQ,
        action=audit_action,
        user_id=user.id,
        user_email=user.email,
        resource_id=rfq.id,
        request=request,
        extra={"rfq_no": rfq.rfq_no, "source": source, "item_count": len(item_rows)},
        commit=False,
    )
    await db.commit()

    return await _load_and_serialize(db, rfq.id, is_operator=scope.is_operator)


# ── 列表 ──────────────────────────────────────────────

async def list_rfqs(
    db: AsyncSession, user: CurrentUser,
    *, page: int = 1, page_size: int = 20,
    status_filter: str | None = None,
    buyer_org_id_filter: int | None = None,
    mine: bool = False,
) -> dict:
    """列表,BUYER 限本组织,OPERATOR 全量。"""
    scope = resolve_rfq_scope(user)

    q = select(Rfq).where(Rfq.deleted_at.is_(None))
    count_q = select(func.count()).select_from(Rfq).where(Rfq.deleted_at.is_(None))

    if scope.is_buyer and not scope.is_operator:
        org = await _resolve_active_buyer_org(db, user)
        q = q.where(Rfq.buyer_org_id == org.id)
        count_q = count_q.where(Rfq.buyer_org_id == org.id)
        if mine:
            q = q.where(Rfq.buyer_user_id == user.id)
            count_q = count_q.where(Rfq.buyer_user_id == user.id)

    # Operator 不看买方草稿和已取消的询价单
    if scope.is_operator and not scope.is_buyer:
        hidden = (RfqStatus.DRAFT, RfqStatus.CANCELLED)
        q = q.where(Rfq.status.notin_(hidden))
        count_q = count_q.where(Rfq.status.notin_(hidden))

    if status_filter:
        q = q.where(Rfq.status == status_filter)
        count_q = count_q.where(Rfq.status == status_filter)

    if buyer_org_id_filter and scope.is_operator:
        q = q.where(Rfq.buyer_org_id == buyer_org_id_filter)
        count_q = count_q.where(Rfq.buyer_org_id == buyer_org_id_filter)

    total = (await db.execute(count_q)).scalar() or 0

    q = (
        q.options(selectinload(Rfq.items))
        .order_by(Rfq.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = (await db.execute(q)).scalars().all()

    serialized = [_serialize_rfq(r, is_operator=scope.is_operator) for r in rows]
    return {
        "items": [s.model_dump() for s in serialized],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


# ── 详情 ──────────────────────────────────────────────

async def get_rfq(
    db: AsyncSession, user: CurrentUser, rfq_id: int,
) -> RfqBuyerPublic | RfqOperatorView:
    """详情,scope 校验 + 报价层叠。"""
    scope = resolve_rfq_scope(user)

    rfq = await load_rfq(db, rfq_id, with_items=True)
    if not rfq:
        raise RfqNotFoundError()

    # scope 校验
    if scope.is_buyer and not scope.is_operator:
        org = await _resolve_active_buyer_org(db, user)
        if rfq.buyer_org_id != org.id:
            raise RfqNotFoundError()

    # 报价层叠
    quote_data = await quote_svc.load_quote_for_rfq_detail(
        db, rfq.id, is_operator=scope.is_operator,
    )

    return _serialize_rfq(rfq, is_operator=scope.is_operator, quote_data=quote_data)


# ── 撤销 ──────────────────────────────────────────────

async def cancel_rfq(
    db: AsyncSession, user: CurrentUser, rfq_id: int,
    cancel_reason: str | None = None,
    *, request: Request | None = None,
) -> RfqBuyerPublic | RfqOperatorView:
    """撤销守卫 + 幂等 + 行锁串行化。"""
    scope = resolve_rfq_scope(user)

    rfq = await lock_rfq(db, rfq_id, user=user, with_items=True)

    if rfq.status == RfqStatus.CANCELLED:
        return _serialize_rfq(rfq, is_operator=scope.is_operator)

    if scope.is_buyer and not scope.is_operator:
        if rfq.status not in RfqStatus.BUYER_CANCELLABLE:
            raise RfqStateInvalidError(rfq.status)

    if not RfqStatus.can_transition(rfq.status, RfqStatus.CANCELLED):
        raise RfqStateInvalidError(rfq.status)

    rfq.status = RfqStatus.CANCELLED
    rfq.cancel_reason = cancel_reason

    await write_audit(
        db,
        resource_type=AuditResourceType.RFQ,
        action=AuditAction.CANCEL,
        user_id=user.id,
        user_email=user.email,
        resource_id=rfq.id,
        request=request,
        extra={"rfq_no": rfq.rfq_no, "cancel_reason": cancel_reason},
        commit=False,
    )
    await db.commit()

    return await _load_and_serialize(db, rfq.id, is_operator=scope.is_operator)


# ── 行来源解析 ─────────────────────────────────────────

def _resolve_direct_items(items: list) -> list[dict]:
    """行项解析(快照在可购校验后填充)。"""
    return [
        {
            "product_id": it.product_id,
            "selected_variants": it.selected_variants,
            "quantity": it.quantity,
            "target_unit_price": it.target_unit_price,
            "remark": it.remark,
        }
        for it in items
    ]


# ── 加载与序列化 ──────────────────────────────────────

async def _load_and_serialize(
    db: AsyncSession, rfq_id: int, *, is_operator: bool, refresh: bool = False,
) -> RfqBuyerPublic | RfqOperatorView:
    """重新加载并序列化。refresh=True 时强制从 DB 刷新（行项增删后需要）。"""
    if refresh:
        # 清除 identity map 中的旧缓存，确保 selectinload 拿到最新行项
        await db.execute(
            select(Rfq).where(Rfq.id == rfq_id)
            .options(selectinload(Rfq.items))
            .execution_options(populate_existing=True)
        )
    rfq = await load_rfq(db, rfq_id, with_items=True)
    if not rfq:
        raise RfqNotFoundError()
    return _serialize_rfq(rfq, is_operator=is_operator)


def _serialize_item(item: RfqItem, locale: str = "zh") -> RfqItemPublic:
    """序列化行项目,按 locale 选快照语言。"""
    if locale == "en":
        name = item.product_name_snapshot_en or item.product_name_snapshot_zh
    else:
        name = item.product_name_snapshot_zh or item.product_name_snapshot_en

    # 新数据：从 variant_snapshot JSON 动态拼接
    # 旧数据（variant_snapshot 为空）：fallback 到 variant_snapshot_zh/en 文本列
    if item.variant_snapshot:
        display = _variant_snapshot_to_display(item.variant_snapshot, locale)
    else:
        display = (item.variant_snapshot_zh if locale == "zh" else item.variant_snapshot_en) \
                  or item.variant_snapshot_zh or item.variant_snapshot_en

    return RfqItemPublic(
        id=item.id,
        product_id=item.product_id,
        variant_snapshot=item.variant_snapshot or [],
        variant_display=display,
        product_name_snapshot=name,
        uom_snapshot=item.uom_snapshot,
        quantity=item.quantity,
        target_unit_price=item.target_unit_price,
        remark=item.remark,
    )


def _serialize_rfq(
    rfq: Rfq, *, is_operator: bool, quote_data: object = None,
) -> RfqBuyerPublic | RfqOperatorView:
    """按角色序列化询价单。quote_data 由详情接口传入(层叠报价)。"""
    active_items = [
        it for it in rfq.items
        if getattr(it, "deleted_at", None) is None
    ]
    items = [_serialize_item(it) for it in active_items]

    if is_operator:
        result = RfqOperatorView(
            id=rfq.id,
            rfq_no=rfq.rfq_no,
            status=rfq.status,
            source=rfq.source,
            buyer_org_id=rfq.buyer_org_id,
            buyer_user_id=rfq.buyer_user_id,
            created_by_user_id=rfq.created_by_user_id,
            operator_assignee_id=rfq.operator_assignee_id,
            contact_name=rfq.contact_name,
            contact_phone=rfq.contact_phone,
            contact_email=rfq.contact_email,
            remark=rfq.remark,
            cancel_reason=rfq.cancel_reason,
            requested_delivery_place=rfq.requested_delivery_place,
            expected_delivery_date=rfq.expected_delivery_date,
            target_currency=rfq.target_currency,
            required_certifications=rfq.required_certifications,
            attachment_urls=rfq.attachment_urls,
            created_at=rfq.created_at,
            updated_at=rfq.updated_at,
            items=items,
        )
        if quote_data is not None:
            result.quotes = quote_data
        return result

    result = RfqBuyerPublic(
        id=rfq.id,
        rfq_no=rfq.rfq_no,
        status=rfq.status,
        source=rfq.source,
        contact_name=rfq.contact_name,
        contact_phone=rfq.contact_phone,
        contact_email=rfq.contact_email,
        remark=rfq.remark,
        requested_delivery_place=rfq.requested_delivery_place,
        expected_delivery_date=rfq.expected_delivery_date,
        target_currency=rfq.target_currency,
        required_certifications=rfq.required_certifications,
        attachment_urls=rfq.attachment_urls,
        created_at=rfq.created_at,
        updated_at=rfq.updated_at,
        items=items,
    )
    if quote_data is not None:
        result.quote = quote_data
    return result


# ── 受理 ────────────────────────────────────────────────


async def claim_rfq(
    db: AsyncSession, user: CurrentUser, rfq_id: int,
    *, request: Request | None = None,
) -> RfqOperatorView:
    """运营受理询价单：SUBMITTED → PROCESSING，写 operator_assignee_id。"""
    rfq = await lock_rfq(db, rfq_id, user=user, with_items=True)

    if rfq.status == RfqStatus.PROCESSING and rfq.operator_assignee_id == user.id:
        return _serialize_rfq(rfq, is_operator=True)

    if rfq.status == RfqStatus.PROCESSING and rfq.operator_assignee_id != user.id:
        raise RfqAlreadyClaimedError()

    if not RfqStatus.can_transition(rfq.status, RfqStatus.PROCESSING):
        raise RfqStateInvalidError(rfq.status)

    rfq.status = RfqStatus.PROCESSING
    rfq.operator_assignee_id = user.id

    await write_audit(
        db,
        resource_type=AuditResourceType.RFQ,
        action=AuditAction.CLAIM,
        user_id=user.id,
        user_email=user.email,
        resource_id=rfq.id,
        request=request,
        extra={"rfq_no": rfq.rfq_no},
        commit=False,
    )
    await db.commit()

    return await _load_and_serialize(db, rfq.id, is_operator=True)


# ── 提交草稿 ────────────────────────────────────────────


async def submit_rfq(
    db: AsyncSession, user: CurrentUser, rfq_id: int,
    *, request: Request | None = None,
) -> RfqBuyerPublic:
    """买方提交草稿询价单：DRAFT → SUBMITTED。"""
    rfq = await lock_rfq(db, rfq_id, user=user, with_items=True)

    if rfq.status == RfqStatus.SUBMITTED:
        return _serialize_rfq(rfq, is_operator=False)

    if not RfqStatus.can_transition(rfq.status, RfqStatus.SUBMITTED):
        raise RfqStateInvalidError(rfq.status)

    active_items = [it for it in rfq.items if getattr(it, "deleted_at", None) is None]
    if not active_items:
        raise RfqNoValidItemsError()

    # 二次校验：草稿保存后商品可能被下架/删除，提交前重新确认
    offending: list[int] = []
    for it in active_items:
        product = await _get_viewable_product(db, it.product_id)
        if not product:
            offending.append(it.product_id)
    if offending:
        raise RfqProductNotAvailableError(offending)

    rfq.status = RfqStatus.SUBMITTED

    await write_audit(
        db,
        resource_type=AuditResourceType.RFQ,
        action=AuditAction.SUBMIT,
        user_id=user.id,
        user_email=user.email,
        resource_id=rfq.id,
        request=request,
        extra={"rfq_no": rfq.rfq_no},
        commit=False,
    )
    await db.commit()

    return await _load_and_serialize(db, rfq.id, is_operator=False)


# ── 撤回改单 ────────────────────────────────────────────


async def withdraw_rfq(
    db: AsyncSession, user: CurrentUser, rfq_id: int,
    *, request: Request | None = None,
) -> RfqBuyerPublic:
    """买方撤回询价单：SUBMITTED → DRAFT，回到可编辑态。"""
    rfq = await lock_rfq(db, rfq_id, user=user, with_items=True)

    if rfq.status == RfqStatus.DRAFT:
        return _serialize_rfq(rfq, is_operator=False)

    if not RfqStatus.can_transition(rfq.status, RfqStatus.DRAFT):
        raise RfqStateInvalidError(rfq.status)

    rfq.status = RfqStatus.DRAFT

    await write_audit(
        db,
        resource_type=AuditResourceType.RFQ,
        action=AuditAction.WITHDRAW,
        user_id=user.id,
        user_email=user.email,
        resource_id=rfq.id,
        request=request,
        extra={"rfq_no": rfq.rfq_no},
        commit=False,
    )
    await db.commit()

    return await _load_and_serialize(db, rfq.id, is_operator=False)


# ── 草稿态整单更新 ─────────────────────────────────────


async def update_rfq(
    db: AsyncSession, user: CurrentUser, rfq_id: int,
    payload: RfqUpdate,
    *, request: Request | None = None,
) -> RfqBuyerPublic:
    """草稿态整单更新：行项全量替换 + 元数据更新。仅 DRAFT 可操作。"""
    rfq = await lock_rfq(db, rfq_id, user=user, with_items=True)

    if rfq.status != RfqStatus.DRAFT:
        raise RfqStateInvalidError(rfq.status)

    if not payload.items:
        raise RfqNoValidItemsError()
    _check_duplicate_items(payload.items)

    item_rows = _resolve_direct_items(payload.items)
    offending: list[int] = []
    for row in item_rows:
        product = await _get_viewable_product(db, row["product_id"])
        if not product:
            offending.append(row["product_id"])
        else:
            row["product_name_snapshot_zh"] = product.name_zh
            row["product_name_snapshot_en"] = product.name_en
            row["uom_snapshot"] = product.unit
            row["variant_snapshot"] = await normalize_variants_to_en(
                db, product.id, row["selected_variants"],
            )
    if offending:
        raise RfqProductNotAvailableError(offending)

    # 硬删旧行项(草稿态配置数据，全量替换)
    await db.execute(delete(RfqItem).where(RfqItem.rfq_id == rfq.id))

    for row in item_rows:
        db.add(RfqItem(
            rfq_id=rfq.id,
            product_id=row["product_id"],
            variant_snapshot=row["variant_snapshot"],
            product_name_snapshot_zh=row.get("product_name_snapshot_zh"),
            product_name_snapshot_en=row.get("product_name_snapshot_en"),
            uom_snapshot=row.get("uom_snapshot"),
            quantity=row["quantity"],
            target_unit_price=row.get("target_unit_price"),
            remark=row.get("remark"),
        ))

    rfq.contact_name = payload.contact_name
    rfq.contact_phone = payload.contact_phone
    rfq.contact_email = payload.contact_email
    rfq.requested_delivery_place = payload.requested_delivery_place
    rfq.expected_delivery_date = to_naive_utc(payload.expected_delivery_date)
    rfq.target_currency = payload.target_currency
    rfq.required_certifications = payload.required_certifications or []
    rfq.attachment_urls = payload.attachment_urls or []
    rfq.remark = payload.remark

    await write_audit(
        db,
        resource_type=AuditResourceType.RFQ,
        action=AuditAction.UPDATE,
        user_id=user.id,
        user_email=user.email,
        resource_id=rfq.id,
        request=request,
        extra={"rfq_no": rfq.rfq_no, "item_count": len(item_rows)},
        commit=False,
    )
    await db.commit()

    return await _load_and_serialize(db, rfq.id, is_operator=False)


# ── 运营行项编辑辅助函数 ──────────────────────────────────


def _assert_operator_can_edit_items(rfq: Rfq, user: CurrentUser) -> None:
    """校验运营是否可编辑行项：PROCESSING + 是受理人。"""
    if rfq.status != RfqStatus.PROCESSING:
        raise RfqStateInvalidError(rfq.status)
    if rfq.operator_assignee_id != user.id:
        raise RfqNotAssignedToYouError()


def _find_item(rfq: Rfq, item_id: int) -> RfqItem:
    """在询价单行项中查找指定 ID 的活跃行项。"""
    for it in rfq.items:
        if it.id == item_id and getattr(it, "deleted_at", None) is None:
            return it
    raise RfqItemNotFoundError()


def _make_fingerprint(product_id: int, variant_snapshot: list) -> str:
    """生成 product_id + variant_snapshot 的去重指纹。"""
    normalized = sorted(
        (variant_snapshot or []),
        key=lambda x: (x.get("attr_name", ""), x.get("value", "")),
    )
    return f"{product_id}::{json.dumps(normalized, sort_keys=True, ensure_ascii=False)}"


def _item_fingerprint(item: RfqItem) -> str:
    """从已有行项生成去重指纹。"""
    return _make_fingerprint(item.product_id, item.variant_snapshot or [])


# ── 编辑行项数量（DRAFT + PROCESSING） ──────────────────


async def update_rfq_item_qty(
    db: AsyncSession, user: CurrentUser,
    rfq_id: int, item_id: int, quantity: Decimal,
    *, request: Request | None = None,
) -> RfqBuyerPublic | RfqOperatorView:
    """修改行项数量。DRAFT（买方）或 PROCESSING（受理人）可操作。"""
    rfq = await lock_rfq(db, rfq_id, user=user, with_items=True)

    scope = resolve_rfq_scope(user)

    if rfq.status == RfqStatus.DRAFT:
        pass  # 买方可改
    elif rfq.status == RfqStatus.PROCESSING:
        _assert_operator_can_edit_items(rfq, user)
    else:
        raise RfqStateInvalidError(rfq.status)

    target_item = _find_item(rfq, item_id)
    target_item.quantity = quantity

    await write_audit(
        db,
        resource_type=AuditResourceType.RFQ,
        action=AuditAction.UPDATE,
        user_id=user.id,
        user_email=user.email,
        resource_id=rfq.id,
        request=request,
        extra={"rfq_no": rfq.rfq_no, "item_id": item_id, "quantity": str(quantity)},
        commit=False,
    )
    await db.commit()

    return await _load_and_serialize(db, rfq.id, is_operator=scope.is_operator)


# ── 运营行项增删改（PROCESSING 态） ──────────────────────


async def add_rfq_item(
    db: AsyncSession, user: CurrentUser,
    rfq_id: int, payload: RfqItemInput,
    *, request: Request | None = None,
) -> RfqOperatorView:
    """PROCESSING 态添加行项（运营受理人）。"""
    rfq = await lock_rfq(db, rfq_id, user=user, with_items=True)
    _assert_operator_can_edit_items(rfq, user)

    # SPU 可用性校验
    product = await _get_viewable_product(db, payload.product_id)
    if not product:
        raise RfqProductNotAvailableError([payload.product_id])

    # 变体规范化
    variant_snapshot = await normalize_variants_to_en(
        db, product.id, payload.selected_variants,
    )

    # 去重检查
    existing_fps = {
        _item_fingerprint(it) for it in rfq.items
        if getattr(it, "deleted_at", None) is None
    }
    if _make_fingerprint(payload.product_id, variant_snapshot) in existing_fps:
        raise RfqDuplicateItemError()

    db.add(RfqItem(
        rfq_id=rfq.id,
        product_id=product.id,
        variant_snapshot=variant_snapshot,
        product_name_snapshot_zh=product.name_zh,
        product_name_snapshot_en=product.name_en,
        uom_snapshot=product.unit,
        quantity=payload.quantity,
        target_unit_price=payload.target_unit_price,
        remark=payload.remark,
    ))

    await write_audit(
        db,
        resource_type=AuditResourceType.RFQ,
        action=AuditAction.UPDATE,
        user_id=user.id,
        user_email=user.email,
        resource_id=rfq.id,
        request=request,
        extra={"rfq_no": rfq.rfq_no, "op": "ADD_ITEM", "product_id": product.id},
        commit=False,
    )
    await db.commit()
    return await _load_and_serialize(db, rfq.id, is_operator=True, refresh=True)


async def edit_rfq_item(
    db: AsyncSession, user: CurrentUser,
    rfq_id: int, item_id: int, payload: RfqItemEdit,
    *, request: Request | None = None,
) -> RfqOperatorView:
    """PROCESSING 态编辑行项（运营受理人）：可改变体、数量、备注。"""
    rfq = await lock_rfq(db, rfq_id, user=user, with_items=True)
    _assert_operator_can_edit_items(rfq, user)

    target = _find_item(rfq, item_id)

    if payload.selected_variants is not None:
        product = await _get_viewable_product(db, target.product_id)
        if not product:
            raise RfqProductNotAvailableError([target.product_id])
        target.variant_snapshot = await normalize_variants_to_en(
            db, product.id, payload.selected_variants,
        )
        # 快照刷新
        target.product_name_snapshot_zh = product.name_zh
        target.product_name_snapshot_en = product.name_en
        target.uom_snapshot = product.unit

    if payload.quantity is not None:
        target.quantity = payload.quantity
    if payload.target_unit_price is not None:
        target.target_unit_price = payload.target_unit_price
    if payload.remark is not None:
        target.remark = payload.remark

    await write_audit(
        db,
        resource_type=AuditResourceType.RFQ,
        action=AuditAction.UPDATE,
        user_id=user.id,
        user_email=user.email,
        resource_id=rfq.id,
        request=request,
        extra={"rfq_no": rfq.rfq_no, "op": "EDIT_ITEM", "item_id": item_id},
        commit=False,
    )
    await db.commit()
    return await _load_and_serialize(db, rfq.id, is_operator=True, refresh=True)


async def delete_rfq_item(
    db: AsyncSession, user: CurrentUser,
    rfq_id: int, item_id: int,
    *, request: Request | None = None,
) -> RfqOperatorView:
    """PROCESSING 态删除行项（运营受理人）。至少保留 1 行。"""
    rfq = await lock_rfq(db, rfq_id, user=user, with_items=True)
    _assert_operator_can_edit_items(rfq, user)

    active_items = [it for it in rfq.items if getattr(it, "deleted_at", None) is None]
    if len(active_items) <= 1:
        raise RfqMinOneItemError()

    target = _find_item(rfq, item_id)
    # 行项是配置数据，硬删
    await db.delete(target)

    await write_audit(
        db,
        resource_type=AuditResourceType.RFQ,
        action=AuditAction.UPDATE,
        user_id=user.id,
        user_email=user.email,
        resource_id=rfq.id,
        request=request,
        extra={"rfq_no": rfq.rfq_no, "op": "DELETE_ITEM", "item_id": item_id},
        commit=False,
    )
    await db.commit()
    return await _load_and_serialize(db, rfq.id, is_operator=True, refresh=True)
