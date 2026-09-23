"""「我的订单」BFF + 内部组织路由 集成测试(契约 §8 matgo 部分)。

覆盖接线:登录门 → 确定性组织解析四态 → 对履约签令牌与透传 → 履约异常映射 503;
内部端点无令牌 / 错 aud / 错 iss → 401,正确令牌可搜索、按 id 取。
履约后台用 httpx.MockTransport 假扮,断言发出的令牌能按 matgo→履约口径验签。
"""
from __future__ import annotations

import httpx
import pytest

from app.core.s2s_auth import (
    AUD_FULFILLMENT_PORTAL,
    AUD_MATGO_INTERNAL,
    ISS_FULFILLMENT,
    ISS_MATGO,
    sign_s2s_token,
    verify_s2s_token,
)
from app.db.models.buyer_member import BuyerMember
from app.db.models.buyer_organization import BuyerOrganization
from app.main import app
from app.services.fulfillment_client import FulfillmentClient, get_fulfillment_client
from tests.conftest import register_buyer_tz

_LIST_PAGE = {
    "items": [{
        "no": "SO-2026-0001", "created_at": "2026-09-01T08:00:00Z", "status": "CONFIRMED",
        "currency": "USD", "total_amount": "1234.50", "stage": "LOADED", "line_count": 2,
    }],
    "total": 1, "page": 1, "size": 20,
}


async def _buyer(client, company: str = "Acme Ltd") -> tuple[dict, int, int]:
    """注册买方(自带 1 个 ACTIVE 组织),返回 (headers, user_id, org_id)。"""
    r = (await register_buyer_tz(client, company_name=company))["response"]
    assert r.status_code == 200, r.text
    h = {"Authorization": f"Bearer {r.json()['data']['access_token']}"}
    me = (await client.get("/api/v1/auth/me", headers=h)).json()["data"]
    return h, me["id"], me["organization"]["id"]


import pytest_asyncio


@pytest_asyncio.fixture
async def fulfillment():
    """用 MockTransport 顶替履约后台:每测试建一个客户端,teardown aclose;
    dependency_overrides 由 client fixture 统一 clear。"""
    holder: list[FulfillmentClient] = []

    def install(handler):
        fc = FulfillmentClient("http://fulfillment.test", transport=httpx.MockTransport(handler))
        holder.append(fc)
        app.dependency_overrides[get_fulfillment_client] = lambda: fc
        return fc

    yield install
    for fc in holder:
        await fc.aclose()


def _envelope(data, code=0):
    return {"code": code, "message": "ok" if code == 0 else "err", "data": data}


# ── BFF:正常透传 + 令牌口径 ────────────────────────────────

@pytest.mark.asyncio
async def test_list_orders_passes_through_and_signs_org_token(client, fulfillment):
    h, _, org_id = await _buyer(client)
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["auth"] = request.headers.get("authorization", "")
        return httpx.Response(200, json=_envelope(_LIST_PAGE))

    fulfillment(handler)
    r = await client.get("/api/v1/buyer/orders?page=1&size=20", headers={**h, "Accept-Language": "en"})
    assert r.status_code == 200, r.text
    assert r.json()["data"] == _LIST_PAGE  # 原样透传,金额仍是 decimal string

    assert seen["url"].startswith("http://fulfillment.test/api/v1/portal/orders?")
    assert "page=1" in seen["url"] and "size=20" in seen["url"] and "lang=en" in seen["url"]
    scheme, _, token = seen["auth"].partition(" ")
    assert scheme == "Bearer"
    # 履约侧口径验签:iss=matgo, aud=fulfillment-portal, sub=org:<id>
    p = verify_s2s_token(token, issuer=ISS_MATGO, audience=AUD_FULFILLMENT_PORTAL)
    assert p.sub == f"org:{org_id}" and p.iss == ISS_MATGO


