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
from app.core.locale import get_current_locale
from app.db.models.product import ProductStatus
from app.db.models.product_image import ImageType
from app.db.session import get_db
from app.schemas.product import (
    AttrGroup,
    AttrItem,
    AttrValue,
    ProductImageSchema,
    ProductPublic,
    ProductPublicDetail,
)
from app.services import product as product_svc

router = APIRouter(prefix="/products", tags=["products"])


def _build_attribute_groups(attrs, images, locale: str) -> list[dict]:
    """SPU 属性按 attr_group → attr_key 两层聚合,色板值关联 swatch 图。

    聚合逻辑:同 attr_key 的多行合成一个 AttrItem.values(N 行→多值)。
    色板:value_type=image 时,从 images 按 spec_value 匹配取图 URL 填 swatch_image。
    """
    # 按 spec_value 索引图片,用于色板匹配
    spec_image_map: dict[str, str] = {}
    for img in images:
        if img.spec_value:
            spec_image_map[img.spec_value] = f"{settings.IMAGE_BASE_URL}/{img.image_key}"

    # 两层聚合:group → key → values
    from collections import OrderedDict
    group_map: OrderedDict[str, OrderedDict[str, dict]] = OrderedDict()

    for attr in sorted(attrs, key=lambda a: (a.sort_order or 0)):
        group_name = attr.attr_group or "General"
        # 按 locale 选 key/value
        key = _localized_attr(attr, "attr_key", locale)
        value = _localized_attr(attr, "attr_value", locale)

        if group_name not in group_map:
            group_map[group_name] = OrderedDict()
        key_map = group_map[group_name]

        if key not in key_map:
            key_map[key] = {"unit": attr.attr_unit, "selectable": False, "values": []}
        # 同 key 多行 selectable 一致,取其一(有 True 即 True)
        if getattr(attr, "selectable", False):
            key_map[key]["selectable"] = True

        swatch = None
        if attr.value_type == "image" and attr.spec_value:
            swatch = spec_image_map.get(attr.spec_value)

        key_map[key]["values"].append(
            AttrValue(value=value, value_type=attr.value_type or "text", swatch_image=swatch).model_dump()
        )

    # 组装最终结构
    result = []
    for group_name, key_map in group_map.items():
        items = []
        for key, info in key_map.items():
            items.append(AttrItem(key=key, unit=info["unit"], selectable=info["selectable"], values=info["values"]).model_dump())
        result.append(AttrGroup(group=group_name, items=items).model_dump())
    return result


def _localized_attr(attr, field: str, locale: str) -> str:
    """属性字段 i18n:统一走 get_localized,列名已规范化为 {field}_{locale}。"""
    from app.core.i18n import get_localized
    return get_localized(attr, field)


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


def _to_public(p) -> dict:
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
        unit=p.unit,
        moq=p.moq,
        moq_unit=p.moq_unit,
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

    # SPU 级属性(sku_id IS NULL),按 attr_group → attr_key 聚合
    spu_attrs = [a for a in p.attrs if a.sku_id is None]
    alive_imgs = _alive_images(p.images)
    locale = get_current_locale()

    # 图片按 type 分:MAIN/GALLERY → 主图区;DETAIL → 详情图
    all_images = [_img_to_dict(img) for img in alive_imgs]

    data = ProductPublicDetail(
        id=p.id,
        spu_code=p.spu_code,
        name=get_localized(p, "name"),
        description=get_localized(p, "description"),
        detail_description=get_localized(p, "detail_description") or None,
        category_code=p.category_code,
        origin=get_localized(p, "origin"),
        brand=get_localized(p, "brand") or None,
        hs_code=p.hs_code,
        certifications=p.certifications,
        selling_points=get_localized(p, "selling_points"),
        is_featured=p.is_featured,
        unit=p.unit,
        moq=p.moq,
        moq_unit=p.moq_unit,
        attribute_groups=_build_attribute_groups(spu_attrs, alive_imgs, locale),
        images=all_images,
    ).model_dump()
    return success(data)
