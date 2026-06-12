"""报价回填 API 单测。

覆盖:首报/重报/单 ACTIVE/版本唯一、行校验(不属/重复/缺行)、
accept/reject/expire 守卫+幂等+锁内回钉、买方 DTO 隔离(无 cost/supplier)、
scope 越权(404)、报价读取(角色分离)、详情层叠。
"""
from __future__ import annotations

from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.category import Category
from app.db.models.rfq import Rfq, RfqStatus


# ── helpers ─────────────────────────────────────────────

_BUYER_EMAIL = "buyer@cscec3b.local"
_BUYER_PASSWORD = "Aa123456789"
_OPERATOR_EMAIL = "operator@platform.local"
_OPERATOR_PASSWORD = "Aa123456789"


async def _login(client: AsyncClient, email: str, password: str) -> dict[str, str]:
    r = await client.post("/api/v1/auth/login", json={
        "identifier": email, "password": password,
    })
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['data']['access_token']}"}


async def _buyer_headers(client: AsyncClient) -> dict[str, str]:
    return await _login(client, _BUYER_EMAIL, _BUYER_PASSWORD)


async def _op_headers(client: AsyncClient) -> dict[str, str]:
    return await _login(client, _OPERATOR_EMAIL, _OPERATOR_PASSWORD)


async def _buyer_info(client: AsyncClient, headers: dict) -> dict:
    r = await client.get("/api/v1/auth/me", headers=headers)
    assert r.status_code == 200
    return r.json()["data"]


async def _create_purchasable_sku(
    client: AsyncClient, op: dict, db: AsyncSession,
) -> int:
    """创建一个可购 SKU(ACTIVE SPU + ACTIVE SKU),返回 sku_id。"""
    cat = (await db.execute(
        select(Category).where(Category.level == 3).limit(1)
    )).scalar_one_or_none()
    assert cat is not None

    r = await client.post("/api/v1/operator/products", headers=op, json={
        "name": "Quote Test Product",
        "category_code": cat.code,
        "unit": "PCS",
        "currency": "USD",
    })
    assert r.status_code == 200, r.text
    product_id = r.json()["data"]["id"]

    r = await client.post(
        f"/api/v1/operator/products/{product_id}/skus",
        headers=op,
        json={"name": "Quote Test SKU", "moq": 1, "price_min": 100, "price_max": 200},
    )
    assert r.status_code == 200, r.text
    sku_id = r.json()["data"]["id"]

    r = await client.patch(
        f"/api/v1/operator/products/{product_id}/status?force=true",
        headers=op,
        json={"status": "ACTIVE"},
    )
    assert r.status_code == 200, r.text
    return sku_id


async def _create_submitted_rfq(
    client: AsyncClient, bh: dict, op: dict, db: AsyncSession,
    *, num_items: int = 1,
) -> tuple[int, list[int]]:
    """创建 SUBMITTED RFQ,返回 (rfq_id, [rfq_item_ids])。"""
    sku_ids = []
    for _ in range(num_items):
        sku_ids.append(await _create_purchasable_sku(client, op, db))

    items = [{"sku_id": sid, "quantity": "10.000"} for sid in sku_ids]
    r = await client.post("/api/v1/rfqs", headers=bh, json={
        "items": items,
    })
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    rfq_id = data["id"]
    rfq_item_ids = [it["id"] for it in data["items"]]
    return rfq_id, rfq_item_ids


async def _create_processing_rfq(
    client: AsyncClient, bh: dict, op: dict, db: AsyncSession,
    *, num_items: int = 1,
) -> tuple[int, list[int]]:
    """创建 PROCESSING RFQ（运营已受理），返回 (rfq_id, [rfq_item_ids])。"""
    rfq_id, rfq_item_ids = await _create_submitted_rfq(
        client, bh, op, db, num_items=num_items,
    )
    r = await client.patch(f"/api/v1/rfqs/{rfq_id}/claim", headers=op)
    assert r.status_code == 200, r.text
    assert r.json()["data"]["status"] == "PROCESSING"
    return rfq_id, rfq_item_ids


