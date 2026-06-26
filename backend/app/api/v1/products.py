"""公开商品 API（无需登录，买方浏览用）— v2 i18n 分列模式。

断层隔离：响应体不含任何供应商字段。
多语言输出经 get_localized 按请求 locale 取值。
"""
from __future__ import annotations

import math
from copy import deepcopy
from datetime import datetime, timezone
from time import monotonic

from fastapi import APIRouter, BackgroundTasks, Depends, Header, Query, Request
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

from app.services.buyer_event import EventType, record_event_background

router = APIRouter(prefix="/products", tags=["products"])

HOME_FLOOR_PRODUCT_SIZE = 8
HOME_FLOOR_CACHE_SECONDS = 300
BRAND_CACHE_SECONDS = 600
_BRAND_CACHE: dict[str, tuple[float, list[str]]] = {}

HOME_FLOOR_CONFIGS = [
    {
        "id": "floor-tools",
        "category_paths": [["工具耗材"], ["手动工具"]],
        "exclude_category_paths": [["手动工具", "园林工具"], ["手动工具", "土杂工具"]],
    },
    {
        "id": "floor-safety",
        "category_paths": [["安全防护"], ["劳保"], ["安防"], ["临建设施"]],
        "exclude_category_paths": [],
    },
    {
        "id": "floor-fasteners",
        "category_paths": [["五金紧固"], ["紧固件"]],
        "exclude_category_paths": [],
    },
    {
        "id": "floor-electrical",
        "category_paths": [
            ["电工电气"], ["卫浴照明"], ["电器"], ["灯具照明"],
            ["工控自动化"], ["电工辅料"], ["中低压配电"],
        ],
        "exclude_category_paths": [],
    },
    {
        "id": "floor-doors",
        "category_paths": [
            ["装饰材料", "门窗幕墙"], ["装饰材料", "门窗型材"],
            ["门窗"], ["暖通"], ["水暖器材"], ["陶瓷卫浴"],
            ["塑胶管道"], ["金属管道"],
        ],
        "exclude_category_paths": [],
    },
    {
        "id": "floor-decoration",
        "category_paths": [
            ["防水保温"], ["装饰材料"], ["保温"], ["防水"],
            ["涂料化工"], ["土建材料"], ["临建设施"], ["装配式材料"],
        ],
        "exclude_category_paths": [
            ["装饰材料", "门窗幕墙"], ["装饰材料", "门窗型材"],
        ],
    },
]

_HOME_FLOOR_CACHE: dict[str, tuple[float, dict]] = {}


async def _resolve_buyer_identity(
    authorization: str | None, db: AsyncSession,
) -> tuple[int | None, int | None]:
    """从 token 解析买方身份，返回 (user_id, buyer_org_id)。非买方或失败返回 (None, None)。"""
    if not authorization:
        return None, None
    try:
        from app.core.security import decode_token
        from sqlalchemy import select
        from app.db.models.buyer_member import BuyerMember
        token = authorization.replace("Bearer ", "") if authorization.startswith("Bearer ") else authorization
        payload = decode_token(token)
        user_id = payload.get("sub")
        if not user_id:
            return None, None
        user_id = int(user_id)
        # 通过 buyer_members 查买方组织
        row = await db.execute(
            select(BuyerMember.buyer_org_id).where(BuyerMember.user_id == user_id).limit(1)
        )
        buyer_org_id = row.scalar_one_or_none()
        if not buyer_org_id:
            return None, None
        return user_id, buyer_org_id
    except Exception:
        return None, None


def _build_attribute_groups(attrs, locale: str) -> list[dict]:
    """SPU 属性按 attr_group → attr_key 两层聚合,色板图直接从 attr.swatch_image 读取。

    聚合逻辑:同 attr_key 的多行合成一个 AttrItem.values(N 行→多值)。
    色板:value_type=image 时,直接读 attr.swatch_image 拼完整 URL。
    """
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
        if attr.value_type == "image" and attr.swatch_image:
            swatch = f"{settings.IMAGE_BASE_URL}/{attr.swatch_image}"

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


def _to_public(p, *, main_image_url: str | None = None) -> dict:
    return ProductPublic(
        id=p.id,
        spu_code=p.spu_code,
        name=get_localized(p, "name"),
        description=get_localized(p, "description"),
        category_code=p.category_code,
        origin=get_localized(p, "origin"),
        brand=p.brand_zh or None,
        certifications=p.certifications,
        is_featured=p.is_featured,
        supply_mode=p.supply_mode,
        main_image=main_image_url if main_image_url is not None else _get_main_image_url(p),
        unit=p.unit,
        moq=p.moq,
        moq_unit=p.moq_unit,
    ).model_dump()


