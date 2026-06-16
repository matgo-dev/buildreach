"""报价回填 API 单测 — 独立报价行 PRODUCT/FEE。

覆盖:首报/重报、PRODUCT+FEE 行、总金额、买方 DTO 隔离、scope 越权、
accept/reject/expire。
"""
from __future__ import annotations

from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.category import Category


# ── helpers ─────────────────────────────────────────────

_BUYER_EMAIL = "buyer@cscec3b.local"
_BUYER_PASSWORD = "Aa123456789"
_OPERATOR_EMAIL = "operator@platform.local"
_OPERATOR_PASSWORD = "Aa123456789"


async def _login(client: AsyncClient, email: str, password: str) -> dict[str, str]:
    r = await client.post("/api/v1/auth/login", json={"identifier": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['data']['access_token']}"}

async def _buyer_headers(client): return await _login(client, _BUYER_EMAIL, _BUYER_PASSWORD)
async def _op_headers(client): return await _login(client, _OPERATOR_EMAIL, _OPERATOR_PASSWORD)


async def _create_active_product(client: AsyncClient, op: dict, db: AsyncSession) -> int:
    cat = (await db.execute(select(Category).where(Category.level == 3).limit(1))).scalar_one_or_none()
    assert cat is not None
    r = await client.post("/api/v1/operator/products", headers=op, json={
        "name": "Quote Test Product", "category_code": cat.code, "unit": "PCS", "currency": "USD",
    })
    assert r.status_code == 200, r.text
    pid = r.json()["data"]["id"]
    r = await client.post(f"/api/v1/operator/products/{pid}/skus", headers=op,
        json={"name": "Test SKU", "moq": 1, "price_min": 100, "price_max": 200})
    assert r.status_code == 200, r.text
    r = await client.patch(f"/api/v1/operator/products/{pid}/status?force=true", headers=op, json={"status": "ACTIVE"})
    assert r.status_code == 200, r.text
    return pid


async def _create_processing_rfq(client, bh, op, db, *, num_items=1):
    pids = [await _create_active_product(client, op, db) for _ in range(num_items)]
    items = [{"product_id": pid, "selected_variants": [], "quantity": "10.000"} for pid in pids]
    r = await client.post("/api/v1/rfqs", headers=bh, json={"items": items})
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    rfq_id = data["id"]
    item_ids = [it["id"] for it in data["items"]]
    r = await client.patch(f"/api/v1/rfqs/{rfq_id}/claim", headers=op)
    assert r.status_code == 200, r.text
    return rfq_id, item_ids, pids


def _build_payload(item_ids, pids, price="25.0000", *, with_tiers=False, with_cost=False):
    lines = []
    for iid, pid in zip(item_ids, pids):
        line = {"source_rfq_item_id": iid, "line_type": "PRODUCT", "product_id": pid,
                "quantity": "10.000", "uom": "PCS", "unit_price": price}
        if with_tiers:
            line["tiers"] = [{"min_qty": "10", "unit_price": "25"}, {"min_qty": "50", "unit_price": "22"}]
        if with_cost:
            line["cost"] = {"supplier_unit_price": "15", "freight_cost_alloc": "2", "gross_margin": "8"}
        lines.append(line)
    return {"header": {"trade_term": "FOB", "currency": "USD", "lead_time_days": 30, "eta_days": 45}, "lines": lines}


# ── 首报 ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_first_quote_success(client, db_session):
    bh, op = await _buyer_headers(client), await _op_headers(client)
    rfq_id, iids, pids = await _create_processing_rfq(client, bh, op, db_session)
    payload = _build_payload(iids, pids, with_tiers=True, with_cost=True)
    r = await client.post(f"/api/v1/rfqs/{rfq_id}/quotes", headers=op, json=payload)
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["version"] == 1
    assert data["quote_status"] == "ACTIVE"
    assert data["items"][0]["line_type"] == "PRODUCT"
    assert data["items"][0]["product_id"] == pids[0]
    assert Decimal(data["items"][0]["line_amount"]) == Decimal("250.0000")
    assert len(data["items"][0]["tiers"]) == 2
    assert data["items"][0]["cost"] is not None

    r2 = await client.get(f"/api/v1/rfqs/{rfq_id}", headers=op)
    assert r2.json()["data"]["status"] == "QUOTED"


# ── PRODUCT + FEE 混合 ──────────────────────────────────

@pytest.mark.asyncio
async def test_product_and_fee_lines(client, db_session):
    bh, op = await _buyer_headers(client), await _op_headers(client)
    rfq_id, iids, pids = await _create_processing_rfq(client, bh, op, db_session)
    payload = {
        "header": {"currency": "USD"},
        "lines": [
            {"source_rfq_item_id": iids[0], "line_type": "PRODUCT", "product_id": pids[0],
             "quantity": "10", "unit_price": "25.00"},
            {"line_type": "FEE", "product_name": "包装费", "quantity": "1", "unit_price": "500.00"},
            {"line_type": "FEE", "product_name": "运费", "quantity": "1", "unit_price": "800.00"},
        ],
    }
    r = await client.post(f"/api/v1/rfqs/{rfq_id}/quotes", headers=op, json=payload)
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert len(data["items"]) == 3
    fee_items = [it for it in data["items"] if it["line_type"] == "FEE"]
    assert len(fee_items) == 2
    assert fee_items[0]["source_rfq_item_id"] is None
    # 25*10 + 500 + 800 = 1550
    assert Decimal(data["total_amount"]) == Decimal("1550.0000")


# ── 不覆盖全部询价行也能提交（无严格覆盖校验）──────────────

@pytest.mark.asyncio
async def test_partial_coverage_ok(client, db_session):
    """只报一部分询价行，不报的不需要标 SKIPPED，直接不提交。"""
    bh, op = await _buyer_headers(client), await _op_headers(client)
    rfq_id, iids, pids = await _create_processing_rfq(client, bh, op, db_session, num_items=2)
    payload = {
        "header": {"currency": "USD"},
        "lines": [{"source_rfq_item_id": iids[0], "line_type": "PRODUCT", "product_id": pids[0],
                    "quantity": "10", "unit_price": "25.00"}],
    }
    r = await client.post(f"/api/v1/rfqs/{rfq_id}/quotes", headers=op, json=payload)
    assert r.status_code == 200, r.text
    assert len(r.json()["data"]["items"]) == 1


# ── 校验 ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_empty_lines_rejected(client, db_session):
    bh, op = await _buyer_headers(client), await _op_headers(client)
    rfq_id, _, _ = await _create_processing_rfq(client, bh, op, db_session)
    r = await client.post(f"/api/v1/rfqs/{rfq_id}/quotes", headers=op,
        json={"header": {"currency": "USD"}, "lines": []})
    assert r.status_code == 422
    assert r.json()["code"] == 40513


@pytest.mark.asyncio
async def test_invalid_source(client, db_session):
    bh, op = await _buyer_headers(client), await _op_headers(client)
    rfq_id, _, pids = await _create_processing_rfq(client, bh, op, db_session)
    r = await client.post(f"/api/v1/rfqs/{rfq_id}/quotes", headers=op, json={
        "header": {"currency": "USD"},
        "lines": [{"source_rfq_item_id": 999999, "line_type": "PRODUCT", "product_id": pids[0],
                    "quantity": "10", "unit_price": "25"}],
    })
    assert r.status_code == 422
    assert r.json()["code"] == 40512


@pytest.mark.asyncio
async def test_product_without_product_id(client, db_session):
    bh, op = await _buyer_headers(client), await _op_headers(client)
    rfq_id, iids, _ = await _create_processing_rfq(client, bh, op, db_session)
    r = await client.post(f"/api/v1/rfqs/{rfq_id}/quotes", headers=op, json={
        "header": {"currency": "USD"},
        "lines": [{"source_rfq_item_id": iids[0], "line_type": "PRODUCT", "quantity": "10", "unit_price": "25"}],
    })
    assert r.status_code == 422
    assert r.json()["code"] == 40512


@pytest.mark.asyncio
async def test_missing_price(client, db_session):
    bh, op = await _buyer_headers(client), await _op_headers(client)
    rfq_id, iids, pids = await _create_processing_rfq(client, bh, op, db_session)
    r = await client.post(f"/api/v1/rfqs/{rfq_id}/quotes", headers=op, json={
        "header": {"currency": "USD"},
        "lines": [{"source_rfq_item_id": iids[0], "line_type": "PRODUCT", "product_id": pids[0], "quantity": "10"}],
    })
    assert r.status_code == 422
    assert r.json()["code"] == 40514


# ── 重报 ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_requote(client, db_session):
    bh, op = await _buyer_headers(client), await _op_headers(client)
    rfq_id, iids, pids = await _create_processing_rfq(client, bh, op, db_session)
    p1 = _build_payload(iids, pids, "25")
    await client.post(f"/api/v1/rfqs/{rfq_id}/quotes", headers=op, json=p1)
    p2 = _build_payload(iids, pids, "22")
    r2 = await client.post(f"/api/v1/rfqs/{rfq_id}/quotes", headers=op, json=p2)
    assert r2.status_code == 200
    assert r2.json()["data"]["version"] == 2
    r3 = await client.get(f"/api/v1/rfqs/{rfq_id}/quotes", headers=op)
    statuses = {q["version"]: q["quote_status"] for q in r3.json()["data"]}
    assert statuses[1] == "SUPERSEDED" and statuses[2] == "ACTIVE"


# ── accept/reject/expire ─────────────────────────────

@pytest.mark.asyncio
async def test_accept(client, db_session):
    bh, op = await _buyer_headers(client), await _op_headers(client)
    rfq_id, iids, pids = await _create_processing_rfq(client, bh, op, db_session)
    await client.post(f"/api/v1/rfqs/{rfq_id}/quotes", headers=op, json=_build_payload(iids, pids))
    r = await client.patch(f"/api/v1/rfqs/{rfq_id}/accept", headers=bh)
    assert r.status_code == 200 and r.json()["data"]["status"] == "ACCEPTED"

@pytest.mark.asyncio
async def test_reject(client, db_session):
    bh, op = await _buyer_headers(client), await _op_headers(client)
    rfq_id, iids, pids = await _create_processing_rfq(client, bh, op, db_session)
    await client.post(f"/api/v1/rfqs/{rfq_id}/quotes", headers=op, json=_build_payload(iids, pids))
    r = await client.patch(f"/api/v1/rfqs/{rfq_id}/reject", headers=bh)
    assert r.status_code == 200 and r.json()["data"]["status"] == "REJECTED"

@pytest.mark.asyncio
async def test_expire(client, db_session):
    bh, op = await _buyer_headers(client), await _op_headers(client)
    rfq_id, iids, pids = await _create_processing_rfq(client, bh, op, db_session)
    await client.post(f"/api/v1/rfqs/{rfq_id}/quotes", headers=op, json=_build_payload(iids, pids))
    r = await client.patch(f"/api/v1/rfqs/{rfq_id}/expire", headers=op)
    assert r.status_code == 200 and r.json()["data"]["status"] == "EXPIRED"


# ── 买方 DTO 隔离 ─────────────────────────────────────

@pytest.mark.asyncio
async def test_buyer_no_cost(client, db_session):
    bh, op = await _buyer_headers(client), await _op_headers(client)
    rfq_id, iids, pids = await _create_processing_rfq(client, bh, op, db_session)
    await client.post(f"/api/v1/rfqs/{rfq_id}/quotes", headers=op, json=_build_payload(iids, pids, with_cost=True))
    r = await client.get(f"/api/v1/rfqs/{rfq_id}/quotes", headers=bh)
    assert r.status_code == 200
    quote = r.json()["data"][0]
    assert "cost" not in quote["items"][0] or quote["items"][0].get("cost") is None
    assert "version" not in quote
    import json
    raw = json.dumps(quote).lower()
    assert "supplier" not in raw and "gross_margin" not in raw


# ── scope ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_buyer_cannot_create(client, db_session):
    bh, op = await _buyer_headers(client), await _op_headers(client)
    rfq_id, iids, pids = await _create_processing_rfq(client, bh, op, db_session)
    r = await client.post(f"/api/v1/rfqs/{rfq_id}/quotes", headers=bh, json=_build_payload(iids, pids))
    assert r.status_code == 403

@pytest.mark.asyncio
async def test_admin_cannot_access(client, superadmin_headers, db_session):
    r = await client.get("/api/v1/rfqs/1/quotes", headers=superadmin_headers)
    assert r.status_code == 403

@pytest.mark.asyncio
async def test_invalid_trade_term(client, db_session):
    bh, op = await _buyer_headers(client), await _op_headers(client)
    rfq_id, iids, pids = await _create_processing_rfq(client, bh, op, db_session)
    payload = _build_payload(iids, pids)
    payload["header"]["trade_term"] = "EXW"
    r = await client.post(f"/api/v1/rfqs/{rfq_id}/quotes", headers=op, json=payload)
    assert r.status_code == 422