def _build_quote_payload(
    rfq_item_ids: list[int],
    unit_price: str = "25.0000",
    *,
    with_tiers: bool = False,
    with_cost: bool = False,
) -> dict:
    """构建报价请求体。"""
    lines = []
    for item_id in rfq_item_ids:
        line: dict = {"rfq_item_id": item_id, "unit_price": unit_price}
        if with_tiers:
            line["tiers"] = [
                {"min_qty": "10.000", "unit_price": "25.0000"},
                {"min_qty": "50.000", "unit_price": "22.0000"},
            ]
        if with_cost:
            line["cost"] = {
                "supplier_unit_price": "15.0000",
                "freight_cost_alloc": "2.0000",
                "gross_margin": "8.0000",
            }
        lines.append(line)
    return {
        "header": {
            "trade_term": "FOB",
            "currency": "USD",
            "lead_time_days": 30,
            "eta_days": 45,
        },
        "lines": lines,
    }


# ── 首报 ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_first_quote_success(client, db_session):
    """首报:SUBMITTED → v1 ACTIVE + RFQ→QUOTED。"""
    bh = await _buyer_headers(client)
    op = await _op_headers(client)
    rfq_id, item_ids = await _create_processing_rfq(client, bh, op, db_session)

    payload = _build_quote_payload(item_ids, with_tiers=True, with_cost=True)
    r = await client.post(f"/api/v1/rfqs/{rfq_id}/quotes", headers=op, json=payload)
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["version"] == 1
    assert data["quote_status"] == "ACTIVE"
    assert data["quote_no"].startswith("Q-")
    assert len(data["items"]) == len(item_ids)
    # line_amount = unit_price * quantity (10)
    assert Decimal(data["items"][0]["line_amount"]) == Decimal("250.0000")
    assert Decimal(data["total_amount"]) == Decimal("250.0000") * len(item_ids)
    # tiers
    assert len(data["items"][0]["tiers"]) == 2
    # cost(运营可见）
    assert data["items"][0]["cost"] is not None
    assert Decimal(str(data["items"][0]["cost"]["supplier_unit_price"])) == Decimal("15.0000")

    # 验 RFQ 状态已转 QUOTED
    r2 = await client.get(f"/api/v1/rfqs/{rfq_id}", headers=op)
    assert r2.json()["data"]["status"] == "QUOTED"


@pytest.mark.asyncio
async def test_first_quote_non_submitted_rejected(client, db_session):
    """非 PROCESSING RFQ（已撤销）→ 40510。"""
    bh = await _buyer_headers(client)
    op = await _op_headers(client)
    rfq_id, item_ids = await _create_submitted_rfq(client, bh, op, db_session)

    # 买方撤销（SUBMITTED 态可撤销）
    await client.patch(f"/api/v1/rfqs/{rfq_id}/cancel", headers=bh)

    payload = _build_quote_payload(item_ids)
    r = await client.post(f"/api/v1/rfqs/{rfq_id}/quotes", headers=op, json=payload)
    assert r.status_code == 409
    assert r.json()["code"] == 40510


# ── 重报 ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_requote_version_increment(client, db_session):
    """重报:旧 ACTIVE→SUPERSEDED,新 v2 ACTIVE,RFQ 仍 QUOTED。"""
    bh = await _buyer_headers(client)
    op = await _op_headers(client)
    rfq_id, item_ids = await _create_processing_rfq(client, bh, op, db_session)

    # 首报
    p1 = _build_quote_payload(item_ids, "25.0000")
    r1 = await client.post(f"/api/v1/rfqs/{rfq_id}/quotes", headers=op, json=p1)
    assert r1.status_code == 200
    v1_id = r1.json()["data"]["id"]

    # 重报
    p2 = _build_quote_payload(item_ids, "22.0000")
    r2 = await client.post(f"/api/v1/rfqs/{rfq_id}/quotes", headers=op, json=p2)
    assert r2.status_code == 200
    data2 = r2.json()["data"]
    assert data2["version"] == 2
    assert data2["quote_status"] == "ACTIVE"

    # 验全版本列表(运营)
    r3 = await client.get(f"/api/v1/rfqs/{rfq_id}/quotes", headers=op)
    quotes = r3.json()["data"]
    assert len(quotes) == 2
    statuses = {q["version"]: q["quote_status"] for q in quotes}
    assert statuses[1] == "SUPERSEDED"
    assert statuses[2] == "ACTIVE"


