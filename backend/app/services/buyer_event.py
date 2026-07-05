"""买方行为事件服务 — 记录 + 查询。

设计决策见 docs/adr/ADR-0007-买方行为追踪方案决策.md
"""
from __future__ import annotations

from datetime import timedelta
from uuid import UUID

from fastapi import Request
from sqlalchemy import delete, distinct, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.i18n import get_localized
from app.db.base import _utcnow
from app.db.models.buyer_event import BuyerEvent
from app.db.models.product import Product, ProductStatus
from app.db.models.product_image import ImageType, ProductImage
from app.services._buyer_utils import thumb_url_from_image_key
from app.services.product_visibility import public_visible


# --------------- 事件类型常量 ---------------

class EventType:
    VIEW_PRODUCT = "VIEW_PRODUCT"
    SEARCH = "SEARCH"
    VIEW_CATEGORY = "VIEW_CATEGORY"
    ADD_TO_CART = "ADD_TO_CART"
    CREATE_RFQ = "CREATE_RFQ"
    SUBMIT_RFQ = "SUBMIT_RFQ"
    ACCEPT_QUOTE = "ACCEPT_QUOTE"


# 去重时间窗口
DEDUP_WINDOW = timedelta(minutes=5)


# --------------- UA 解析 ---------------

def parse_device_type(ua: str) -> str:
    """从 User-Agent 解析设备类型。"""
    ua_lower = ua.lower()
    if any(k in ua_lower for k in ("iphone", "android", "mobile")):
        return "mobile"
    if any(k in ua_lower for k in ("ipad", "tablet")):
        return "tablet"
    return "desktop"


def _valid_session_id(raw: str | None) -> str | None:
    """校验客户端 x-session-id 为合法 UUID，否则丢弃。

    session_id 客户端可任意伪造，用作游客归属键前必须校验:
    - 挡住伪造/垃圾值无限灌库(非法值 → 无归属主体 → 事件丢弃)
    - 保证不超过列宽 String(36)，避免 insert 失败被静默吞掉
    """
    if not raw:
        return None
    try:
        return str(UUID(raw))
    except (ValueError, AttributeError, TypeError):
        return None


# --------------- 事件记录 ---------------

async def record_event(
    db: AsyncSession,
    *,
    buyer_org_id: int | None,
    user_id: int | None,
    event_type: str,
    resource_type: str | None = None,
    resource_id: int | None = None,
    extra: dict | None = None,
    request: Request | None = None,
) -> None:
    """记录买方行为事件（含去重）。

    归属主体: 登录买家按 user_id，游客按 session_id。二者皆无则无法归属，丢弃。
    去重规则: 同一主体 + event_type + resource_id，5 分钟内不重复记录。
    SEARCH 事件按 keyword 去重。
    """
    now = _utcnow()
    cutoff = now - DEDUP_WINDOW

    # 从 request 提取上下文
    session_id = None
    referrer = None
    device_type = None
    ip = None
    if request is not None:
        session_id = _valid_session_id(request.headers.get("x-session-id"))
        referrer = request.headers.get("referer")
        ua = request.headers.get("user-agent", "")
        device_type = parse_device_type(ua) if ua else None
        ip = request.client.host if request.client else None

    # 归属主体: 登录按 user_id，游客按 session_id；都没有则无法归属，丢弃
    if user_id is not None:
        subject = BuyerEvent.user_id == user_id
    elif session_id:
        subject = BuyerEvent.session_id == session_id
    else:
        return

    # 去重查询
    if event_type == EventType.SEARCH:
        keyword = (extra or {}).get("keyword", "")
        dup_q = select(BuyerEvent.id).where(
            subject,
            BuyerEvent.event_type == event_type,
            BuyerEvent.extra["keyword"].astext == keyword,
            BuyerEvent.created_at > cutoff,
        ).limit(1)
    else:
        dup_q = select(BuyerEvent.id).where(
            subject,
            BuyerEvent.event_type == event_type,
            BuyerEvent.resource_id == resource_id,
            BuyerEvent.created_at > cutoff,
        ).limit(1)

    dup = (await db.execute(dup_q)).scalar_one_or_none()
    if dup is not None:
        return

    event = BuyerEvent(
        buyer_org_id=buyer_org_id,
        user_id=user_id,
        session_id=session_id,
        event_type=event_type,
        resource_type=resource_type,
        resource_id=resource_id,
        referrer=referrer,
        device_type=device_type,
        ip=ip,
        extra=extra or {},
        created_at=now,
    )
    db.add(event)
    await db.flush()


