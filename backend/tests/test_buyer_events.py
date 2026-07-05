"""买方行为追踪 — 事件记录 + 查询 API + RBAC 测试。

BackgroundTask 用独立 session 写事件，SAVEPOINT 隔离看不到。
因此: service 层直接测，API 层通过手动种事件 + 查询 API 测。
"""
from __future__ import annotations

import pytest
from sqlalchemy import select

from app.db.base import _utcnow
from app.db.models.buyer_event import BuyerEvent
from app.db.models.product import Product, ProductStatus
from app.services.buyer_event import (
    EventType,
    get_funnel_stats,
    get_popular_products,
    get_recent_searches,
    get_recent_views,
    clear_recent_searches,
    parse_device_type,
    record_event,
)
from tests.conftest import register_buyer_tz

pytestmark = pytest.mark.asyncio


# ─── helpers ────────────────────────────────────────────

async def _buyer_headers(client) -> tuple[dict, int]:
    """注册买方并返回 (headers, user_id)。"""
    reg = await register_buyer_tz(client)
    token = reg["response"].json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    me = await client.get("/api/v1/auth/me", headers=headers)
    user_id = me.json()["data"]["id"]
    return headers, user_id


async def _get_buyer_org_id(db_session, user_id: int) -> int:
    """从 DB 查买方组织 ID（通过 buyer_members）。"""
    from app.db.models.buyer_member import BuyerMember
    row = await db_session.execute(
        select(BuyerMember.buyer_org_id).where(BuyerMember.user_id == user_id).limit(1)
    )
    return row.scalar_one()


async def _get_active_product_id(db_session) -> int | None:
    """获取一个 ACTIVE 商品 ID。"""
    row = await db_session.execute(
        select(Product.id).where(
            Product.status == ProductStatus.ACTIVE,
            Product.deleted_at.is_(None),
        ).limit(1)
    )
    return row.scalar_one_or_none()


async def _seed_event(db_session, **kwargs):
    """直接向 buyer_events 表插入一条记录。"""
    defaults = {
        "session_id": None,
        "resource_type": None,
        "resource_id": None,
        "referrer": None,
        "device_type": "desktop",
        "ip": "127.0.0.1",
        "extra": {},
        "created_at": _utcnow(),
    }
    defaults.update(kwargs)
    ev = BuyerEvent(**defaults)
    db_session.add(ev)
    await db_session.flush()
    return ev


# ─── parse_device_type ──────────────────────────────────


def test_parse_device_type_mobile():
    assert parse_device_type("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0)") == "mobile"
    assert parse_device_type("Mozilla/5.0 (Linux; Android 14)") == "mobile"


def test_parse_device_type_tablet():
    assert parse_device_type("Mozilla/5.0 (iPad; CPU OS 17_0)") == "tablet"


def test_parse_device_type_desktop():
    assert parse_device_type("Mozilla/5.0 (Macintosh; Intel Mac OS X)") == "desktop"
    assert parse_device_type("") == "desktop"


# ─── record_event 直接测 service ─────────────────────────


async def test_record_event_basic(client, db_session):
    """record_event 写入事件记录。"""
    _, user_id = await _buyer_headers(client)
    org_id = await _get_buyer_org_id(db_session, user_id)

    await record_event(
        db_session,
        buyer_org_id=org_id,
        user_id=user_id,
        event_type=EventType.VIEW_PRODUCT,
        resource_type="product",
        resource_id=999,
    )
    await db_session.flush()

    rows = (await db_session.execute(
        select(BuyerEvent).where(
            BuyerEvent.user_id == user_id,
            BuyerEvent.event_type == EventType.VIEW_PRODUCT,
            BuyerEvent.resource_id == 999,
        )
    )).scalars().all()
    assert len(rows) == 1
    assert rows[0].resource_type == "product"


async def test_record_event_search_with_keyword(client, db_session):
    """SEARCH 事件 extra 包含 keyword。"""
    _, user_id = await _buyer_headers(client)
    org_id = await _get_buyer_org_id(db_session, user_id)

    await record_event(
        db_session,
        buyer_org_id=org_id,
        user_id=user_id,
        event_type=EventType.SEARCH,
        extra={"keyword": "cement", "results": 12},
    )
    await db_session.flush()

    rows = (await db_session.execute(
        select(BuyerEvent).where(
            BuyerEvent.user_id == user_id,
            BuyerEvent.event_type == EventType.SEARCH,
        )
    )).scalars().all()
    assert len(rows) == 1
    assert rows[0].extra["keyword"] == "cement"
    assert rows[0].extra["results"] == 12


