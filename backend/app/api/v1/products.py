"""公开商品 API（无需登录，买方浏览用）— v2 i18n 分列模式。

断层隔离：响应体不含任何供应商字段。
多语言输出经 get_localized 按请求 locale 取值。
"""
from __future__ import annotations

import math

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import NotFoundError, success
from app.core.i18n import get_localized
from app.db.models.product import ProductStatus
from app.db.models.product_image import ImageType
from app.db.models.product_sku import SkuStatus
from app.db.session import get_db
from app.schemas.product import (
    PriceTierSchema,
    ProductAttrSchema,
    ProductImageSchema,
    ProductPublic,
    ProductPublicDetail,
    SkuPublic,
)
from app.services import product as product_svc

router = APIRouter(prefix="/products", tags=["products"])


def _img_to_dict(img) -> dict:
    d = ProductImageSchema.model_validate(img).model_dump()
    d["full_url"] = f"{settings.IMAGE_BASE_URL}/{img.image_key}"
    return d


def _get_main_image_url(p) -> str | None:
    if not p.images:
        return None
    main = next((i for i in p.images if i.image_type == ImageType.MAIN), None)
    if not main:
        main = sorted(p.images, key=lambda i: i.sort_order)[0]
    return f"{settings.IMAGE_BASE_URL}/{main.image_key}"


def _default_sku(p):
    if not p.skus:
        return None
    default = next((s for s in p.skus if s.is_default), None)
    if not default:
        active = [s for s in p.skus if s.status == SkuStatus.ACTIVE]
        default = active[0] if active else p.skus[0]
    return default


def _to_public(p) -> dict:
    ds = _default_sku(p)
    active_count = sum(1 for s in p.skus if s.status == SkuStatus.ACTIVE)
    return ProductPublic(
        id=p.id,
        spu_code=p.spu_code,
        name=get_localized(p, "name"),
        category_code=p.category_code,
        origin=get_localized(p, "origin"),
        brand=get_localized(p, "brand") or None,
        certifications=p.certifications,
        is_featured=p.is_featured,
        main_image=_get_main_image_url(p),
        price_min=ds.price_min if ds else None,
        price_max=ds.price_max if ds else None,
        currency=ds.currency if ds else None,
        sku_count=active_count,
    ).model_dump()


def _sku_to_public(sku) -> dict:
    sku_images = [_img_to_dict(img) for img in (sku.images or [])]
    tiers = [PriceTierSchema.model_validate(t).model_dump() for t in (sku.price_tiers or [])]
    return SkuPublic(
        id=sku.id,
        sku_code=sku.sku_code,
        name=get_localized(sku, "name") or None,
        color=get_localized(sku, "color") or None,
        material=get_localized(sku, "material") or None,
        manufacturer_model=sku.manufacturer_model,
        price_min=sku.price_min,
        price_max=sku.price_max,
        currency=sku.currency,
        unit=sku.unit,
        moq=sku.moq,
        lead_time_min=sku.lead_time_min,
        lead_time_max=sku.lead_time_max,
        is_default=sku.is_default,
        status=sku.status,
        price_tiers=tiers,
        images=sku_images,
    ).model_dump()


@router.get("", summary="公开商品列表")
async def list_products(
    category_code: str | None = Query(None),
    featured: bool | None = Query(None),
    keyword: str | None = Query(None),
    sort: str = Query("newest"),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    items, total = await product_svc.list_products_public(
        db, category_code=category_code,
        featured=featured, keyword=keyword,
        sort=sort, page=page, size=size,
    )
    return success({
        "items": [_to_public(p) for p in items],
        "total": total,
        "page": page,
        "size": size,
        "pages": math.ceil(total / size) if size else 0,
    })


@router.get("/{product_id}", summary="公开商品详情")
async def get_product(
    product_id: int,
    db: AsyncSession = Depends(get_db),
):
    p = await product_svc.get_product(db, product_id)
    if p.status != ProductStatus.ACTIVE:
        raise NotFoundError("Product not found")

    active_skus = [s for s in p.skus if s.status == SkuStatus.ACTIVE]

    data = ProductPublicDetail(
        id=p.id,
        spu_code=p.spu_code,
        name=get_localized(p, "name"),
        description=get_localized(p, "description"),
        category_code=p.category_code,
        origin=get_localized(p, "origin"),
        brand=get_localized(p, "brand") or None,
        hs_code=p.hs_code,
        certifications=p.certifications,
        selling_points=get_localized(p, "selling_points"),
        is_featured=p.is_featured,
        skus=[_sku_to_public(s) for s in active_skus],
        images=[_img_to_dict(img) for img in p.images],
        attributes=[ProductAttrSchema.model_validate(attr) for attr in p.attrs],
    ).model_dump()
    return success(data)