def _floor_category_to_public(category) -> dict:
    return {
        "code": category.code,
        "name": get_localized(category, "name"),
        "name_zh": category.name_zh,
        "level": category.level,
    }


@router.get("/certification-options", summary="认证筛选选项")
async def certification_options(db: AsyncSession = Depends(get_db)):
    """聚合所有上架商品的认证值，供前端筛选下拉使用。"""
    options = await product_svc.list_certification_options(db)
    return success(options)


@router.get("", summary="公开商品列表")
async def list_products(
    request: Request,
    background_tasks: BackgroundTasks,
    category_code: str | None = Query(None),
    featured: bool | None = Query(None),
    supply_mode: str | None = Query(None),
    certification: str | None = Query(None, description="按认证筛选，如 CE、ISO 9001"),
    brand: str | None = Query(None, description="按品牌筛选"),
    keyword: str | None = Query(None),
    sort: str = Query("newest"),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=50),
    authorization: str | None = Header(None),
    db: AsyncSession = Depends(get_db),
):
    items, total, img_map = await product_svc.list_products_public(
        db, category_code=category_code,
        featured=featured, supply_mode=supply_mode,
        certification=certification,
        brand=brand,
        keyword=keyword, sort=sort, page=page, size=size,
    )
    # 买方行为埋点: SEARCH / VIEW_CATEGORY
    buyer_uid, buyer_org = await _resolve_buyer_identity(authorization, db)
    if buyer_uid and buyer_org:
        if keyword:
            background_tasks.add_task(
                record_event_background, buyer_org, buyer_uid,
                EventType.SEARCH, None, None,
                {"keyword": keyword, "results": total}, request,
            )
        elif category_code:
            background_tasks.add_task(
                record_event_background, buyer_org, buyer_uid,
                EventType.VIEW_CATEGORY, "category", None,
                {"category_code": category_code}, request,
            )

    return success({
        "items": [_to_public(p, main_image_url=img_map.get(p.id)) for p in items],
        "total": total,
        "page": page,
        "size": size,
        "pages": math.ceil(total / size) if size else 0,
    })


@router.get("/brands", summary="品牌筛选选项（Top 50，缓存 10 分钟）")
async def brand_options(
    category_code: str | None = Query(None, description="按品类缩小范围"),
    db: AsyncSession = Depends(get_db),
):
    """按商品数量降序返回 Top 50 品牌，结果缓存 10 分钟。"""
    cache_key = category_code or "__all__"
    now = monotonic()
    cached = _BRAND_CACHE.get(cache_key)
    if cached and now - cached[0] < BRAND_CACHE_SECONDS:
        return success(cached[1][:])

    brands = await product_svc.list_brand_options(db, category_code=category_code)
    _BRAND_CACHE[cache_key] = (now, brands)
    return success(brands)


@router.get("/home-floors", summary="首页品类楼层商品")
async def home_floor_products(
    db: AsyncSession = Depends(get_db),
):
    locale = get_current_locale()
    cached = _HOME_FLOOR_CACHE.get(locale)
    now = monotonic()
    if cached and now - cached[0] < HOME_FLOOR_CACHE_SECONDS:
        return success(deepcopy(cached[1]))

    floors: dict[str, dict] = {}
    for config in HOME_FLOOR_CONFIGS:
        products, img_map, categories = await product_svc.sample_home_floor_products(
            db,
            category_paths=config["category_paths"],
            exclude_category_paths=config["exclude_category_paths"],
            size=HOME_FLOOR_PRODUCT_SIZE,
        )
        floors[config["id"]] = {
            "categories": [_floor_category_to_public(category) for category in categories[:10]],
            "products": [
                _to_public(product, main_image_url=img_map.get(product.id))
                for product in products
            ],
        }

    data = {
        "floors": floors,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "ttl_seconds": HOME_FLOOR_CACHE_SECONDS,
    }
    _HOME_FLOOR_CACHE[locale] = (now, deepcopy(data))
    return success(data)


@router.get("/{product_id}", summary="公开商品详情")
async def get_product(
    product_id: int,
    request: Request,
    background_tasks: BackgroundTasks,
    authorization: str | None = Header(None),
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
        brand=p.brand_zh or None,
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

    # 买方行为埋点: VIEW_PRODUCT
    buyer_uid, buyer_org = await _resolve_buyer_identity(authorization, db)
    if buyer_uid and buyer_org:
        background_tasks.add_task(
            record_event_background, buyer_org, buyer_uid,
            EventType.VIEW_PRODUCT, "product", product_id,
            {}, request,
        )

    return success(data)
