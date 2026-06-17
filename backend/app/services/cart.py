"""购物车 Service — 买方侧,单边模型。

并发安全:cart 与 cart_item 两处 insert-or-get 都走 SAVEPOINT 标准。
提交点唯一在本 service;route 不自行 commit。

SPU 化改造:cart_items 以 product_id + selected_variants + variant_fingerprint 为核心,
行身份 = (cart_id, product_id, variant_fingerprint) 三元组。
sku_id 保留但可空(历史兼容)。
"""
from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from fastapi import Request

from app.audit.constants import AuditAction, AuditResourceType
from app.audit.logger import write_audit
from app.core.config import settings
from app.core.dependencies import CurrentUser
from app.core.exceptions import (
    BuyerOrgRequiredError,
    CartItemNotFoundError,
    CartProductNotAvailableError,
    CartQuantityInvalidError,
)
from app.core.i18n import get_localized
from app.db.models.buyer_member import BuyerMember
from app.db.models.buyer_organization import BuyerOrgStatus, BuyerOrganization
from app.db.models.cart import Cart
from app.db.models.cart_item import CartItem
from app.db.models.product import Product, ProductStatus
from app.db.models.product_image import ImageType, ProductImage
from app.schemas.cart import CartItemPublic, CartPublic
from app.services._variant_utils import normalize_variants_to_en, variant_fingerprint


# ── SPU 可用性校验 ─────────────────────────────────────────


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


def _check_variant_available(
    product: Product, selected_variants: list[dict],
) -> tuple[bool, str | None]:
    """校验买方选的变体值在当前商品属性中仍然存在。

    若商品属性被运营删改，已入购物车的变体值可能失效。
    selected_variants 为空时视为对 SPU 整体询价，不校验。
    匹配时比对所有语言列（zh/en/sw），兼容数据质量不一致的情况。
    """
    if not selected_variants:
        return True, None
    valid_pairs: set[tuple[str, str]] = set()
    for a in (product.attrs or []):
        if a.selectable:
            for k, v in [
                (a.attr_key_en, a.attr_value_en),
                (a.attr_key_zh, a.attr_value_zh),
                (a.attr_key_sw, a.attr_value_sw),
            ]:
                if k and v:
                    valid_pairs.add((k, v))
    for sv in selected_variants:
        pair = (sv.get("attr_name", ""), sv.get("value", ""))
        if pair not in valid_pairs:
            return False, "VARIANT_UNAVAILABLE"
    return True, None


def _check_purchasable_product(product) -> tuple[bool, str | None]:
    """从已加载数据算可购状态,不增查询。"""
    if product is None:
        return False, "PRODUCT_DELETED"
    if product.deleted_at is not None:
        return False, "PRODUCT_DELETED"
    if product.status != ProductStatus.ACTIVE:
        return False, "PRODUCT_INACTIVE"
    return True, None


def _variants_to_display(variants: list[dict]) -> str | None:
    """将 selected_variants 拼为可读字符串。"""
    if not variants:
        return None
    return " / ".join(
        f"{sv.get('attr_name', '')}: {sv.get('value', '')}"
        for sv in variants
    )


# ── 买方组织前置校验 ────────────────────────────────────


async def resolve_active_buyer_org(
    db: AsyncSession, user: CurrentUser,
) -> BuyerOrganization:
    """经 buyer_members 解析当前用户买方组织;不存在或非 ACTIVE → 40504。"""
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


# ── 购物车 CRUD ─────────────────────────────────────────


async def get_cart(db: AsyncSession, user: CurrentUser) -> CartPublic:
    """只读,无车返回虚拟空车,不落库。"""
    org = await resolve_active_buyer_org(db, user)

    row = await db.execute(
        select(Cart)
        .where(Cart.buyer_org_id == org.id, Cart.buyer_user_id == user.id)
        .options(
            selectinload(Cart.items)
            .selectinload(CartItem.product)
            .selectinload(Product.images),
            selectinload(Cart.items)
            .selectinload(CartItem.product)
            .selectinload(Product.attrs),
        )
    )
    cart = row.scalar_one_or_none()
    if not cart:
        return CartPublic(id=None, items=[])

    return _serialize_cart(cart)


