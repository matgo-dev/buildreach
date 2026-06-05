"""运营商品管理 API（需 OPERATOR 角色 + 对应权限）。"""
from __future__ import annotations

import math
from typing import List

from fastapi import APIRouter, Depends, File, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import CurrentUser
from app.core.exceptions import success
from app.core.i18n import get_localized
from app.db.session import get_db
from app.rbac.constants import Permissions
from app.rbac.guards import require_permission
from app.schemas.product import (
    AttrTemplateSchema,
    ProductAttrSchema,
    ProductCreate,
    ProductImageSchema,
    ProductOperator,
    ProductOperatorDetail,
    ProductStatusUpdate,
    ProductSupplierCreate,
    ProductSupplierUpdate,
    ProductUpdate,
)
from app.services import product as product_svc

router = APIRouter(prefix="/operator/products", tags=["operator-products"])


def _to_operator(p) -> dict:
    main_image = None
    if hasattr(p, "images") and p.images:
        sorted_imgs = sorted(p.images, key=lambda i: i.sort_order)
        main_image = sorted_imgs[0].url if sorted_imgs else None
    supplier_count = len(p.supplier_relations) if hasattr(p, "supplier_relations") and p.supplier_relations else 0
    return ProductOperator(
        id=p.id,
        sku_code=p.sku_code,
        name=get_localized(p, "name"),
        name_i18n=p.name_i18n,
        category_code=p.category_code,
        price_min=p.price_min,
        price_max=p.price_max,
        currency=p.currency,
        unit=p.unit,
        moq=p.moq,
        lead_time_days=p.lead_time_days,
        origin=get_localized(p, "origin"),
        brand=get_localized(p, "brand") or None,
        certifications=p.certifications,
        is_featured=p.is_featured,
        main_image=main_image,
        status=p.status,
        supplier_count=supplier_count,
        created_at=p.created_at,
        updated_at=p.updated_at,
    ).model_dump()


# ── 商品 CRUD ──────────────────────────────────────────────

@router.get("", summary="运营商品列表")
async def list_products(
    category_code: str | None = Query(None),
    status: str | None = Query(None),
    keyword: str | None = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=50),
    current: CurrentUser = Depends(require_permission(Permissions.PRODUCT_READ)),
    db: AsyncSession = Depends(get_db),
):
    items, total = await product_svc.list_products_operator(
        db, category_code=category_code, status=status,
        keyword=keyword, page=page, size=size,
    )
    return success({
        "items": [_to_operator(p) for p in items],
        "total": total,
        "page": page,
        "size": size,
        "pages": math.ceil(total / size) if size else 0,
    })


@router.post("", summary="创建商品")
async def create_product(
    data: ProductCreate,
    current: CurrentUser = Depends(require_permission(Permissions.PRODUCT_WRITE)),
    db: AsyncSession = Depends(get_db),
):
    product = await product_svc.create_product(db, data, current.id)
    return success({"id": product.id, "sku_code": product.sku_code})


@router.put("/{product_id}", summary="编辑商品")
async def update_product(
    product_id: int,
    data: ProductUpdate,
    current: CurrentUser = Depends(require_permission(Permissions.PRODUCT_WRITE)),
    db: AsyncSession = Depends(get_db),
):
    product = await product_svc.update_product(db, product_id, data)
    return success({"id": product.id})


@router.patch("/{product_id}/status", summary="上架/下架")
async def update_status(
    product_id: int,
    data: ProductStatusUpdate,
    current: CurrentUser = Depends(require_permission(Permissions.PRODUCT_APPROVE)),
    db: AsyncSession = Depends(get_db),
):
    product = await product_svc.update_product_status(db, product_id, data.status)
    return success({"id": product.id, "status": product.status})


@router.delete("/{product_id}", summary="删除草稿商品")
async def delete_product(
    product_id: int,
    current: CurrentUser = Depends(require_permission(Permissions.PRODUCT_WRITE)),
    db: AsyncSession = Depends(get_db),
):
    await product_svc.delete_product(db, product_id)
    return success()