@pytest.mark.asyncio
async def test_requote_multiple_items(client, db_session):
    """多行重报:验证金额计算正确。"""
    bh = await _buyer_headers(client)
    op = await _op_headers(client)
    rfq_id, item_ids = await _create_processing_rfq(client, bh, op, db_session, num_items=2)

    # 首报
    p1 = _build_quote_payload(item_ids, "20.0000")
    await client.post(f"/api/v1/rfqs/{rfq_id}/quotes", headers=op, json=p1)

    # 重报
    p2 = _build_quote_payload(item_ids, "18.0000")
    r2 = await client.post(f"/api/v1/rfqs/{rfq_id}/quotes", headers=op, json=p2)
    assert r2.status_code == 200
    # total = 18 * 10 * 2 items = 360
    assert Decimal(r2.json()["data"]["total_amount"]) == Decimal("360.0000")


# ── 行校验 ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_quote_item_not_in_rfq(client, db_session):
    """报价行不属本 RFQ → 40512。"""
    bh = await _buyer_headers(client)
    op = await _op_headers(client)
    rfq_id, item_ids = await _create_processing_rfq(client, bh, op, db_session)

    payload = _build_quote_payload([999999])
    r = await client.post(f"/api/v1/rfqs/{rfq_id}/quotes", headers=op, json=payload)
    assert r.status_code == 422
    assert r.json()["code"] == 40512


@pytest.mark.asyncio
async def test_quote_duplicate_item(client, db_session):
    """报价行重复 → 40512。"""
    bh = await _buyer_headers(client)
    op = await _op_headers(client)
    rfq_id, item_ids = await _create_processing_rfq(client, bh, op, db_session)

    payload = {
        "header": {"currency": "USD"},
        "lines": [
            {"rfq_item_id": item_ids[0], "unit_price": "25.0000"},
            {"rfq_item_id": item_ids[0], "unit_price": "25.0000"},
        ],
    }
    r = await client.post(f"/api/v1/rfqs/{rfq_id}/quotes", headers=op, json=payload)
    assert r.status_code == 422
    assert r.json()["code"] == 40512


@pytest.mark.asyncio
async def test_quote_incomplete_lines(client, db_session):
    """报价未覆盖全部 rfq_items → 40513。"""
    bh = await _buyer_headers(client)
    op = await _op_headers(client)
    rfq_id, item_ids = await _create_processing_rfq(client, bh, op, db_session, num_items=2)

    # 只报第一行
    payload = _build_quote_payload([item_ids[0]])
    r = await client.post(f"/api/v1/rfqs/{rfq_id}/quotes", headers=op, json=payload)
    assert r.status_code == 422
    assert r.json()["code"] == 40513


# ── 接受 ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_accept_success(client, db_session):
    """QUOTED→ACCEPTED + accepted_quote_id 钉。"""
    bh = await _buyer_headers(client)
    op = await _op_headers(client)
    rfq_id, item_ids = await _create_processing_rfq(client, bh, op, db_session)

    # 首报
    p = _build_quote_payload(item_ids)
    r1 = await client.post(f"/api/v1/rfqs/{rfq_id}/quotes", headers=op, json=p)
    quote_id = r1.json()["data"]["id"]

    # 买方接受
    r = await client.patch(f"/api/v1/rfqs/{rfq_id}/accept", headers=bh)
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["status"] == "ACCEPTED"
    assert data["accepted_quote_id"] == quote_id


@pytest.mark.asyncio
async def test_accept_idempotent(client, db_session):
    """已 ACCEPTED → 幂等返回,不重复写审计。"""
    bh = await _buyer_headers(client)
    op = await _op_headers(client)
    rfq_id, item_ids = await _create_processing_rfq(client, bh, op, db_session)

    p = _build_quote_payload(item_ids)
    await client.post(f"/api/v1/rfqs/{rfq_id}/quotes", headers=op, json=p)

    # 接受两次
    r1 = await client.patch(f"/api/v1/rfqs/{rfq_id}/accept", headers=bh)
    assert r1.status_code == 200
    r2 = await client.patch(f"/api/v1/rfqs/{rfq_id}/accept", headers=bh)
    assert r2.status_code == 200
    assert r2.json()["data"]["status"] == "ACCEPTED"