# --------------- BackgroundTask 辅助 ---------------

async def record_event_background(
    buyer_org_id: int | None,
    user_id: int | None,
    event_type: str,
    resource_type: str | None,
    resource_id: int | None,
    extra: dict | None,
    request: Request | None,
) -> None:
    """BackgroundTask 用: 独立 session + commit，失败静默。"""
    from app.db.session import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        try:
            await record_event(
                db,
                buyer_org_id=buyer_org_id,
                user_id=user_id,
                event_type=event_type,
                resource_type=resource_type,
                resource_id=resource_id,
                extra=extra,
                request=request,
            )
            await db.commit()
        except Exception:
            pass  # 行为记录失败不影响业务


# --------------- 查询: 最近浏览 ---------------

async def get_recent_views(
    db: AsyncSession,
    user_id: int,
    limit: int = 8,
) -> list[dict]:
    """返回买方最近浏览的商品列表（去重、排除已下架/软删）。"""
    # 子查询: 按 resource_id 去重，取每个商品最近一次浏览时间
    subq = (
        select(
            BuyerEvent.resource_id,
            func.max(BuyerEvent.created_at).label("last_viewed"),
        )
        .where(
            BuyerEvent.user_id == user_id,
            BuyerEvent.event_type == EventType.VIEW_PRODUCT,
            BuyerEvent.resource_type == "product",
            BuyerEvent.resource_id.isnot(None),
        )
        .group_by(BuyerEvent.resource_id)
        .subquery()
    )

    # JOIN products 取商品摘要
    q = (
        select(Product, subq.c.last_viewed)
        .join(subq, Product.id == subq.c.resource_id)
        .where(public_visible())
        .order_by(subq.c.last_viewed.desc())
        .limit(limit)
    )

    rows = (await db.execute(q)).all()

    result = []
    for product, last_viewed in rows:
        main_url, thumb_url = await _get_product_main_image(db, product.id)
        result.append({
            "id": product.id,
            "name": get_localized(product, "name"),
            "main_image": main_url,
            "main_image_thumbnail": thumb_url,
            "category_code": product.category_code,
            "unit": product.unit,
            "moq": float(product.moq) if product.moq else None,
        })
    return result


async def _get_product_main_image(db: AsyncSession, product_id: int) -> tuple[str | None, str | None]:
    """获取商品主图 URL 和缩略图 URL。"""
    q = (
        select(ProductImage.image_key)
        .where(
            ProductImage.product_id == product_id,
            ProductImage.deleted_at.is_(None),
        )
        .order_by(
            (ProductImage.image_type != ImageType.MAIN).asc(),
            ProductImage.sort_order.asc(),
        )
        .limit(1)
    )
    key = (await db.execute(q)).scalar_one_or_none()
    if key:
        return f"{settings.IMAGE_PATH_PREFIX}/{key}", thumb_url_from_image_key(key)
    return None, None


# --------------- 删除: 单条浏览记录 ---------------

async def remove_recent_view(
    db: AsyncSession,
    user_id: int,
    product_id: int,
) -> int:
    """物理删除该用户对指定商品的所有 VIEW_PRODUCT 事件，返回删除行数。"""
    result = await db.execute(
        delete(BuyerEvent).where(
            BuyerEvent.user_id == user_id,
            BuyerEvent.event_type == EventType.VIEW_PRODUCT,
            BuyerEvent.resource_type == "product",
            BuyerEvent.resource_id == product_id,
        )
    )
    await db.flush()
    return result.rowcount


