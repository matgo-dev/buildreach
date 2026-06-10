"""购物车 Service — 买方侧,单边模型。

并发安全:cart 与 cart_item 两处 insert-or-get 都走 SAVEPOINT 标准。
提交点唯一在本 service;route 不自行 commit。
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
    CartQuantityInvalidError,
    CartSkuNotPurchasableError,
)
from app.core.i18n import get_localized
from app.db.models.buyer_member import BuyerMember
from app.db.models.buyer_organization import BuyerOrgStatus, BuyerOrganization
from app.db.models.cart import Cart
from app.db.models.cart_item import CartItem
from app.db.models.product import Product, ProductStatus
from app.db.models.product_image import ImageType, ProductImage
from app.db.models.product_sku import ProductSku, SkuStatus
from app.schemas.cart import CartItemPublic, CartPublic
from app.services import product as product_svc


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
            selectinload(Cart.items).selectinload(CartItem.sku).selectinload(ProductSku.product).selectinload(Product.images),
            selectinload(Cart.items).selectinload(CartItem.sku).selectinload(ProductSku.images),
        )
    )
    cart = row.scalar_one_or_none()
    if not cart:
        return CartPublic(id=None, items=[])

    return _serialize_cart(cart)


async def add_item(
    db: AsyncSession, user: CurrentUser, sku_id: int, quantity: Decimal,
    *, request: Request | None = None,
) -> CartPublic:
    """加购。并发安全:cart + cart_item 两处 SAVEPOINT 保护。"""
    org = await resolve_active_buyer_org(db, user)

    # 可购校验(委托商品域,单一事实源)
    sku = await product_svc.get_purchasable_sku(db, sku_id)
    if not sku:
        raise CartSkuNotPurchasableError()

    if quantity <= 0:
        raise CartQuantityInvalidError()

    # ① get_or_create_cart (SAVEPOINT)
    cart = await _get_or_create_cart(db, org.id, user.id)

    # ② 检查同 SKU 是否已在车中
    existing = await db.execute(
        select(CartItem).where(
            CartItem.cart_id == cart.id,
            CartItem.sku_id == sku_id,
        )
    )
    existing_item = existing.scalar_one_or_none()

    if existing_item:
        # 原子 UPDATE 累加,防 lost update
        await db.execute(
            update(CartItem)
            .where(CartItem.cart_id == cart.id, CartItem.sku_id == sku_id)
            .values(quantity=CartItem.quantity + quantity)
        )
    else:
        # 新行 insert-or-get (SAVEPOINT)
        await _insert_or_merge_item(db, cart.id, sku_id, quantity)

    # 审计与业务写同事务
    await write_audit(
        db,
        resource_type=AuditResourceType.CART,
        action=AuditAction.ADD_ITEM,
        user_id=user.id,
        user_email=user.email,
        resource_id=sku_id,
        request=request,
        extra={"sku_id": sku_id, "quantity": str(quantity)},
        commit=False,
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
    db: AsyncSession, cart_id: int, sku_id: int, quantity: Decimal,
) -> None:
    """SAVEPOINT 保护:并发同 SKU 加购,冲突时原子 UPDATE 累加。"""
    nested = await db.begin_nested()
    try:
        item = CartItem(cart_id=cart_id, sku_id=sku_id, quantity=quantity)
        db.add(item)
        await db.flush()
    except IntegrityError:
        await nested.rollback()
        # 冲突 → 回查确认是 (cart_id, sku_id) 唯一约束
        row = await db.execute(
            select(CartItem).where(
                CartItem.cart_id == cart_id,
                CartItem.sku_id == sku_id,
            )
        )
        existing = row.scalar_one_or_none()
        if existing:
            # 原子 UPDATE 累加
            await db.execute(
                update(CartItem)
                .where(CartItem.cart_id == cart_id, CartItem.sku_id == sku_id)
                .values(quantity=CartItem.quantity + quantity)
            )
        else:
            raise  # 非预期约束冲突,不误吞
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
            selectinload(Cart.items).selectinload(CartItem.sku).selectinload(ProductSku.product).selectinload(Product.images),
            selectinload(Cart.items).selectinload(CartItem.sku).selectinload(ProductSku.images),
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
        sku = ci.sku
        if sku is None:
            continue

        product = sku.product

        # 可购状态
        is_purchasable, unavailable_reason = _check_purchasable(sku, product)

        # 主图:SKU 主图 → Product 主图 → None
        main_image = _resolve_main_image(sku, product)

        items.append(CartItemPublic(
            item_id=ci.id,
            sku_id=ci.sku_id,
            product_id=sku.product_id,
            quantity=ci.quantity,
            sku_code=sku.sku_code,
            sku_name=get_localized(sku, "name"),
            product_name=get_localized(product, "name") if product else None,
            manufacturer_model=sku.manufacturer_model,
            color=get_localized(sku, "color"),
            material=get_localized(sku, "material"),
            unit=product.unit if product else None,
            moq=sku.moq,
            is_purchasable=is_purchasable,
            unavailable_reason=unavailable_reason,
            main_image=main_image,
        ))

    return CartPublic(id=cart.id, items=items)


def _check_purchasable(sku: ProductSku, product) -> tuple[bool, str | None]:
    """从已加载数据算可购状态,不增查询。"""
    if sku.deleted_at is not None:
        return False, "SKU_DELETED"
    if sku.status != SkuStatus.ACTIVE:
        return False, "SKU_INACTIVE"
    if product is None:
        return False, "PRODUCT_DELETED"
    if product.deleted_at is not None:
        return False, "PRODUCT_DELETED"
    if product.status != ProductStatus.ACTIVE:
        return False, "PRODUCT_INACTIVE"
    return True, None


def _resolve_main_image(sku: ProductSku, product) -> str | None:
    """SKU 主图 → Product 主图 → None。"""
    base = settings.IMAGE_BASE_URL

    # SKU 级图片
    sku_images = [i for i in (sku.images or []) if not getattr(i, "deleted_at", None)]
    if sku_images:
        main = next((i for i in sku_images if i.image_type == ImageType.MAIN), None)
        img = main or sorted(sku_images, key=lambda i: i.sort_order)[0]
        return f"{base}/{img.image_key}"

    # Product 级图片
    if product and product.images:
        prod_images = [i for i in product.images if not getattr(i, "deleted_at", None)]
        if prod_images:
            main = next((i for i in prod_images if i.image_type == ImageType.MAIN), None)
            img = main or sorted(prod_images, key=lambda i: i.sort_order)[0]
            return f"{base}/{img.image_key}"

    return None