@pytest.mark.asyncio
async def test_accept_non_quoted_rejected(client, db_session):
    """非 QUOTED → 40508。"""
    bh = await _buyer_headers(client)
    op = await _op_headers(client)
    rfq_id, _ = await _create_processing_rfq(client, bh, op, db_session)

    # PROCESSING 状态下不能接受
    r = await client.patch(f"/api/v1/rfqs/{rfq_id}/accept", headers=bh)
    assert r.status_code == 409
    assert r.json()["code"] == 40508


@pytest.mark.asyncio
async def test_operator_accept_proxy(client, db_session):
    """运营代客接受。"""
    bh = await _buyer_headers(client)
    op = await _op_headers(client)
    rfq_id, item_ids = await _create_processing_rfq(client, bh, op, db_session)

    p = _build_quote_payload(item_ids)
    await client.post(f"/api/v1/rfqs/{rfq_id}/quotes", headers=op, json=p)

    r = await client.patch(f"/api/v1/rfqs/{rfq_id}/accept", headers=op)
    assert r.status_code == 200
    assert r.json()["data"]["status"] == "ACCEPTED"


# ── 拒绝 ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_reject_success(client, db_session):
    """QUOTED→REJECTED。"""
    bh = await _buyer_headers(client)
    op = await _op_headers(client)
    rfq_id, item_ids = await _create_processing_rfq(client, bh, op, db_session)

    p = _build_quote_payload(item_ids)
    await client.post(f"/api/v1/rfqs/{rfq_id}/quotes", headers=op, json=p)

    r = await client.patch(f"/api/v1/rfqs/{rfq_id}/reject", headers=bh)
    assert r.status_code == 200
    assert r.json()["data"]["status"] == "REJECTED"


@pytest.mark.asyncio
async def test_reject_idempotent(client, db_session):
    """已 REJECTED → 幂等。"""
    bh = await _buyer_headers(client)
    op = await _op_headers(client)
    rfq_id, item_ids = await _create_processing_rfq(client, bh, op, db_session)

    p = _build_quote_payload(item_ids)
    await client.post(f"/api/v1/rfqs/{rfq_id}/quotes", headers=op, json=p)

    await client.patch(f"/api/v1/rfqs/{rfq_id}/reject", headers=bh)
    r2 = await client.patch(f"/api/v1/rfqs/{rfq_id}/reject", headers=bh)
    assert r2.status_code == 200
    assert r2.json()["data"]["status"] == "REJECTED"


# ── 失效 ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_expire_success(client, db_session):
    """QUOTED→EXPIRED。"""
    bh = await _buyer_headers(client)
    op = await _op_headers(client)
    rfq_id, item_ids = await _create_processing_rfq(client, bh, op, db_session)

    p = _build_quote_payload(item_ids)
    await client.post(f"/api/v1/rfqs/{rfq_id}/quotes", headers=op, json=p)

    r = await client.patch(f"/api/v1/rfqs/{rfq_id}/expire", headers=op)
    assert r.status_code == 200
    assert r.json()["data"]["status"] == "EXPIRED"


@pytest.mark.asyncio
async def test_expire_idempotent(client, db_session):
    """已 EXPIRED → 幂等。"""
    bh = await _buyer_headers(client)
    op = await _op_headers(client)
    rfq_id, item_ids = await _create_processing_rfq(client, bh, op, db_session)

    p = _build_quote_payload(item_ids)
    await client.post(f"/api/v1/rfqs/{rfq_id}/quotes", headers=op, json=p)

    await client.patch(f"/api/v1/rfqs/{rfq_id}/expire", headers=op)
    r2 = await client.patch(f"/api/v1/rfqs/{rfq_id}/expire", headers=op)
    assert r2.status_code == 200
    assert r2.json()["data"]["status"] == "EXPIRED"


@pytest.mark.asyncio
async def test_expire_non_quoted_rejected(client, db_session):
    """非 QUOTED → 40508。"""
    bh = await _buyer_headers(client)
    op = await _op_headers(client)
    rfq_id, _ = await _create_processing_rfq(client, bh, op, db_session)

    r = await client.patch(f"/api/v1/rfqs/{rfq_id}/expire", headers=op)
    assert r.status_code == 409
    assert r.json()["code"] == 40508