@pytest.mark.asyncio
async def test_detail_passes_no_and_lang(client, fulfillment):
    h, _, _ = await _buyer(client)
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        return httpx.Response(200, json=_envelope({"no": "SO-2026-0001", "lines": [], "shipments": []}))

    fulfillment(handler)
    r = await client.get("/api/v1/buyer/orders/SO-2026-0001", headers={**h, "Accept-Language": "sw"})
    assert r.status_code == 200, r.text
    assert r.json()["data"]["no"] == "SO-2026-0001"
    assert seen["url"] == "http://fulfillment.test/api/v1/portal/orders/SO-2026-0001?lang=sw"


@pytest.mark.asyncio
async def test_detail_rejects_malformed_order_no(client, fulfillment):
    h, _, _ = await _buyer(client)
    fulfillment(lambda req: httpx.Response(200, json=_envelope({})))
    r = await client.get("/api/v1/buyer/orders/SO%401", headers=h)
    assert r.status_code == 422


# ── BFF:四态 ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_not_bound_when_fulfillment_returns_42501(client, fulfillment):
    h, _, _ = await _buyer(client)
    fulfillment(lambda req: httpx.Response(404, json=_envelope(None, 42501)))
    r = await client.get("/api/v1/buyer/orders", headers=h)
    assert r.status_code == 200
    assert r.json()["data"] == {"binding": "NOT_BOUND"}


@pytest.mark.asyncio
async def test_no_org_for_buyer_without_membership(client, fulfillment, db_session):
    """BUYER 角色但 buyer_members 已无行(组织被清)→ NO_ORG,且不碰履约。"""
    from sqlalchemy import delete
    h, user_id, _ = await _buyer(client)
    await db_session.execute(delete(BuyerMember).where(BuyerMember.user_id == user_id))
    await db_session.commit()
    calls = []
    fulfillment(lambda req: calls.append(req) or httpx.Response(200, json=_envelope(_LIST_PAGE)))
    r = await client.get("/api/v1/buyer/orders", headers=h)
    assert r.status_code == 200
    assert r.json()["data"] == {"binding": "NO_ORG"}
    assert calls == []  # 未解析出组织就不该碰履约


@pytest.mark.asyncio
async def test_non_buyer_role_is_403_even_with_membership(client, fulfillment, superadmin_headers, db_session):
    """角色门在组织解析之前:管理员即便被挂进某组织的 buyer_members,也拿不到订单。"""
    from sqlalchemy import select
    from app.db.models.user import User
    from app.core.config import settings
    _, _, org_id = await _buyer(client)
    admin_id = (await db_session.execute(
        select(User.id).where(User.email == settings.SUPER_ADMIN_EMAIL)
    )).scalar_one()
    db_session.add(BuyerMember(user_id=admin_id, buyer_org_id=org_id, is_owner=False))
    await db_session.commit()
    calls = []
    fulfillment(lambda req: calls.append(req) or httpx.Response(200, json=_envelope(_LIST_PAGE)))
    r = await client.get("/api/v1/buyer/orders", headers=superadmin_headers)
    assert r.status_code == 403 and r.json()["code"] == 40003
    assert calls == []


@pytest.mark.asyncio
async def test_must_change_password_blocked(client, fulfillment, db_session):
    from app.db.models.user import User
    h, user_id, _ = await _buyer(client)
    user = await db_session.get(User, user_id)
    user.must_change_password = True
    await db_session.commit()
    fulfillment(lambda req: httpx.Response(200, json=_envelope(_LIST_PAGE)))
    r = await client.get("/api/v1/buyer/orders", headers=h)
    assert r.status_code == 403 and r.json()["code"] == 40007


@pytest.mark.asyncio
async def test_ambiguous_org_when_user_in_two_orgs(client, fulfillment, db_session):
    h_a, user_a, _ = await _buyer(client, "Alpha Co")
    _, _, org_b = await _buyer(client, "Beta Co")
    db_session.add(BuyerMember(user_id=user_a, buyer_org_id=org_b, is_owner=False))
    await db_session.commit()

    calls = []
    fulfillment(lambda req: calls.append(req) or httpx.Response(200, json=_envelope(_LIST_PAGE)))
    r = await client.get("/api/v1/buyer/orders", headers=h_a)
    assert r.status_code == 200
    assert r.json()["data"] == {"binding": "AMBIGUOUS_ORG"}
    assert calls == []


