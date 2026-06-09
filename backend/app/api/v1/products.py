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
from app.services.product import spu_price_range, default_sku_fields

router = APIRouter(prefix="/products", tags=["products"])


def _enrich_attrs(attrs, template_map: dict) -> list[dict]:
    """属性序列化：attr_unit/sort_order/display_name 从模板取。"""
    result = []
    for attr in attrs:
        tpl = template_map.get(attr.attr_key)
        result.append({
            "attr_key": attr.attr_key,
            "attr_value": attr.attr_value,
            "attr_unit": tpl.attr_unit if tpl else attr.attr_unit,
            "sort_order": tpl.sort_order if tpl else attr.sort_order,
            "sku_id": attr.sku_id,
            "display_name": tpl.display_name if tpl else attr.attr_key,
        })
    result.sort(key=lambda x: x["sort_order"])
    return result


def _img_to_dict(img) -> dict:
    d = ProductImageSchema.model_validate(img).model_dump()
    d["full_url"] = f"{settings.IMAGE_BASE_URL}/{img.image_key}"
    return d


def _alive_images(images):
    """过滤软删图片"""
    return [i for i in images if not getattr(i, "deleted_at", None)]


def _get_main_image_url(p) -> str | None:
    imgs = _alive_images(p.images) if p.images else []
    if not imgs:
        return None
    main = next((i for i in imgs if i.image_type == ImageType.MAIN), None)
    if not main:
        main = sorted(imgs, key=lambda i: i.sort_order)[0]
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
    prices = spu_price_range(p)
    ds_fields = default_sku_fields(p)
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
        price_min=prices["price_min"],
        price_max=prices["price_max"],
        currency=prices["currency"],
        moq=ds_fields["moq"],
        unit=ds_fields["unit"],
        lead_time_min=ds_fields["lead_time_min"],
        lead_time_max=ds_fields["lead_time_max"],
        sku_count=active_count,
    ).model_dump()


def _sku_to_public(sku) -> dict:
    sku_images = [_img_to_dict(img) for img in _alive_images(sku.images or [])]
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

    tpl_map = {t.attr_key: t for t in await product_svc.get_attr_templates(db, p.category_code)}

    active_skus = [s for s in p.skus if s.status == SkuStatus.ACTIVE]
    spu_attrs = [a for a in p.attrs if a.sku_id is None]

    # SKU 级属性按 sku_id 分组
    sku_attr_groups: dict[int, list] = {}
    for a in p.attrs:
        if a.sku_id is not None:
            sku_attr_groups.setdefault(a.sku_id, []).append(a)

    skus_data = []
    for s in active_skus:
        d = _sku_to_public(s)
        d["attributes"] = _enrich_attrs(sku_attr_groups.get(s.id, []), tpl_map)
        skus_data.append(d)

    prices = spu_price_range(p)
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
        unit=p.unit,
        currency=p.currency,
        price_min=prices["price_min"],
        price_max=prices["price_max"],
        skus=skus_data,
        images=[_img_to_dict(img) for img in _alive_images(p.images)],
        attributes=_enrich_attrs(spu_attrs, tpl_map),
    ).model_dump()
    return success(data)