# ── 报价读取(角色分离)──────────────────────────────────


@pytest.mark.asyncio
async def test_buyer_get_quotes_only_active(client, db_session):
    """BUYER 仅看 ACTIVE。"""
    bh = await _buyer_headers(client)
    op = await _op_headers(client)
    rfq_id, item_ids = await _create_processing_rfq(client, bh, op, db_session)

    # 首报 + 重报
    p1 = _build_quote_payload(item_ids, "25.0000")
    await client.post(f"/api/v1/rfqs/{rfq_id}/quotes", headers=op, json=p1)
    p2 = _build_quote_payload(item_ids, "22.0000")
    await client.post(f"/api/v1/rfqs/{rfq_id}/quotes", headers=op, json=p2)

    r = await client.get(f"/api/v1/rfqs/{rfq_id}/quotes", headers=bh)
    assert r.status_code == 200
    quotes = r.json()["data"]
    assert len(quotes) == 1  # 仅 ACTIVE
    assert quotes[0]["quote_no"].startswith("Q-")


@pytest.mark.asyncio
async def test_operator_get_quotes_all_versions(client, db_session):
    """OPERATOR 看全版本。"""
    bh = await _buyer_headers(client)
    op = await _op_headers(client)
    rfq_id, item_ids = await _create_processing_rfq(client, bh, op, db_session)

    p1 = _build_quote_payload(item_ids, "25.0000")
    await client.post(f"/api/v1/rfqs/{rfq_id}/quotes", headers=op, json=p1)
    p2 = _build_quote_payload(item_ids, "22.0000")
    await client.post(f"/api/v1/rfqs/{rfq_id}/quotes", headers=op, json=p2)

    r = await client.get(f"/api/v1/rfqs/{rfq_id}/quotes", headers=op)
    quotes = r.json()["data"]
    assert len(quotes) == 2


# ── DTO 隔离(买方无 cost/supplier)──────────────────────


@pytest.mark.asyncio
async def test_buyer_quote_no_cost_fields(client, db_session):
    """买方 DTO 不含 cost/supplier/quoted_by/版本。"""
    bh = await _buyer_headers(client)
    op = await _op_headers(client)
    rfq_id, item_ids = await _create_processing_rfq(client, bh, op, db_session)

    payload = _build_quote_payload(item_ids, with_cost=True)
    await client.post(f"/api/v1/rfqs/{rfq_id}/quotes", headers=op, json=payload)

    r = await client.get(f"/api/v1/rfqs/{rfq_id}/quotes", headers=bh)
    assert r.status_code == 200
    quote = r.json()["data"][0]
    # 买方无这些字段
    assert "cost" not in quote["items"][0] or quote["items"][0].get("cost") is None
    assert "quoted_by_user_id" not in quote
    assert "version" not in quote
    assert "quote_status" not in quote

    # 深层检查:整个 JSON 不含 supplier
    import json
    raw = json.dumps(quote).lower()
    assert "supplier" not in raw
    assert "gross_margin" not in raw


# ── 详情层叠 ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_rfq_detail_buyer_has_quote(client, db_session):
    """买方 RFQ 详情层叠 ACTIVE 报价。"""
    bh = await _buyer_headers(client)
    op = await _op_headers(client)
    rfq_id, item_ids = await _create_processing_rfq(client, bh, op, db_session)

    p = _build_quote_payload(item_ids)
    await client.post(f"/api/v1/rfqs/{rfq_id}/quotes", headers=op, json=p)

    r = await client.get(f"/api/v1/rfqs/{rfq_id}", headers=bh)
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["quote"] is not None
    assert data["quote"]["quote_no"].startswith("Q-")


@pytest.mark.asyncio
async def test_rfq_detail_buyer_no_quote(client, db_session):
    """买方 RFQ 详情无报价 → quote=null。"""
    bh = await _buyer_headers(client)
    op = await _op_headers(client)
    rfq_id, _ = await _create_processing_rfq(client, bh, op, db_session)

    r = await client.get(f"/api/v1/rfqs/{rfq_id}", headers=bh)
    assert r.status_code == 200
    assert r.json()["data"]["quote"] is None


