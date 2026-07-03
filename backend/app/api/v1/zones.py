"""央企/客户专区(Zone)买家侧只读 API — 类目导航 + 商品列表 + 商品详情。

访问门槛:`require_zone_access` 依赖 —— 当前买方须持有该 zone 的 ZoneGrant(经其
buyer_org),且该 zone 必须 ACTIVE;不满足一律 403,不区分"zone 不存在"/"未授权"/
"zone 已停用",避免存在性泄露。查询模式与 `GET /me`(auth.py)的 zones 字段一致:
Zone ⋈ ZoneGrant ⋈ BuyerMember。

商品列表/详情尽量复用现有公开商品序列化(app.api.v1.products),使前端
components/mall/* 可直接复用:
- 列表卡片:复用 `_to_public()` + `_batch_main_images()`,输出与
  `GET /products`(list_products_public)一致的 items/total/page/size/pages 信封。
  但底层查询不能复用 `list_products_public()` 本体 —— 它按 `public_visible()`
  过滤,会把 ZONE_ONLY 商品排除掉;这里改为按 zone_products 白名单查询。
- 详情:复用 `ProductPublicDetail` 的字段集合(`_build_attribute_groups` /
  `_alive_images` / `_img_to_dict`),但公开详情本身是"广告牌模式"(去价去 SKU),
  专区买家需要真实换购 SKU 变体,因此在其基础上追加一个基于 `SkuPublic` 的最小
  wrapper(`_build_sku_public`),补上 SKU 列表及其变体属性 —— 这是本任务唯一
  做不到"零适配复用"的地方。
"""
from __future__ import annotations

import math

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.products import (
    _alive_images,
    _build_attribute_groups,
    _img_to_dict,
    _localized_attr,
    _to_public,
)
from app.core.exceptions import NotFoundError, PermissionDeniedError, success
from app.core.i18n import get_localized
from app.core.locale import get_current_locale
from app.core.dependencies import CurrentUser, get_current_user
from app.db.models.buyer_member import BuyerMember
from app.db.models.product import Product, ProductStatus
from app.db.models.zone import Zone, ZoneCategory, ZoneGrant, ZoneProduct
from app.db.session import get_db
from app.schemas.product import ProductAttrSchema, ProductPublicDetail, SkuPublic
from app.services import product as product_svc

router = APIRouter(prefix="/zones", tags=["zones"])


async def require_zone_access(
    zone_code: str,
    current: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Zone:
    """解析当前买方对 `zone_code` 的访问权限,返回 Zone 行。

    查询模式与 `GET /me`(auth.py)一致:Zone ⋈ ZoneGrant ⋈ BuyerMember,
    仅 ACTIVE 专区。zone 不存在 / 未授权 / zone 已停用,统一 403,不泄露存在性。
    """
    row = await db.execute(
        select(Zone)
        .join(ZoneGrant, ZoneGrant.zone_id == Zone.id)
        .join(BuyerMember, BuyerMember.buyer_org_id == ZoneGrant.buyer_org_id)
        .where(
            BuyerMember.user_id == current.id,
            Zone.code == zone_code,
            Zone.status == "ACTIVE",
        )
    )
    zone = row.scalar_one_or_none()
    if zone is None:
        raise PermissionDeniedError("Zone access denied")
    return zone


def _zone_category_to_public(zc: ZoneCategory) -> dict:
    return {
        "id": zc.id,
        "code": zc.code,
        "name": get_localized(zc, "name"),
        "name_zh": zc.name_zh,
        "name_en": zc.name_en,
        "sort_order": zc.sort_order,
    }


def _build_sku_public(sku, sku_attrs: list, locale: str) -> dict:
    """SKU 变体序列化(供专区详情换购用)。

    公开商品详情(products.py:get_product)本身不下发 SKU —— 广告牌模式无需换购;
    这里补一份基于 SkuPublic 的最小实现:调用方按 sku_id 分好该 SKU 自己的变体属性
    (sku_id == sku.id)传入,按 sort_order 排序,key/value 走 get_localized 同款本地化。
    """
    attrs = sorted(sku_attrs, key=lambda a: (a.sort_order or 0))
    attributes = [
        ProductAttrSchema(
            attr_key=_localized_attr(a, "attr_key", locale),
            attr_value=_localized_attr(a, "attr_value", locale),
            attr_unit=a.attr_unit,
            sort_order=a.sort_order or 0,
            sku_id=a.sku_id,
            display_name=None,
        ).model_dump()
        for a in attrs
    ]
    images = [_img_to_dict(img) for img in _alive_images(sku.images)] if sku.images else []
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
        price_tiers=[],
        images=images,
        attributes=attributes,
    ).model_dump()