# --------------- 查询: 最近搜索 ---------------

async def get_recent_searches(
    db: AsyncSession,
    user_id: int,
    limit: int = 10,
) -> list[str]:
    """返回买方最近搜索的关键词（去重）。"""
    q = (
        select(
            BuyerEvent.extra["keyword"].astext.label("keyword"),
            func.max(BuyerEvent.created_at).label("last_searched"),
        )
        .where(
            BuyerEvent.user_id == user_id,
            BuyerEvent.event_type == EventType.SEARCH,
            BuyerEvent.extra["keyword"].astext != "",
        )
        .group_by(text("keyword"))
        .order_by(text("last_searched DESC"))
        .limit(limit)
    )
    rows = (await db.execute(q)).all()
    return [row.keyword for row in rows]


# --------------- 清空搜索历史 ---------------

async def clear_recent_searches(
    db: AsyncSession,
    user_id: int,
) -> int:
    """物理删除该用户所有 SEARCH 事件，返回删除行数。"""
    result = await db.execute(
        delete(BuyerEvent).where(
            BuyerEvent.user_id == user_id,
            BuyerEvent.event_type == EventType.SEARCH,
        )
    )
    await db.flush()
    return result.rowcount


# --------------- 运营分析: 热门商品 ---------------

async def get_popular_products(
    db: AsyncSession,
    days: int = 30,
    limit: int = 20,
    metric: str = "view",
) -> list[dict]:
    """按指定维度返回热门商品 Top N。"""
    metric_map = {
        "view": EventType.VIEW_PRODUCT,
        "cart": EventType.ADD_TO_CART,
        "rfq": EventType.CREATE_RFQ,
    }
    event_type = metric_map.get(metric, EventType.VIEW_PRODUCT)
    cutoff = _utcnow() - timedelta(days=days)

    subq = (
        select(
            BuyerEvent.resource_id,
            func.count().label("event_count"),
            func.count(distinct(BuyerEvent.user_id)).label("unique_users"),
        )
        .where(
            BuyerEvent.event_type == event_type,
            BuyerEvent.resource_type == "product",
            BuyerEvent.resource_id.isnot(None),
            BuyerEvent.created_at > cutoff,
        )
        .group_by(BuyerEvent.resource_id)
        .order_by(text("event_count DESC"))
        .limit(limit)
        .subquery()
    )

    q = (
        select(Product, subq.c.event_count, subq.c.unique_users)
        .join(subq, Product.id == subq.c.resource_id)
        .where(Product.deleted_at.is_(None))
        .order_by(subq.c.event_count.desc())
    )

    rows = (await db.execute(q)).all()
    return [
        {
            "product_id": p.id,
            "name": get_localized(p, "name"),
            "category_code": p.category_code,
            "event_count": count,
            "unique_users": users,
        }
        for p, count, users in rows
    ]


# --------------- 运营分析: 转化漏斗 ---------------

FUNNEL_STAGES = [
    EventType.VIEW_PRODUCT,
    EventType.ADD_TO_CART,
    EventType.CREATE_RFQ,
    EventType.SUBMIT_RFQ,
    EventType.ACCEPT_QUOTE,
]


async def get_funnel_stats(
    db: AsyncSession,
    days: int = 30,
) -> dict:
    """返回各阶段独立用户数。"""
    cutoff = _utcnow() - timedelta(days=days)

    stages = []
    for et in FUNNEL_STAGES:
        q = select(func.count(distinct(BuyerEvent.user_id))).where(
            BuyerEvent.event_type == et,
            BuyerEvent.created_at > cutoff,
        )
        count = (await db.execute(q)).scalar() or 0
        stages.append({"event_type": et, "unique_users": count})

    return {"period_days": days, "stages": stages}