async def test_dedup_within_5min(client, db_session):
    """5 分钟内同一商品只记 1 条。"""
    _, user_id = await _buyer_headers(client)
    org_id = await _get_buyer_org_id(db_session, user_id)

    for _ in range(3):
        await record_event(
            db_session,
            buyer_org_id=org_id,
            user_id=user_id,
            event_type=EventType.VIEW_PRODUCT,
            resource_type="product",
            resource_id=888,
        )
        await db_session.flush()

    rows = (await db_session.execute(
        select(BuyerEvent).where(
            BuyerEvent.user_id == user_id,
            BuyerEvent.event_type == EventType.VIEW_PRODUCT,
            BuyerEvent.resource_id == 888,
        )
    )).scalars().all()
    assert len(rows) == 1


async def test_dedup_different_products(client, db_session):
    """不同商品各记 1 条。"""
    _, user_id = await _buyer_headers(client)
    org_id = await _get_buyer_org_id(db_session, user_id)

    for pid in [777, 778, 779]:
        await record_event(
            db_session,
            buyer_org_id=org_id,
            user_id=user_id,
            event_type=EventType.VIEW_PRODUCT,
            resource_type="product",
            resource_id=pid,
        )
        await db_session.flush()

    rows = (await db_session.execute(
        select(BuyerEvent).where(
            BuyerEvent.user_id == user_id,
            BuyerEvent.event_type == EventType.VIEW_PRODUCT,
        )
    )).scalars().all()
    assert len(rows) == 3


async def test_dedup_search_by_keyword(client, db_session):
    """SEARCH 去重按 keyword。"""
    _, user_id = await _buyer_headers(client)
    org_id = await _get_buyer_org_id(db_session, user_id)

    # 同关键词搜索两次
    for _ in range(2):
        await record_event(
            db_session,
            buyer_org_id=org_id,
            user_id=user_id,
            event_type=EventType.SEARCH,
            extra={"keyword": "tiles_dedup"},
        )
        await db_session.flush()

    rows = (await db_session.execute(
        select(BuyerEvent).where(
            BuyerEvent.user_id == user_id,
            BuyerEvent.event_type == EventType.SEARCH,
            BuyerEvent.extra["keyword"].astext == "tiles_dedup",
        )
    )).scalars().all()
    assert len(rows) == 1

    # 不同关键词应各记一条
    await record_event(
        db_session,
        buyer_org_id=org_id,
        user_id=user_id,
        event_type=EventType.SEARCH,
        extra={"keyword": "cement_dedup"},
    )
    await db_session.flush()

    all_searches = (await db_session.execute(
        select(BuyerEvent).where(
            BuyerEvent.user_id == user_id,
            BuyerEvent.event_type == EventType.SEARCH,
        )
    )).scalars().all()
    assert len(all_searches) == 2


# ─── 游客事件: 按 session_id 归属 ────────────────────────


class _FakeReq:
    """最小 Request 桩: record_event 只读 headers 和 client。"""
    def __init__(self, session_id=None, ua="Mozilla/5.0 (Macintosh)"):
        h = {}
        if session_id:
            h["x-session-id"] = session_id
        if ua:
            h["user-agent"] = ua
        self.headers = h
        self.client = None


_SESS_1 = "11111111-1111-1111-1111-111111111111"
_SESS_2 = "22222222-2222-2222-2222-222222222222"
_SESS_A = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
_SESS_B = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"


async def test_guest_search_recorded_by_session(db_session):
    """游客(无 user_id)搜索按 session_id 落库，user_id / org 为空。"""
    await record_event(
        db_session, buyer_org_id=None, user_id=None,
        event_type=EventType.SEARCH,
        extra={"keyword": "guest_cement"},
        request=_FakeReq(session_id=_SESS_1),
    )
    await db_session.flush()

    rows = (await db_session.execute(
        select(BuyerEvent).where(BuyerEvent.session_id == _SESS_1)
    )).scalars().all()
    assert len(rows) == 1
    assert rows[0].user_id is None
    assert rows[0].buyer_org_id is None
    assert rows[0].extra["keyword"] == "guest_cement"


