"""购物车路由 — 买方侧。

所有写端点返回最新 CartPublic;GET 无车返回虚拟空车。
审计:写路径成功后 write_audit(commit=False) 同事务;GET 与校验错误不写审计。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.constants import AuditAction, AuditResourceType
from app.audit.logger import write_audit
from app.core.dependencies import CurrentUser
from app.core.exceptions import success
from app.db.session import get_db
from app.rbac.constants import Permissions
from app.rbac.guards import require_any_role, require_permission
from app.schemas.cart import CartItemAdd, CartItemUpdate
from app.services import cart as cart_svc

router = APIRouter(
    prefix="/cart",
    tags=["cart"],
    dependencies=[Depends(require_any_role("BUYER"))],
)


@router.get("", summary="查看购物车")
async def get_cart(
    current: CurrentUser = Depends(require_permission(Permissions.CART_READ)),
    db: AsyncSession = Depends(get_db),
):
    cart = await cart_svc.get_cart(db, current)
    return success(cart.model_dump())


@router.post("/items", summary="加购")
async def add_item(
    request: Request,
    data: CartItemAdd,
    current: CurrentUser = Depends(require_permission(Permissions.CART_WRITE)),
    db: AsyncSession = Depends(get_db),
):
    cart = await cart_svc.add_item(db, current, data.sku_id, data.quantity)
    await write_audit(
        db,
        resource_type=AuditResourceType.CART,
        action=AuditAction.ADD_ITEM,
        user_id=current.id,
        user_email=current.email,
        resource_id=data.sku_id,
        request=request,
        extra={"sku_id": data.sku_id, "quantity": str(data.quantity)},
        commit=False,
    )
    await db.commit()
    return success(cart.model_dump())


@router.patch("/items/{item_id}", summary="改量")
async def update_item(
    item_id: int,
    request: Request,
    data: CartItemUpdate,
    current: CurrentUser = Depends(require_permission(Permissions.CART_WRITE)),
    db: AsyncSession = Depends(get_db),
):
    cart = await cart_svc.update_item_qty(db, current, item_id, data.quantity)
    await write_audit(
        db,
        resource_type=AuditResourceType.CART,
        action=AuditAction.UPDATE_ITEM,
        user_id=current.id,
        user_email=current.email,
        resource_id=item_id,
        request=request,
        extra={"item_id": item_id, "quantity": str(data.quantity)},
        commit=False,
    )
    await db.commit()
    return success(cart.model_dump())


@router.delete("/items/{item_id}", summary="删行")
async def remove_item(
    item_id: int,
    request: Request,
    current: CurrentUser = Depends(require_permission(Permissions.CART_WRITE)),
    db: AsyncSession = Depends(get_db),
):
    cart = await cart_svc.remove_item(db, current, item_id)
    await write_audit(
        db,
        resource_type=AuditResourceType.CART,
        action=AuditAction.REMOVE_ITEM,
        user_id=current.id,
        user_email=current.email,
        resource_id=item_id,
        request=request,
        commit=False,
    )
    await db.commit()
    return success(cart.model_dump())


@router.delete("/items", summary="清空购物车")
async def clear_cart(
    request: Request,
    current: CurrentUser = Depends(require_permission(Permissions.CART_WRITE)),
    db: AsyncSession = Depends(get_db),
):
    cart = await cart_svc.clear_cart(db, current)
    await write_audit(
        db,
        resource_type=AuditResourceType.CART,
        action=AuditAction.CLEAR,
        user_id=current.id,
        user_email=current.email,
        request=request,
        commit=False,
    )
    await db.commit()
    return success(cart.model_dump())
