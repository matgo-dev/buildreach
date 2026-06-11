"""询价单 Service — 买方需求侧,单边模型。

创建(CART/DIRECT/代客)、列表、详情、撤销。
报价由《报价回填后端》工单层叠。
提交点唯一在本 service;route 不自行 commit。
"""
from __future__ import annotations

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
    RfqDuplicateSkuError,
    RfqItemNotFoundError,
    RfqItemNotPurchasableError,
    RfqNoGenerationFailedError,
    RfqNoValidItemsError,
    RfqNotFoundError,
    RfqSourceNotAllowedError,
    RfqStateInvalidError,
)
from app.core.i18n import get_localized
from app.db.models.buyer_member import BuyerMember
from app.db.models.buyer_organization import BuyerOrgStatus, BuyerOrganization
from app.db.models.cart import Cart
from app.db.models.cart_item import CartItem
from app.db.models.product import Product
from app.db.models.product_sku import ProductSku
from app.db.models.rfq import Rfq, RfqSource, RfqStatus
from app.db.models.rfq_item import RfqItem
from app.schemas.rfq import (
    RfqBuyerPublic,
    RfqCreate,
    RfqItemPublic,
    RfqOperatorView,
    SourceType,
)
from app.services import product as product_svc
from app.services import quote as quote_svc
from app.services._rfq_loader import load_rfq, lock_rfq

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


# ── 快照构建 ───────────────────────────────────────────

def _build_sku_spec(sku: ProductSku) -> tuple[str | None, str | None]:
    """构建 SKU 规格快照:name + color + material 组合。"""
    parts_zh = [p for p in [sku.name_zh, sku.color_zh, sku.material_zh] if p]
    parts_en = [p for p in [sku.name_en, sku.color_en, sku.material_en] if p]
    return (
        " / ".join(parts_zh) if parts_zh else None,
        " / ".join(parts_en) if parts_en else None,
    )


# ── 创建询价单 ─────────────────────────────────────────

async def create_rfq(
    db: AsyncSession, user: CurrentUser, payload: RfqCreate,
    *, idempotency_key: str | None = None, request: Request | None = None,
) -> RfqBuyerPublic | RfqOperatorView:
    """单聚合事务创建询价单。"""
    is_buyer = "BUYER" in user.roles
    is_operator = "OPERATOR" in user.roles

    # ── 角色与来源约束 ──
    if is_buyer:
        org = await _resolve_active_buyer_org(db, user)
        buyer_org_id = org.id
        buyer_user_id = user.id
        created_by_user_id = user.id
        source = RfqSource.BUYER_SELF
    elif is_operator:
        # 运营仅 DIRECT
        if payload.source_type != SourceType.DIRECT:
            raise RfqSourceNotAllowedError()
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
            return await _load_and_serialize(db, existing_id, is_operator=is_operator)

    # ── 1. 取行来源 ──
    item_rows: list[dict] = []
    cart_item_ids_to_delete: list[int] = []

    if payload.source_type == SourceType.CART:
        item_rows, cart_item_ids_to_delete = await _resolve_cart_items(
            db, user, buyer_org_id, payload.cart_item_ids,
        )
    else:  # DIRECT
        if not payload.items:
            raise RfqNoValidItemsError()
        # 重复 SKU 检查
        sku_ids = [it.sku_id for it in payload.items]
        if len(sku_ids) != len(set(sku_ids)):
            raise RfqDuplicateSkuError()
        item_rows = await _resolve_direct_items(db, payload.items)

    if not item_rows:
        raise RfqNoValidItemsError()

    # ── 2. 可购重校验(权威闸)+ 快照数据 ──
    offending: list[int] = []
    for row in item_rows:
        sku = await product_svc.get_purchasable_sku(db, row["sku_id"])
        if not sku:
            offending.append(row["sku_id"])
        else:
            # 单独加载 product(get_purchasable_sku 不含 eagerly loaded product)
            prod_row = await db.execute(
                select(Product).where(Product.id == sku.product_id)
            )
            product = prod_row.scalar_one_or_none()
            row["product_name_snapshot_zh"] = product.name_zh if product else None
            row["product_name_snapshot_en"] = product.name_en if product else None
            spec_zh, spec_en = _build_sku_spec(sku)
            row["sku_spec_snapshot_zh"] = spec_zh
            row["sku_spec_snapshot_en"] = spec_en
            row["uom_snapshot"] = product.unit if product else None
    if offending:
        raise RfqItemNotPurchasableError(offending)

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
                status=RfqStatus.SUBMITTED,
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
            # 按冲突源分流：幂等键 > rfq_no > 未知
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
                    # 幂等并发命中,短路返回既有单（不写审计/不删购物车）
                    return await _load_and_serialize(db, idem_id, is_operator=is_operator)
            # 回查确认是 rfq_no 冲突
            existing = await db.execute(
                select(Rfq.id).where(Rfq.rfq_no == rfq_no)
            )
            if existing.scalar_one_or_none() is None:
                raise  # 非 rfq_no 冲突,不误吞
            # rfq_no 冲突,重新生成序号重试
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
        raise RfqNoGenerationFailedError()  # 极端情况:重试耗尽

    # ── 5. SAVEPOINT 成功后 add RfqItem ──
    for row in item_rows:
        db.add(RfqItem(
            rfq_id=rfq.id,
            sku_id=row["sku_id"],
            product_name_snapshot_zh=row.get("product_name_snapshot_zh"),
            product_name_snapshot_en=row.get("product_name_snapshot_en"),
            sku_spec_snapshot_zh=row.get("sku_spec_snapshot_zh"),
            sku_spec_snapshot_en=row.get("sku_spec_snapshot_en"),
            uom_snapshot=row.get("uom_snapshot"),
            quantity=row["quantity"],
            target_unit_price=row.get("target_unit_price"),
            remark=row.get("remark"),
        ))

    # ── 6. CART:同事务硬删已提交的 cart_items ──
    if cart_item_ids_to_delete:
        await db.execute(
            delete(CartItem).where(CartItem.id.in_(cart_item_ids_to_delete))
        )

    # ── 7. 审计 + 单次 commit ──
    audit_action = AuditAction.PROXY_CREATE if source == RfqSource.OPERATOR_PROXY else AuditAction.SUBMIT
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

    return await _load_and_serialize(db, rfq.id, is_operator=is_operator)