async def test_guest_dedup_by_session(db_session):
    """同一 session 同关键词 5 分钟内去重。"""
    req = _FakeReq(session_id=_SESS_2)
    for _ in range(3):
        await record_event(
            db_session, buyer_org_id=None, user_id=None,
            event_type=EventType.SEARCH,
            extra={"keyword": "guest_tiles"}, request=req,
        )
        await db_session.flush()

    rows = (await db_session.execute(
        select(BuyerEvent).where(BuyerEvent.session_id == _SESS_2)
    )).scalars().all()
    assert len(rows) == 1


async def test_guest_different_sessions_not_deduped(db_session):
    """不同 session 同关键词各记一条(是两个游客)。"""
    for sid in [_SESS_A, _SESS_B]:
        await record_event(
            db_session, buyer_org_id=None, user_id=None,
            event_type=EventType.SEARCH,
            extra={"keyword": "shared_kw"},
            request=_FakeReq(session_id=sid),
        )
        await db_session.flush()

    rows = (await db_session.execute(
        select(BuyerEvent).where(
            BuyerEvent.event_type == EventType.SEARCH,
            BuyerEvent.extra["keyword"].astext == "shared_kw",
        )
    )).scalars().all()
    assert len(rows) == 2


async def test_event_dropped_without_subject(db_session):
    """既无 user_id 又无 session_id → 无法归属，丢弃。"""
    await record_event(
        db_session, buyer_org_id=None, user_id=None,
        event_type=EventType.SEARCH,
        extra={"keyword": "orphan_kw"},
        request=_FakeReq(session_id=None),
    )
    await db_session.flush()

    rows = (await db_session.execute(
        select(BuyerEvent).where(
            BuyerEvent.extra["keyword"].astext == "orphan_kw"
        )
    )).scalars().all()
    assert rows == []


async def test_guest_invalid_session_id_dropped(db_session):
    """非法 session_id(伪造/非 UUID/超长) → 无归属主体，丢弃。"""
    for bad_sid in ["sess-forged", "a" * 100, "not-a-uuid"]:
        await record_event(
            db_session, buyer_org_id=None, user_id=None,
            event_type=EventType.SEARCH,
            extra={"keyword": "forged_kw"},
            request=_FakeReq(session_id=bad_sid),
        )
        await db_session.flush()

    rows = (await db_session.execute(
        select(BuyerEvent).where(
            BuyerEvent.extra["keyword"].astext == "forged_kw"
        )
    )).scalars().all()
    assert rows == []


# ─── 查询: get_recent_views ─────────────────────────────


async def test_recent_views(client, db_session):
    """最近浏览返回 ACTIVE 商品摘要。"""
    _, user_id = await _buyer_headers(client)
    org_id = await _get_buyer_org_id(db_session, user_id)

    pid = await _get_active_product_id(db_session)
    if not pid:
        pytest.skip("No ACTIVE products in test DB")

    await _seed_event(
        db_session,
        buyer_org_id=org_id, user_id=user_id,
        event_type=EventType.VIEW_PRODUCT,
        resource_type="product", resource_id=pid,
    )

    views = await get_recent_views(db_session, user_id, limit=5)
    assert len(views) >= 1
    assert views[0]["id"] == pid
    assert "name" in views[0]


async def test_recent_views_dedup(client, db_session):
    """同一商品多次浏览只返回一条。"""
    _, user_id = await _buyer_headers(client)
    org_id = await _get_buyer_org_id(db_session, user_id)

    pid = await _get_active_product_id(db_session)
    if not pid:
        pytest.skip("No ACTIVE products in test DB")

    from datetime import timedelta
    now = _utcnow()
    # 插入两条不同时间的浏览记录
    for i in range(2):
        await _seed_event(
            db_session,
            buyer_org_id=org_id, user_id=user_id,
            event_type=EventType.VIEW_PRODUCT,
            resource_type="product", resource_id=pid,
            created_at=now - timedelta(minutes=i * 10),
        )

    views = await get_recent_views(db_session, user_id, limit=10)
    pids = [v["id"] for v in views]
    assert pids.count(pid) == 1


# ─── 查询: get_recent_searches ──────────────────────────


async def test_recent_searches(client, db_session):
    """返回去重的关键词列表。"""
    _, user_id = await _buyer_headers(client)
    org_id = await _get_buyer_org_id(db_session, user_id)

    for kw in ["tiles", "cement", "tiles"]:  # tiles 重复
        await _seed_event(
            db_session,
            buyer_org_id=org_id, user_id=user_id,
            event_type=EventType.SEARCH,
            extra={"keyword": kw},
        )

    keywords = await get_recent_searches(db_session, user_id, limit=10)
    assert "tiles" in keywords
    assert "cement" in keywords
    assert keywords.count("tiles") == 1  # 去重