@pytest.mark.asyncio
async def test_org_disabled(client, fulfillment, db_session):
    h, _, org_id = await _buyer(client)
    org = await db_session.get(BuyerOrganization, org_id)
    org.status = "DISABLED"
    await db_session.commit()

    fulfillment(lambda req: httpx.Response(200, json=_envelope(_LIST_PAGE)))
    r = await client.get("/api/v1/buyer/orders/SO-1", headers=h)
    assert r.status_code == 200
    assert r.json()["data"] == {"binding": "ORG_DISABLED"}


# ── BFF:履约异常 → 503;单号不存在 → 404 ───────────────────

@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["timeout", "http500", "http403", "garbage"])
async def test_fulfillment_failures_map_to_503(client, fulfillment, failure):
    h, _, _ = await _buyer(client)

    def handler(request: httpx.Request) -> httpx.Response:
        if failure == "timeout":
            raise httpx.ReadTimeout("slow", request=request)
        if failure == "http500":
            return httpx.Response(500, json=_envelope(None, 50000))
        if failure == "http403":
            return httpx.Response(403, json=_envelope(None, 40003))
        return httpx.Response(200, content=b"<html>not json</html>")

    fulfillment(handler)
    r = await client.get("/api/v1/buyer/orders", headers=h)
    assert r.status_code == 503, r.text
    body = r.json()
    assert body["code"] == 51001
    assert body["message_key"] == "error.orders.unavailable"


@pytest.mark.asyncio
async def test_detail_not_found_is_404_not_503(client, fulfillment):
    h, _, _ = await _buyer(client)
    fulfillment(lambda req: httpx.Response(404, json=_envelope(None, 40008)))
    r = await client.get("/api/v1/buyer/orders/SO-NOPE", headers=h)
    assert r.status_code == 404
    assert r.json()["code"] == 40008


@pytest.mark.asyncio
@pytest.mark.parametrize("code", [40000, 42502, None])
async def test_detail_404_with_other_code_is_503(client, fulfillment, code):
    """只有履约通用 NotFound(40008)才是"单号不存在";反代 JSON 404 / 别的业务码 → 不可用。"""
    h, _, _ = await _buyer(client)
    body = _envelope(None, code) if code is not None else {"detail": "Not Found"}
    fulfillment(lambda req: httpx.Response(404, json=body))
    r = await client.get("/api/v1/buyer/orders/SO-NOPE", headers=h)
    assert r.status_code == 503 and r.json()["code"] == 51001


@pytest.mark.asyncio
async def test_total_timeout_budget(client, fulfillment, monkeypatch):
    """asyncio.timeout 兜整个请求:传输拖过预算即 503,不受 httpx 分阶段超时叠加影响。"""
    import asyncio
    from app.services import fulfillment_client as fc_mod
    monkeypatch.setattr(fc_mod, "TIMEOUT_SECONDS", 0.05)
    h, _, _ = await _buyer(client)

    async def slow(request: httpx.Request) -> httpx.Response:
        await asyncio.sleep(0.3)
        return httpx.Response(200, json=_envelope(_LIST_PAGE))

    fulfillment(slow)
    r = await client.get("/api/v1/buyer/orders", headers=h)
    assert r.status_code == 503 and r.json()["code"] == 51001


@pytest.mark.asyncio
async def test_list_404_is_unavailable_not_not_found(client, fulfillment):
    """列表端点不可能 404;出现即视为履约配置错/不可用,不能给用户"订单不存在"。"""
    h, _, _ = await _buyer(client)
    fulfillment(lambda req: httpx.Response(404, json=_envelope(None, 40000)))
    r = await client.get("/api/v1/buyer/orders", headers=h)
    assert r.status_code == 503 and r.json()["code"] == 51001


@pytest.mark.asyncio
async def test_unconfigured_integration_returns_503(client):
    """互通未配置 = lifespan 没建单例(测试不跑 lifespan,等价);不覆盖依赖直接打 → 503。"""
    h, _, _ = await _buyer(client)
    r = await client.get("/api/v1/buyer/orders", headers=h)
    assert r.status_code == 503 and r.json()["code"] == 51001