# ── 列表 ──────────────────────────────────────────────

async def list_rfqs(
    db: AsyncSession, user: CurrentUser,
    *, page: int = 1, page_size: int = 20,
    status_filter: str | None = None,
    buyer_org_id_filter: int | None = None,
    mine: bool = False,
) -> dict:
    """列表,BUYER 限本组织,OPERATOR 全量。"""
    is_buyer = "BUYER" in user.roles
    is_operator = "OPERATOR" in user.roles

    q = select(Rfq).where(Rfq.deleted_at.is_(None))
    count_q = select(func.count()).select_from(Rfq).where(Rfq.deleted_at.is_(None))

    if is_buyer and not is_operator:
        org = await _resolve_active_buyer_org(db, user)
        q = q.where(Rfq.buyer_org_id == org.id)
        count_q = count_q.where(Rfq.buyer_org_id == org.id)
        if mine:
            q = q.where(Rfq.buyer_user_id == user.id)
            count_q = count_q.where(Rfq.buyer_user_id == user.id)

    if status_filter:
        q = q.where(Rfq.status == status_filter)
        count_q = count_q.where(Rfq.status == status_filter)

    if buyer_org_id_filter and is_operator:
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

    serialized = [_serialize_rfq(r, is_operator=is_operator) for r in rows]
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
    is_buyer = "BUYER" in user.roles
    is_operator = "OPERATOR" in user.roles

    rfq = await load_rfq(db, rfq_id, with_items=True)
    if not rfq:
        raise RfqNotFoundError()

    # scope 校验
    if is_buyer and not is_operator:
        org = await _resolve_active_buyer_org(db, user)
        if rfq.buyer_org_id != org.id:
            raise RfqNotFoundError()

    # 报价层叠
    quote_data = await quote_svc.load_quote_for_rfq_detail(
        db, rfq.id, is_operator=is_operator,
    )

    return _serialize_rfq(rfq, is_operator=is_operator, quote_data=quote_data)


# ── 撤销 ──────────────────────────────────────────────

async def cancel_rfq(
    db: AsyncSession, user: CurrentUser, rfq_id: int,
    cancel_reason: str | None = None,
    *, request: Request | None = None,
) -> RfqBuyerPublic | RfqOperatorView:
    """撤销守卫 + 幂等 + 行锁串行化。"""
    is_buyer = "BUYER" in user.roles
    is_operator = "OPERATOR" in user.roles

    # 行锁加载（含 scope 过滤,买方越权 → 404）
    rfq = await lock_rfq(db, rfq_id, user=user, with_items=True)

    # 幂等:已 CANCELLED → 返回当前,不改 reason/不写审计
    if rfq.status == RfqStatus.CANCELLED:
        return _serialize_rfq(rfq, is_operator=is_operator)

    # 买方硬禁:PROCESSING/QUOTED 后不可撤销
    if is_buyer and not is_operator:
        if rfq.status not in RfqStatus.BUYER_CANCELLABLE:
            raise RfqStateInvalidError(rfq.status)

    # 状态守卫
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

    return await _load_and_serialize(db, rfq.id, is_operator=is_operator)


# ── CART 行来源解析 ────────────────────────────────────