async def test_clear_searches(client, db_session):
    """清空搜索历史后返回空列表。"""
    _, user_id = await _buyer_headers(client)
    org_id = await _get_buyer_org_id(db_session, user_id)

    await _seed_event(
        db_session,
        buyer_org_id=org_id, user_id=user_id,
        event_type=EventType.SEARCH,
        extra={"keyword": "blocks"},
    )

    deleted = await clear_recent_searches(db_session, user_id)
    assert deleted >= 1

    keywords = await get_recent_searches(db_session, user_id)
    assert keywords == []


# ─── 运营分析 ───────────────────────────────────────────


async def test_popular_products(client, db_session):
    """热门商品返回按浏览量排行。"""
    _, user_id = await _buyer_headers(client)
    org_id = await _get_buyer_org_id(db_session, user_id)

    pid = await _get_active_product_id(db_session)
    if not pid:
        pytest.skip("No ACTIVE products in test DB")

    for _ in range(3):
        await _seed_event(
            db_session,
            buyer_org_id=org_id, user_id=user_id,
            event_type=EventType.VIEW_PRODUCT,
            resource_type="product", resource_id=pid,
        )

    results = await get_popular_products(db_session, days=30, limit=5, metric="view")
    assert len(results) >= 1
    assert results[0]["product_id"] == pid
    assert results[0]["event_count"] >= 3


async def test_funnel_stats(client, db_session):
    """转化漏斗返回各阶段独立用户数。"""
    _, user_id = await _buyer_headers(client)
    org_id = await _get_buyer_org_id(db_session, user_id)

    # 种各阶段事件
    for et in [EventType.VIEW_PRODUCT, EventType.ADD_TO_CART, EventType.CREATE_RFQ]:
        await _seed_event(
            db_session,
            buyer_org_id=org_id, user_id=user_id,
            event_type=et,
            resource_type="product", resource_id=100,
        )

    stats = await get_funnel_stats(db_session, days=30)
    assert stats["period_days"] == 30
    assert len(stats["stages"]) == 5

    view_stage = next(s for s in stats["stages"] if s["event_type"] == EventType.VIEW_PRODUCT)
    assert view_stage["unique_users"] >= 1


# ─── RBAC API ──────────────────────────────────────────


async def test_buyer_can_read_events(client):
    """BUYER 可访问 recent-views / recent-searches。"""
    headers, _ = await _buyer_headers(client)
    r = await client.get("/api/v1/buyer/events/recent-views", headers=headers)
    assert r.status_code == 200
    r = await client.get("/api/v1/buyer/events/recent-searches", headers=headers)
    assert r.status_code == 200


async def test_buyer_cannot_read_analytics(client):
    """BUYER 不能访问运营分析端点。"""
    headers, _ = await _buyer_headers(client)
    r = await client.get("/api/v1/operator/analytics/popular-products", headers=headers)
    assert r.status_code == 403


async def test_anonymous_cannot_read_events(client):
    """未登录不能访问买方事件 API。"""
    r = await client.get("/api/v1/buyer/events/recent-views")
    assert r.status_code in (401, 403)


async def test_operator_can_read_analytics(client, superadmin_headers):
    """OPERATOR 可访问运营分析端点。"""
    from tests.conftest import _next_phone
    phone = _next_phone()
    r = await client.post(
        "/api/v1/admin/users",
        json={
            "email": f"op_{phone[4:]}@test.local",
            "phone": phone,
            "password": "TestOp123!",
            "name": "Test Op",
            "role_code": "OPERATOR",
        },
        headers=superadmin_headers,
    )
    if r.status_code != 200:
        pytest.skip("Cannot create operator via admin API")

    login = await client.post(
        "/api/v1/auth/login",
        json={"identifier": phone, "password": "TestOp123!"},
    )
    token = login.json()["data"]["access_token"]
    op_headers = {"Authorization": f"Bearer {token}"}

    r = await client.get("/api/v1/operator/analytics/popular-products", headers=op_headers)
    assert r.status_code == 200
    r = await client.get("/api/v1/operator/analytics/funnel", headers=op_headers)
    assert r.status_code == 200