async def add_item(
    db: AsyncSession, user: CurrentUser,
    product_id: int,
    selected_variants: list[dict],
    quantity: Decimal,
    *, request: Request | None = None,
) -> CartPublic:
    """加购。行身份 = (cart_id, product_id, variant_fingerprint)。"""
    org = await resolve_active_buyer_org(db, user)

    product = await _get_viewable_product(db, product_id)
    if not product:
        raise CartProductNotAvailableError()

    if quantity <= 0:
        raise CartQuantityInvalidError()

    # 归一化为英文 + 指纹（后端唯一来源，跨语言稳定）
    normalized_variants = await normalize_variants_to_en(db, product_id, selected_variants)
    fingerprint = variant_fingerprint(normalized_variants)

    # ① get_or_create_cart (SAVEPOINT)
    cart = await _get_or_create_cart(db, org.id, user.id)

    # ② 按三元组精确定位已有行
    existing = await db.execute(
        select(CartItem).where(
            CartItem.cart_id == cart.id,
            CartItem.product_id == product_id,
            CartItem.variant_fingerprint == fingerprint,
        )
    )
    existing_item = existing.scalar_one_or_none()

    if existing_item:
        # 原子 UPDATE 累加到正确的变体行，防 lost update
        await db.execute(
            update(CartItem)
            .where(
                CartItem.cart_id == cart.id,
                CartItem.product_id == product_id,
                CartItem.variant_fingerprint == fingerprint,
            )
            .values(quantity=CartItem.quantity + quantity)
        )
    else:
        await _insert_or_merge_item(
            db, cart.id, product_id, normalized_variants, fingerprint, quantity,
        )

    await write_audit(
        db,
        resource_type=AuditResourceType.CART,
        action=AuditAction.ADD_ITEM,
        user_id=user.id,
        user_email=user.email,
        resource_id=product_id,
        request=request,
        extra={
            "product_id": product_id,
            "selected_variants": normalized_variants,
            "variant_fingerprint": fingerprint,
            "quantity": str(quantity),
        },
        commit=False,
    )

    # 买方行为埋点: ADD_TO_CART
    from app.services.buyer_event import EventType, record_event
    await record_event(
        db,
        buyer_org_id=org.id,
        user_id=user.id,
        event_type=EventType.ADD_TO_CART,
        resource_type="product",
        resource_id=product_id,
        extra={"quantity": float(quantity)},
        request=request,
    )

    await db.commit()
    return await _reload_cart(db, cart.id)


async def update_item_qty(
    db: AsyncSession, user: CurrentUser, item_id: int, quantity: Decimal,
    *, request: Request | None = None,
) -> CartPublic:
    """改量。"""
    if quantity <= 0:
        raise CartQuantityInvalidError()

    item = await _get_own_item_or_404(db, user, item_id)
    await db.execute(
        update(CartItem)
        .where(CartItem.id == item.id)
        .values(quantity=quantity)
    )
    # 审计与业务写同事务
    await write_audit(
        db,
        resource_type=AuditResourceType.CART,
        action=AuditAction.UPDATE_ITEM,
        user_id=user.id,
        user_email=user.email,
        resource_id=item_id,
        request=request,
        extra={"item_id": item_id, "quantity": str(quantity)},
        commit=False,
    )
    await db.commit()
    return await _reload_cart(db, item.cart_id)


async def remove_item(
    db: AsyncSession, user: CurrentUser, item_id: int,
    *, request: Request | None = None,
) -> CartPublic:
    """删行(硬删)。"""
    item = await _get_own_item_or_404(db, user, item_id)
    cart_id = item.cart_id
    await db.delete(item)
    # 审计与业务写同事务
    await write_audit(
        db,
        resource_type=AuditResourceType.CART,
        action=AuditAction.REMOVE_ITEM,
        user_id=user.id,
        user_email=user.email,
        resource_id=item_id,
        request=request,
        commit=False,
    )
    await db.commit()
    return await _reload_cart(db, cart_id)


async def clear_cart(
    db: AsyncSession, user: CurrentUser,
    *, request: Request | None = None,
) -> CartPublic:
    """清空(硬删全部行)。"""
    org = await resolve_active_buyer_org(db, user)

    row = await db.execute(
        select(Cart).where(
            Cart.buyer_org_id == org.id,
            Cart.buyer_user_id == user.id,
        )
    )
    cart = row.scalar_one_or_none()
    if not cart:
        return CartPublic(id=None, items=[])

    # 加载行项目后批量删除
    items_row = await db.execute(
        select(CartItem).where(CartItem.cart_id == cart.id)
    )
    for item in items_row.scalars().all():
        await db.delete(item)

    # 审计与业务写同事务
    await write_audit(
        db,
        resource_type=AuditResourceType.CART,
        action=AuditAction.CLEAR,
        user_id=user.id,
        user_email=user.email,
        request=request,
        commit=False,
    )
    await db.commit()
    return await _reload_cart(db, cart.id)


# ── 并发安全工具 ────────────────────────────────────────


async def _get_or_create_cart(
    db: AsyncSession, buyer_org_id: int, buyer_user_id: int,
) -> Cart:
    """SAVEPOINT 保护:并发首次加购不会撞唯一约束。"""
    # 先查
    row = await db.execute(
        select(Cart).where(
            Cart.buyer_org_id == buyer_org_id,
            Cart.buyer_user_id == buyer_user_id,
        )
    )
    cart = row.scalar_one_or_none()
    if cart:
        return cart

    # SAVEPOINT 内创建:成功显式 release,异常自动 rollback
    nested = await db.begin_nested()
    try:
        cart = Cart(buyer_org_id=buyer_org_id, buyer_user_id=buyer_user_id)
        db.add(cart)
        await db.flush()
    except IntegrityError:
        await nested.rollback()
        # 回查
        row = await db.execute(
            select(Cart).where(
                Cart.buyer_org_id == buyer_org_id,
                Cart.buyer_user_id == buyer_user_id,
            )
        )
        cart = row.scalar_one_or_none()
        if cart:
            return cart
        raise  # 非预期约束冲突,不误吞
    except BaseException:
        await nested.rollback()
        raise
    else:
        await nested.commit()
        return cart