async def _resolve_cart_items(
    db: AsyncSession, user: CurrentUser, buyer_org_id: int,
    cart_item_ids: list[int] | None,
) -> tuple[list[dict], list[int]]:
    """从购物车取行,校验归属。返回 (item_rows, cart_item_ids_to_delete)。"""
    # 先找用户的车
    row = await db.execute(
        select(Cart).where(
            Cart.buyer_org_id == buyer_org_id,
            Cart.buyer_user_id == user.id,
        )
    )
    cart = row.scalar_one_or_none()
    if not cart:
        raise RfqNoValidItemsError()

    q = select(CartItem).where(CartItem.cart_id == cart.id)
    if cart_item_ids:
        q = q.where(CartItem.id.in_(cart_item_ids))

    cart_items = (await db.execute(q)).scalars().all()
    if not cart_items:
        raise RfqNoValidItemsError()

    # 校验选定的 cart_item_ids 确实属于本人车
    if cart_item_ids:
        found_ids = {ci.id for ci in cart_items}
        missing = set(cart_item_ids) - found_ids
        if missing:
            raise RfqNoValidItemsError()

    item_rows = []
    delete_ids = []
    for ci in cart_items:
        item_rows.append({
            "sku_id": ci.sku_id,
            "quantity": ci.quantity,
            "target_unit_price": None,
            "remark": None,
        })
        delete_ids.append(ci.id)

    return item_rows, delete_ids


# ── DIRECT 行来源解析 ──────────────────────────────────

async def _resolve_direct_items(
    db: AsyncSession, items: list,
) -> list[dict]:
    """DIRECT 来源行解析(快照在可购校验后填充)。"""
    return [
        {
            "sku_id": it.sku_id,
            "quantity": it.quantity,
            "target_unit_price": it.target_unit_price,
            "remark": it.remark,
        }
        for it in items
    ]


# ── 加载与序列化 ──────────────────────────────────────

async def _load_and_serialize(
    db: AsyncSession, rfq_id: int, *, is_operator: bool,
) -> RfqBuyerPublic | RfqOperatorView:
    """重新加载并序列化。"""
    rfq = await load_rfq(db, rfq_id, with_items=True)
    if not rfq:
        raise RfqNotFoundError()
    return _serialize_rfq(rfq, is_operator=is_operator)


def _serialize_item(item: RfqItem, locale: str = "zh") -> RfqItemPublic:
    """序列化行项目,按 locale 选快照语言。"""
    if locale == "en":
        name = item.product_name_snapshot_en or item.product_name_snapshot_zh
        spec = item.sku_spec_snapshot_en or item.sku_spec_snapshot_zh
    else:
        name = item.product_name_snapshot_zh or item.product_name_snapshot_en
        spec = item.sku_spec_snapshot_zh or item.sku_spec_snapshot_en

    return RfqItemPublic(
        id=item.id,
        sku_id=item.sku_id,
        product_name_snapshot=name,
        sku_spec_snapshot=spec,
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

    # 幂等:已 PROCESSING 且受理人是自己
    if rfq.status == RfqStatus.PROCESSING and rfq.operator_assignee_id == user.id:
        return _serialize_rfq(rfq, is_operator=True)

    # 冲突:已被其他运营受理
    if rfq.status == RfqStatus.PROCESSING and rfq.operator_assignee_id != user.id:
        raise RfqAlreadyClaimedError()

    # 状态守卫
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

    # 幂等：已 SUBMITTED → 直接返回
    if rfq.status == RfqStatus.SUBMITTED:
        return _serialize_rfq(rfq, is_operator=False)

    # 状态守卫
    if not RfqStatus.can_transition(rfq.status, RfqStatus.SUBMITTED):
        raise RfqStateInvalidError(rfq.status)

    # 行项非空守卫
    active_items = [it for it in rfq.items if getattr(it, "deleted_at", None) is None]
    if not active_items:
        raise RfqNoValidItemsError()

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

    # 幂等:已 DRAFT
    if rfq.status == RfqStatus.DRAFT:
        return _serialize_rfq(rfq, is_operator=False)

    # 状态守卫:仅 SUBMITTED 可撤回到 DRAFT
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


# ── 草稿态编辑行项数量 ──────────────────────────────────


async def update_rfq_item_qty(
    db: AsyncSession, user: CurrentUser,
    rfq_id: int, item_id: int, quantity: Decimal,
    *, request: Request | None = None,
) -> RfqBuyerPublic:
    """草稿态修改行项数量。仅 DRAFT 可操作。"""
    rfq = await lock_rfq(db, rfq_id, user=user, with_items=True)

    # 状态守卫:仅 DRAFT 可编辑
    if rfq.status != RfqStatus.DRAFT:
        raise RfqStateInvalidError(rfq.status)

    # 查找行项
    target_item = None
    for it in rfq.items:
        if it.id == item_id and getattr(it, "deleted_at", None) is None:
            target_item = it
            break
    if not target_item:
        raise RfqItemNotFoundError()

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

    return await _load_and_serialize(db, rfq.id, is_operator=False)
