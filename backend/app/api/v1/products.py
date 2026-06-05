"""公开商品 API（无需登录，买方浏览用）。"""
from __future__ import annotations

import math

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import success
from app.core.i18n import get_localized
from app.db.session import get_db
from app.schemas.product import ProductPublic, ProductPublicDetail, ProductAttrSchema, ProductImageSchema
from app.services import product as product_svc

router = APIRouter(prefix="/products", tags=["products"])


def _img_to_dict(img) -> dict:
    d = ProductImageSchema.model_validate(img).model_dump()
    d["full_url"] = f"{settings.IMAGE_BASE_URL}/{img.image_key}"
    return d


def _get_main_image_url(p) -> str | None:
    """取 MAIN 类型图片的 full_url，没有则取 sort_order 最小的。"""
    if not p.images:
        return None
    from app.db.models.product_image import ImageType
    main = next((i for i in p.images if i.image_type == ImageType.MAIN), None)
    if not main:
        main = sorted(p.images, key=lambda i: i.sort_order)[0]
    return f"{settings.IMAGE_BASE_URL}/{main.image_key}"


def _to_public(p) -> dict:
    main_image = _get_main_image_url(p)
    return ProductPublic(
        id=p.id,
        sku_code=p.sku_code,
        name=get_localized(p, "name"),
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
    ).model_dump()


@router.get("", summary="公开商品列表")
async def list_products(
    category_code: str | None = Query(None),
    price_min: float | None = Query(None),
    price_max: float | None = Query(None),
    featured: bool | None = Query(None),
    keyword: str | None = Query(None),
    sort: str = Query("newest"),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    items, total = await product_svc.list_products_public(
        db, category_code=category_code, price_min=price_min,
        price_max=price_max, featured=featured, keyword=keyword,
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
    from app.db.models.product import ProductStatus
    if p.status != ProductStatus.ACTIVE:
        from app.core.exceptions import NotFoundError
        raise NotFoundError("Product not found")

    main_image = _get_main_image_url(p)

    data = ProductPublicDetail(
        id=p.id,
        sku_code=p.sku_code,
        name=get_localized(p, "name"),
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
        description=get_localized(p, "description"),
        hs_code=p.hs_code,
        images=[_img_to_dict(img) for img in p.images],
        attributes=[ProductAttrSchema.model_validate(attr) for attr in p.attrs],
    ).model_dump()
    return success(data)