@router.get("/{product_id}", summary="运营商品详情")
async def get_product(
    product_id: int,
    current: CurrentUser = Depends(require_permission(Permissions.PRODUCT_READ)),
    db: AsyncSession = Depends(get_db),
):
    p = await product_svc.get_product(db, product_id)
    main_image = None
    if p.images:
        sorted_imgs = sorted(p.images, key=lambda i: i.sort_order)
        main_image = sorted_imgs[0].url if sorted_imgs else None

    suppliers = await product_svc.list_product_suppliers(db, product_id)

    data = ProductOperatorDetail(
        id=p.id,
        sku_code=p.sku_code,
        name=get_localized(p, "name"),
        name_i18n=p.name_i18n,
        category_code=p.category_code,
        price_min=p.price_min,
        price_max=p.price_max,
        currency=p.currency,
        unit=p.unit,
        moq=p.moq,
        lead_time_days=p.lead_time_days,
        origin=get_localized(p, "origin"),
        origin_i18n=p.origin_i18n,
        brand=get_localized(p, "brand") or None,
        brand_i18n=p.brand_i18n,
        certifications=p.certifications,
        is_featured=p.is_featured,
        main_image=main_image,
        description=get_localized(p, "description"),
        description_i18n=p.description_i18n,
        hs_code=p.hs_code,
        images=[ProductImageSchema.model_validate(img) for img in p.images],
        attributes=[ProductAttrSchema.model_validate(attr) for attr in p.attrs],
        status=p.status,
        suppliers=suppliers,
        created_at=p.created_at,
        updated_at=p.updated_at,
    ).model_dump()
    return success(data)


# ── 图片 ──────────────────────────────────────────────────

@router.post("/{product_id}/images", summary="上传商品图片")
async def upload_image(
    product_id: int,
    file: UploadFile = File(...),
    current: CurrentUser = Depends(require_permission(Permissions.PRODUCT_WRITE)),
    db: AsyncSession = Depends(get_db),
):
    img = await product_svc.add_product_image(db, product_id, file)
    return success(ProductImageSchema.model_validate(img).model_dump())


@router.delete("/{product_id}/images/{image_id}", summary="删除商品图片")
async def delete_image(
    product_id: int,
    image_id: int,
    current: CurrentUser = Depends(require_permission(Permissions.PRODUCT_WRITE)),
    db: AsyncSession = Depends(get_db),
):
    await product_svc.delete_product_image(db, image_id)
    return success()


@router.patch("/{product_id}/images/sort", summary="图片排序")
async def sort_images(
    product_id: int,
    image_ids: List[int],
    current: CurrentUser = Depends(require_permission(Permissions.PRODUCT_WRITE)),
    db: AsyncSession = Depends(get_db),
):
    await product_svc.update_image_sort(db, product_id, image_ids)
    return success()


# ── 供货关系 ──────────────────────────────────────────────

@router.get("/{product_id}/suppliers", summary="商品供货关系列表")
async def list_suppliers(
    product_id: int,
    current: CurrentUser = Depends(require_permission(Permissions.PRODUCT_READ)),
    db: AsyncSession = Depends(get_db),
):
    items = await product_svc.list_product_suppliers(db, product_id)
    return success(items)


@router.post("/{product_id}/suppliers", summary="绑定供应商")
async def add_supplier(
    product_id: int,
    data: ProductSupplierCreate,
    current: CurrentUser = Depends(require_permission(Permissions.PRODUCT_WRITE)),
    db: AsyncSession = Depends(get_db),
):
    ps = await product_svc.add_product_supplier(db, product_id, data)
    return success({"id": ps.id})


@router.put("/{product_id}/suppliers/{ps_id}", summary="编辑供货关系")
async def update_supplier(
    product_id: int,
    ps_id: int,
    data: ProductSupplierUpdate,
    current: CurrentUser = Depends(require_permission(Permissions.PRODUCT_WRITE)),
    db: AsyncSession = Depends(get_db),
):
    ps = await product_svc.update_product_supplier(db, ps_id, data)
    return success({"id": ps.id})


@router.delete("/{product_id}/suppliers/{ps_id}", summary="移除供货关系")
async def remove_supplier(
    product_id: int,
    ps_id: int,
    current: CurrentUser = Depends(require_permission(Permissions.PRODUCT_WRITE)),
    db: AsyncSession = Depends(get_db),
):
    await product_svc.remove_product_supplier(db, ps_id)
    return success()