@router.get("/{zone_code}/categories", summary="专区客户视角大类导航")
async def list_zone_categories(
    zone: Zone = Depends(require_zone_access),
    db: AsyncSession = Depends(get_db),
):
    rows = await db.execute(
        select(ZoneCategory)
        .where(ZoneCategory.zone_id == zone.id)
        .order_by(ZoneCategory.sort_order, ZoneCategory.id)
    )
    categories = rows.scalars().all()
    return success([_zone_category_to_public(zc) for zc in categories])


@router.get("/{zone_code}/products", summary="专区白名单商品列表")
async def list_zone_products(
    zone: Zone = Depends(require_zone_access),
    zone_category_code: str | None = Query(None, description="按客户视角大类筛选"),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    zone_category_id: int | None = None
    if zone_category_code is not None:
        zc_row = await db.execute(
            select(ZoneCategory.id).where(
                ZoneCategory.zone_id == zone.id, ZoneCategory.code == zone_category_code,
            )
        )
        zone_category_id = zc_row.scalar_one_or_none()
        if zone_category_id is None:
            # 未知/不属于该专区的类目筛选值 → 空结果(不是错误,列表语义)
            return success({"items": [], "total": 0, "page": page, "size": size, "pages": 0})

    base_filters = [
        ZoneProduct.zone_id == zone.id,
        Product.status == ProductStatus.ACTIVE,
        Product.deleted_at.is_(None),
    ]
    if zone_category_id is not None:
        base_filters.append(ZoneProduct.zone_category_id == zone_category_id)

    count_q = (
        select(func.count(ZoneProduct.id))
        .join(Product, Product.id == ZoneProduct.spu_id)
        .where(*base_filters)
    )
    total = (await db.execute(count_q)).scalar() or 0

    q = (
        select(Product)
        .join(ZoneProduct, ZoneProduct.spu_id == Product.id)
        .where(*base_filters)
        .order_by(ZoneProduct.sort_order, ZoneProduct.id)
        .offset((page - 1) * size)
        .limit(size)
    )
    products = (await db.execute(q)).scalars().all()

    img_map = await product_svc._batch_main_images(db, [p.id for p in products])

    return success({
        # 本查询未预加载 images 关系;products 若没有主图,img_map 中不会有该 id 的条目。
        # 必须显式传 (None, None) 而非让 img_map.get(p.id) 落回 None——_to_public()
        # 在 main_image_urls=None 时会回退到同步访问 p.images,在异步会话下懒加载会炸。
        "items": [
            _to_public(p, main_image_urls=img_map.get(p.id, (None, None)))
            for p in products
        ],
        "total": total,
        "page": page,
        "size": size,
        "pages": math.ceil(total / size) if size else 0,
    })


@router.get("/{zone_code}/products/{product_id}", summary="专区商品详情(含 SKU 变体)")
async def get_zone_product(
    product_id: int,
    zone: Zone = Depends(require_zone_access),
    db: AsyncSession = Depends(get_db),
):
    # 白名单校验:商品必须挂在该 zone 下,否则 404(不泄露商品是否存在)。
    listed = await db.execute(
        select(ZoneProduct.id).where(
            ZoneProduct.zone_id == zone.id, ZoneProduct.spu_id == product_id,
        ).limit(1)
    )
    if listed.scalar_one_or_none() is None:
        raise NotFoundError("Product not found")

    # 注意:不走 public_visible() —— ZONE_ONLY 商品会被它过滤掉。
    # 这里的门禁就是"zone 白名单 + grant",不是 public_visible()。
    p = await product_svc.get_product(db, product_id)
    if p.status != ProductStatus.ACTIVE:
        raise NotFoundError("Product not found")

    spu_attrs = [a for a in p.attrs if a.sku_id is None]
    alive_imgs = _alive_images(p.images)
    locale = get_current_locale()
    all_images = [_img_to_dict(img) for img in alive_imgs]

    detail = ProductPublicDetail(
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
        supply_mode=p.supply_mode,
        unit=p.unit,
        moq=p.moq,
        moq_unit=p.moq_unit,
        lead_time_min=p.lead_time_min,
        lead_time_max=p.lead_time_max,
        gross_weight_kg=p.gross_weight_kg,
        volume_cbm=p.volume_cbm,
        attribute_groups=_build_attribute_groups(spu_attrs, locale),
        images=all_images,
    ).model_dump()

    # 追加 SKU 变体(公开详情本身不带,专区买家需要真实换购):按 ACTIVE 排序,is_default 优先。
    skus = sorted(
        [s for s in p.skus if s.status == "ACTIVE"],
        key=lambda s: (not s.is_default, s.id),
    )
    detail["skus"] = [
        _build_sku_public(s, [a for a in p.attrs if a.sku_id == s.id], locale)
        for s in skus
    ]

    return success(detail)