@pytest.mark.asyncio
@pytest.mark.parametrize("data", [None, [], "x", 0])
async def test_non_object_data_is_503(client, fulfillment, data):
    """履约 {code:0,data:null} 之类不透传,否则前端在解构处崩。"""
    h, _, _ = await _buyer(client)
    fulfillment(lambda req: httpx.Response(200, json=_envelope(data)))
    r = await client.get("/api/v1/buyer/orders", headers=h)
    assert r.status_code == 503 and r.json()["code"] == 51001


@pytest.mark.asyncio
@pytest.mark.parametrize("q", ["a", "%20a", "a%20", "%20%20"])
async def test_internal_search_requires_two_chars_after_strip(client, q):
    r = await client.get(f"/api/v1/internal/buyer-organizations?q={q}", headers=_fulfillment_headers())
    assert r.status_code == 422, r.text


@pytest.mark.asyncio
async def test_internal_search_strips_surrounding_space(client):
    _, _, org_id = await _buyer(client, "Zanzibar Steel")
    r = await client.get("/api/v1/internal/buyer-organizations?q=%20zanzibar%20", headers=_fulfillment_headers())
    assert r.status_code == 200 and [o["id"] for o in r.json()["data"]] == [org_id]


@pytest.mark.asyncio
async def test_orders_require_login(client):
    r = await client.get("/api/v1/buyer/orders")
    assert r.status_code == 401


# ── 内部路由:令牌门 ───────────────────────────────────────

def _fulfillment_headers() -> dict:
    token, _ = sign_s2s_token(iss=ISS_FULFILLMENT, aud=AUD_MATGO_INTERNAL, sub="svc:fulfillment")
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_internal_requires_token(client):
    r = await client.get("/api/v1/internal/buyer-organizations?q=ab")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_internal_rejects_wrong_aud_reverse_replay(client):
    token, _ = sign_s2s_token(iss=ISS_MATGO, aud=AUD_FULFILLMENT_PORTAL, sub="org:1")
    r = await client.get("/api/v1/internal/buyer-organizations?q=ab", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_internal_rejects_wrong_iss(client):
    token, _ = sign_s2s_token(iss=ISS_MATGO, aud=AUD_MATGO_INTERNAL, sub="svc:fulfillment")
    r = await client.get("/api/v1/internal/buyer-organizations/1", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_internal_rejects_user_access_token(client):
    """前台登录 access token 不是 S2S 令牌(密钥/claims 都不同)。"""
    h, _, _ = await _buyer(client)
    r = await client.get("/api/v1/internal/buyer-organizations?q=ab", headers=h)
    assert r.status_code == 401


# ── 内部路由:搜索 / 取单 ──────────────────────────────────

@pytest.mark.asyncio
async def test_internal_search_and_get(client):
    _, _, org_id = await _buyer(client, "Kilimanjaro Builders Ltd")
    h = _fulfillment_headers()

    r = await client.get("/api/v1/internal/buyer-organizations?q=kilimanjaro&limit=5", headers=h)
    assert r.status_code == 200, r.text
    hits = r.json()["data"]
    assert [o["id"] for o in hits] == [org_id]
    assert set(hits[0].keys()) == {"id", "name", "code", "status"}  # 不回成员 / 联系方式
    assert hits[0]["status"] == "ACTIVE"

    r = await client.get(f"/api/v1/internal/buyer-organizations/{org_id}", headers=h)
    assert r.status_code == 200
    assert r.json()["data"]["name"] == "Kilimanjaro Builders Ltd"

    r = await client.get("/api/v1/internal/buyer-organizations/999999999", headers=h)
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_internal_search_escapes_like_wildcards_and_caps_limit(client):
    await _buyer(client, "Percent Co")
    h = _fulfillment_headers()
    r = await client.get("/api/v1/internal/buyer-organizations?q=%25%25", headers=h)  # q="%%"
    assert r.status_code == 200
    assert r.json()["data"] == []  # 通配符被转义成字面量,不匹配任何名字
    r = await client.get("/api/v1/internal/buyer-organizations?q=co&limit=50", headers=h)
    assert r.status_code == 422  # limit ≤ 20