async def _insert_or_merge_item(
    db: AsyncSession, cart_id: int,
    product_id: int, selected_variants: list[dict],
    fingerprint: str, quantity: Decimal,
) -> None:
    """SAVEPOINT 保护：并发同三元组加购，冲突时按三元组精确回查累加。"""
    nested = await db.begin_nested()
    try:
        item = CartItem(
            cart_id=cart_id,
            product_id=product_id,
            selected_variants=selected_variants,
            variant_fingerprint=fingerprint,
            quantity=quantity,
        )
        db.add(item)
        await db.flush()
    except IntegrityError:
        await nested.rollback()
        # 冲突 → 三元组唯一约束命中，回查精确行累加（不再错配到第一行）
        row = await db.execute(
            select(CartItem).where(
                CartItem.cart_id == cart_id,
                CartItem.product_id == product_id,
                CartItem.variant_fingerprint == fingerprint,
            )
        )
        existing = row.scalar_one_or_none()
        if existing:
            await db.execute(
                update(CartItem)
                .where(
                    CartItem.cart_id == cart_id,
                    CartItem.product_id == product_id,
                    CartItem.variant_fingerprint == fingerprint,
                )
                .values(quantity=CartItem.quantity + quantity)
            )
        else:
            raise  # 非预期约束冲突，不误吞
    except BaseException:
        await nested.rollback()
        raise
    else:
        await nested.commit()


# ── 归属校验 ────────────────────────────────────────────


async def _get_own_item_or_404(
    db: AsyncSession, user: CurrentUser, item_id: int,
) -> CartItem:
    """校验行项目属于当前用户活动车,不属于则 404(不暴露存在性)。"""
    org = await resolve_active_buyer_org(db, user)

    row = await db.execute(
        select(CartItem)
        .join(Cart, Cart.id == CartItem.cart_id)
        .where(
            CartItem.id == item_id,
            Cart.buyer_org_id == org.id,
            Cart.buyer_user_id == user.id,
        )
    )
    item = row.scalar_one_or_none()
    if not item:
        raise CartItemNotFoundError()
    return item


# ── 序列化 ──────────────────────────────────────────────


async def _reload_cart(db: AsyncSession, cart_id: int) -> CartPublic:
    """重新加载带关联的完整购物车。"""
    row = await db.execute(
        select(Cart)
        .where(Cart.id == cart_id)
        .options(
            selectinload(Cart.items)
            .selectinload(CartItem.product)
            .selectinload(Product.images),
            selectinload(Cart.items)
            .selectinload(CartItem.product)
            .selectinload(Product.attrs),
        )
    )
    cart = row.scalar_one_or_none()
    if not cart:
        return CartPublic(id=None, items=[])
    return _serialize_cart(cart)


def _serialize_cart(cart: Cart) -> CartPublic:
    """将 ORM Cart 转为 CartPublic DTO。"""
    items = []
    for ci in cart.items:
        product = ci.product

        is_purchasable, unavailable_reason = _check_purchasable_product(product)

        # 变体失效校验（仅在商品本身可购时再查）
        if is_purchasable and ci.selected_variants:
            ok, reason = _check_variant_available(product, ci.selected_variants)
            if not ok:
                is_purchasable = False
                unavailable_reason = reason

        main_image = _resolve_main_image_from_product(product)

        variant_display = _variants_to_display(ci.selected_variants or [])

        items.append(CartItemPublic(
            item_id=ci.id,
            product_id=ci.product_id,
            sku_id=ci.sku_id,
            selected_variants=ci.selected_variants or [],
            quantity=ci.quantity,
            product_name=get_localized(product, "name") if product else None,
            variant_display=variant_display,
            description=get_localized(product, "description") if product else None,
            brand=get_localized(product, "brand") if product else None,
            origin=get_localized(product, "origin") if product else None,
            unit=product.unit if product else None,
            moq=product.moq if product else None,
            supply_mode=product.supply_mode if product else None,
            certifications=product.certifications or [] if product else [],
            lead_time_min=product.lead_time_min if product else None,
            lead_time_max=product.lead_time_max if product else None,
            category_name=product.category_code if product else None,
            is_purchasable=is_purchasable,
            unavailable_reason=unavailable_reason,
            main_image=main_image,
        ))

    return CartPublic(id=cart.id, items=items)


def _resolve_main_image_from_product(product) -> str | None:
    """Product 主图 → None。"""
    if product is None or not product.images:
        return None

    base = settings.IMAGE_BASE_URL
    prod_images = [i for i in product.images if not getattr(i, "deleted_at", None)]
    if not prod_images:
        return None

    main = next((i for i in prod_images if i.image_type == ImageType.MAIN), None)
    img = main or sorted(prod_images, key=lambda i: i.sort_order)[0]
    return f"{base}/{img.image_key}"