@pytest.mark.asyncio
async def test_rfq_detail_operator_has_quotes_list(client, db_session):
    """运营 RFQ 详情层叠全版本列表。"""
    bh = await _buyer_headers(client)
    op = await _op_headers(client)
    rfq_id, item_ids = await _create_processing_rfq(client, bh, op, db_session)

    p1 = _build_quote_payload(item_ids, "25.0000")
    await client.post(f"/api/v1/rfqs/{rfq_id}/quotes", headers=op, json=p1)
    p2 = _build_quote_payload(item_ids, "22.0000")
    await client.post(f"/api/v1/rfqs/{rfq_id}/quotes", headers=op, json=p2)

    r = await client.get(f"/api/v1/rfqs/{rfq_id}", headers=op)
    data = r.json()["data"]
    assert "quotes" in data
    assert len(data["quotes"]) == 2


# ── scope 越权 ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_buyer_cannot_create_quote(client, db_session):
    """BUYER 无 quote:write 权限 → 403。"""
    bh = await _buyer_headers(client)
    op = await _op_headers(client)
    rfq_id, item_ids = await _create_processing_rfq(client, bh, op, db_session)

    payload = _build_quote_payload(item_ids)
    r = await client.post(f"/api/v1/rfqs/{rfq_id}/quotes", headers=bh, json=payload)
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_quote_rfq_not_found(client, db_session):
    """RFQ 不存在 → 40507/404。"""
    op = await _op_headers(client)

    payload = {"header": {}, "lines": [{"rfq_item_id": 1, "unit_price": "10.0000"}]}
    r = await client.post("/api/v1/rfqs/999999/quotes", headers=op, json=payload)
    assert r.status_code == 404
    assert r.json()["code"] == 40507


@pytest.mark.asyncio
async def test_get_quotes_rfq_not_found(client, db_session):
    """GET 报价列表 RFQ 不存在 → 404。"""
    bh = await _buyer_headers(client)
    r = await client.get("/api/v1/rfqs/999999/quotes", headers=bh)
    assert r.status_code == 404


# ── ADMIN 拒绝 ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_admin_cannot_access_quotes(client, superadmin_headers, db_session):
    """ADMIN → 403。"""
    r = await client.get("/api/v1/rfqs/1/quotes", headers=superadmin_headers)
    assert r.status_code == 403


# ── trade_term / currency 枚举校验 ───────────────────────


@pytest.mark.asyncio
async def test_quote_valid_trade_term_and_currency(client, db_session):
    """合法枚举码正常通过。"""
    bh = await _buyer_headers(client)
    op = await _op_headers(client)
    rfq_id, item_ids = await _create_processing_rfq(client, bh, op, db_session)

    payload = _build_quote_payload(item_ids)
    payload["header"]["trade_term"] = "FOB"
    payload["header"]["currency"] = "USD"
    r = await client.post(f"/api/v1/rfqs/{rfq_id}/quotes", headers=op, json=payload)
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["trade_term"] == "FOB"
    assert data["currency"] == "USD"


@pytest.mark.asyncio
async def test_quote_invalid_trade_term_rejected(client, db_session):
    """非法 trade_term → 422。"""
    bh = await _buyer_headers(client)
    op = await _op_headers(client)
    rfq_id, item_ids = await _create_processing_rfq(client, bh, op, db_session)

    payload = _build_quote_payload(item_ids)
    payload["header"]["trade_term"] = "EXW"
    r = await client.post(f"/api/v1/rfqs/{rfq_id}/quotes", headers=op, json=payload)
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_quote_invalid_currency_rejected(client, db_session):
    """非法 currency → 422。"""
    bh = await _buyer_headers(client)
    op = await _op_headers(client)
    rfq_id, item_ids = await _create_processing_rfq(client, bh, op, db_session)

    payload = _build_quote_payload(item_ids)
    payload["header"]["currency"] = "EUR"
    r = await client.post(f"/api/v1/rfqs/{rfq_id}/quotes", headers=op, json=payload)
    assert r.status_code == 422
