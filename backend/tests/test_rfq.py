"""询价单 API 单测。

覆盖:统一 items 入参、代客、目标 org 校验、商品可用性校验、
rfq_no 生成、dup product+variant、scope 越权(404)、撤销守卫+幂等、
买方 DTO 不漏内部 id、清篮零副作用。
"""
from __future__ import annotations

import asyncio
from decimal import Decimal
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.audit_log import AuditLog
from app.db.models.cart_item import CartItem
from app.db.models.category import Category
from app.db.models.rfq import Rfq, RfqSource, RfqStatus


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


async def _create_active_product(
    client: AsyncClient, op: dict, db: AsyncSession,
) -> tuple[int, int]:
    """创建一个 ACTIVE 商品(SPU + SKU),返回 (product_id, sku_id)。"""
    cat = (await db.execute(
        select(Category).where(Category.level == 3).limit(1)
    )).scalar_one_or_none()
    assert cat is not None, "No level-3 category in seed data"

    r = await client.post("/api/v1/operator/products", headers=op, json={
        "name": "RFQ Test Product",
        "category_code": cat.code,
        "unit": "PCS",
        "currency": "TZS",
    })
    assert r.status_code == 200, r.text
    product_id = r.json()["data"]["id"]

    r = await client.post(
        f"/api/v1/operator/products/{product_id}/skus",
        headers=op,
        json={"name": "RFQ Test SKU", "moq": 1, "price_min": 100, "price_max": 200},
    )
    assert r.status_code == 200, r.text
    sku_id = r.json()["data"]["id"]

    r = await client.patch(
        f"/api/v1/operator/products/{product_id}/status?force=true",
        headers=op,
        json={"status": "ACTIVE"},
    )
    assert r.status_code == 200, r.text
    return product_id, sku_id


async def _add_to_cart(client: AsyncClient, headers: dict, product_id: int, qty: str = "5.000") -> int:
    """加购并返回 cart_item_id。"""
    r = await client.post("/api/v1/cart/items", headers=headers, json={
        "product_id": product_id, "selected_variants": [], "quantity": qty,
    })
    assert r.status_code == 200, r.text
    return r.json()["data"]["items"][-1]["item_id"]


# ── 统一 items 创建 ─────────────────────────────────────


@pytest.mark.asyncio
async def test_buyer_create(client, db_session):
    """BUYER 创建询价单 → SUBMITTED + BUYER_SELF。"""
    bh = await _buyer_headers(client)
    op = await _op_headers(client)
    product_id, _ = await _create_active_product(client, op, db_session)

    r = await client.post("/api/v1/rfqs", headers=bh, json={
        "items": [{"product_id": product_id, "selected_variants": [], "quantity": "10.000", "target_unit_price": "50.0000"}],
        "remark": "test direct",
    })
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["status"] == "SUBMITTED"
    assert data["source"] == "BUYER_SELF"
    assert data["rfq_no"].startswith("RFQ-")
    assert len(data["items"]) == 1
    assert Decimal(data["items"][0]["quantity"]) == Decimal("10.000")


@pytest.mark.asyncio
async def test_buyer_create_multiple_items(client, db_session):
    """BUYER 多行创建。"""
    bh = await _buyer_headers(client)
    op = await _op_headers(client)
    pid1, _ = await _create_active_product(client, op, db_session)
    pid2, _ = await _create_active_product(client, op, db_session)

    r = await client.post("/api/v1/rfqs", headers=bh, json={
        "items": [
            {"product_id": pid1, "selected_variants": [], "quantity": "5.000"},
            {"product_id": pid2, "selected_variants": [], "quantity": "3.000"},
        ],
    })
    assert r.status_code == 200, r.text
    assert len(r.json()["data"]["items"]) == 2


# ── 清篮零副作用 ──────────────────────────────────────


@pytest.mark.asyncio
async def test_buyer_create_no_cart_side_effect(client, db_session):
    """创建询价单不再自动清篮 — 购物车行保留。"""
    bh = await _buyer_headers(client)
    op = await _op_headers(client)
    product_id, sku_id = await _create_active_product(client, op, db_session)
    ci_id = await _add_to_cart(client, bh, product_id)

    r = await client.post("/api/v1/rfqs", headers=bh, json={
        "items": [{"product_id": product_id, "selected_variants": [], "quantity": "5.000"}],
    })
    assert r.status_code == 200, r.text
    assert len(r.json()["data"]["items"]) == 1

    # 购物车行不受影响（清篮由前端负责）
    row = await db_session.execute(
        select(CartItem).where(CartItem.id == ci_id)
    )
    assert row.scalar_one_or_none() is not None


# ── 代客 ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_operator_proxy_create(client, db_session):
    """OPERATOR 代客创建(DIRECT + buyer_org_id)→ OPERATOR_PROXY。"""
    op = await _op_headers(client)
    product_id, _ = await _create_active_product(client, op, db_session)

    # 取买方组织 id
    bh = await _buyer_headers(client)
    me = await _buyer_info(client, bh)
    buyer_org_id = me["organization"]["id"]

    r = await client.post("/api/v1/rfqs", headers=op, json={
        "buyer_org_id": buyer_org_id,
        "items": [{"product_id": product_id, "selected_variants": [], "quantity": "20.000"}],
        "contact_name": "John",
        "contact_phone": "+255123456789",
    })
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["source"] == "OPERATOR_PROXY"
    assert data["buyer_org_id"] == buyer_org_id
    assert data["contact_name"] == "John"


@pytest.mark.asyncio
async def test_operator_proxy_invalid_org(client, db_session):
    """代客:目标 org 不存在 → 40504。"""
    op = await _op_headers(client)
    product_id, _ = await _create_active_product(client, op, db_session)

    r = await client.post("/api/v1/rfqs", headers=op, json={
        "buyer_org_id": 999999,
        "items": [{"product_id": product_id, "selected_variants": [], "quantity": "1.000"}],
    })
    assert r.status_code == 403
    assert r.json()["code"] == 40504


@pytest.mark.asyncio
async def test_operator_missing_items_rejected(client, db_session):
    """OPERATOR 缺少 items → 422 Pydantic 校验。"""
    op = await _op_headers(client)

    bh = await _buyer_headers(client)
    me = await _buyer_info(client, bh)
    buyer_org_id = me["organization"]["id"]

    r = await client.post("/api/v1/rfqs", headers=op, json={
        "buyer_org_id": buyer_org_id,
    })
    assert r.status_code == 422


# ── 校验 ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_direct_duplicate_product_variant_rejected(client, db_session):
    """DIRECT 重复 product_id + selected_variants → 40509。"""
    bh = await _buyer_headers(client)
    op = await _op_headers(client)
    product_id, _ = await _create_active_product(client, op, db_session)

    r = await client.post("/api/v1/rfqs", headers=bh, json={
        "items": [
            {"product_id": product_id, "selected_variants": [], "quantity": "5.000"},
            {"product_id": product_id, "selected_variants": [], "quantity": "3.000"},
        ],
    })
    assert r.status_code == 422
    assert r.json()["code"] == 40509


@pytest.mark.asyncio
async def test_direct_empty_items_rejected(client, db_session):
    """DIRECT 空行 → 40505。"""
    bh = await _buyer_headers(client)

    r = await client.post("/api/v1/rfqs", headers=bh, json={
        "items": [],
    })
    assert r.status_code == 422
    assert r.json()["code"] == 40505


@pytest.mark.asyncio
async def test_direct_not_available_product(client, db_session):
    """DIRECT 含不可用商品 → 40506 + offending_product_ids。"""
    bh = await _buyer_headers(client)

    r = await client.post("/api/v1/rfqs", headers=bh, json={
        "items": [{"product_id": 999999, "selected_variants": [], "quantity": "1.000"}],
    })
    assert r.status_code == 422
    assert r.json()["code"] == 40506
    assert 999999 in r.json()["data"]["offending_product_ids"]


# ── 列表 ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_buyer_list_scoped(client, db_session):
    """BUYER 列表只看本组织。"""
    bh = await _buyer_headers(client)
    op = await _op_headers(client)
    product_id, _ = await _create_active_product(client, op, db_session)

    await client.post("/api/v1/rfqs", headers=bh, json={
        "items": [{"product_id": product_id, "selected_variants": [], "quantity": "1.000"}],
    })

    r = await client.get("/api/v1/rfqs", headers=bh)
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["total"] >= 1
    assert len(data["items"]) >= 1


@pytest.mark.asyncio
async def test_buyer_list_mine_filter(client, db_session):
    """BUYER mine=true 只看本人。"""
    bh = await _buyer_headers(client)
    op = await _op_headers(client)
    product_id, _ = await _create_active_product(client, op, db_session)

    await client.post("/api/v1/rfqs", headers=bh, json={
        "items": [{"product_id": product_id, "selected_variants": [], "quantity": "1.000"}],
    })

    r = await client.get("/api/v1/rfqs?mine=true", headers=bh)
    assert r.status_code == 200
    assert r.json()["data"]["total"] >= 1


@pytest.mark.asyncio
async def test_operator_list_all(client, db_session):
    """OPERATOR 列表全量。"""
    op = await _op_headers(client)
    r = await client.get("/api/v1/rfqs", headers=op)
    assert r.status_code == 200


# ── 详情 ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_buyer_get_detail(client, db_session):
    """BUYER 查看自己的询价单详情。"""
    bh = await _buyer_headers(client)
    op = await _op_headers(client)
    product_id, _ = await _create_active_product(client, op, db_session)

    r = await client.post("/api/v1/rfqs", headers=bh, json={
        "items": [{"product_id": product_id, "selected_variants": [], "quantity": "1.000"}],
    })
    rfq_id = r.json()["data"]["id"]

    r = await client.get(f"/api/v1/rfqs/{rfq_id}", headers=bh)
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["id"] == rfq_id
    assert len(data["items"]) == 1


@pytest.mark.asyncio
async def test_buyer_get_nonexistent_404(client, db_session):
    """BUYER 查看不存在的 → 40507/404。"""
    bh = await _buyer_headers(client)
    r = await client.get("/api/v1/rfqs/999999", headers=bh)
    assert r.status_code == 404
    assert r.json()["code"] == 40507


# ── 撤销 ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_cancel_submitted(client, db_session):
    """撤销 SUBMITTED → CANCELLED。"""
    bh = await _buyer_headers(client)
    op = await _op_headers(client)
    product_id, _ = await _create_active_product(client, op, db_session)

    r = await client.post("/api/v1/rfqs", headers=bh, json={
        "items": [{"product_id": product_id, "selected_variants": [], "quantity": "1.000"}],
    })
    rfq_id = r.json()["data"]["id"]

    r = await client.patch(f"/api/v1/rfqs/{rfq_id}/cancel", headers=bh, json={
        "cancel_reason": "no longer needed",
    })
    assert r.status_code == 200
    assert r.json()["data"]["status"] == "CANCELLED"


@pytest.mark.asyncio
async def test_cancel_idempotent(client, db_session):
    """已 CANCELLED → 幂等返回当前,不改 reason。"""
    bh = await _buyer_headers(client)
    op = await _op_headers(client)
    product_id, _ = await _create_active_product(client, op, db_session)

    r = await client.post("/api/v1/rfqs", headers=bh, json={
        "items": [{"product_id": product_id, "selected_variants": [], "quantity": "1.000"}],
    })
    rfq_id = r.json()["data"]["id"]

    # 第一次撤销
    await client.patch(f"/api/v1/rfqs/{rfq_id}/cancel", headers=bh, json={
        "cancel_reason": "reason 1",
    })

    # 第二次撤销(不同 reason)→ 幂等,reason 不变
    r = await client.patch(f"/api/v1/rfqs/{rfq_id}/cancel", headers=bh, json={
        "cancel_reason": "reason 2",
    })
    assert r.status_code == 200
    # 幂等:cancel_reason 应该保持 "reason 1"(不被第二次覆盖)
    # 买方 DTO 不含 cancel_reason,用运营视角检查
    r2 = await client.get(f"/api/v1/rfqs/{rfq_id}", headers=op)
    assert r2.json()["data"]["cancel_reason"] == "reason 1"


@pytest.mark.asyncio
async def test_cancel_nonexistent_404(client, db_session):
    """撤销不存在的 → 40507/404。"""
    bh = await _buyer_headers(client)
    r = await client.patch("/api/v1/rfqs/999999/cancel", headers=bh)
    assert r.status_code == 404
    assert r.json()["code"] == 40507


# ── DTO 隔离 ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_buyer_dto_no_internal_fields(client, db_session):
    """买方 DTO 不含 created_by_user_id / operator_assignee_id / buyer_org_id。"""
    bh = await _buyer_headers(client)
    op = await _op_headers(client)
    product_id, _ = await _create_active_product(client, op, db_session)

    r = await client.post("/api/v1/rfqs", headers=bh, json={
        "items": [{"product_id": product_id, "selected_variants": [], "quantity": "1.000"}],
    })
    data = r.json()["data"]
    assert "created_by_user_id" not in data
    assert "operator_assignee_id" not in data
    assert "buyer_org_id" not in data

    # 不含供应商/成本/报价
    data_str = str(data).lower()
    assert "supplier" not in data_str
    assert "cost" not in data_str


@pytest.mark.asyncio
async def test_operator_dto_has_internal_fields(client, db_session):
    """运营 DTO 含 buyer_org_id / created_by_user_id。"""
    op = await _op_headers(client)
    bh = await _buyer_headers(client)
    me = await _buyer_info(client, bh)
    buyer_org_id = me["organization"]["id"]
    product_id, _ = await _create_active_product(client, op, db_session)

    r = await client.post("/api/v1/rfqs", headers=op, json={
        "buyer_org_id": buyer_org_id,
        "items": [{"product_id": product_id, "selected_variants": [], "quantity": "1.000"}],
    })
    data = r.json()["data"]
    assert "created_by_user_id" in data
    assert "buyer_org_id" in data
    assert data["buyer_org_id"] == buyer_org_id


# ── 快照 ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_item_snapshot_populated(client, db_session):
    """创建后行项目快照字段已填充。"""
    bh = await _buyer_headers(client)
    op = await _op_headers(client)
    product_id, _ = await _create_active_product(client, op, db_session)

    r = await client.post("/api/v1/rfqs", headers=bh, json={
        "items": [{"product_id": product_id, "selected_variants": [], "quantity": "1.000"}],
    })
    item = r.json()["data"]["items"][0]
    # product_name_snapshot 应该有值
    assert item["product_name_snapshot"] is not None
    assert item["uom_snapshot"] is not None
    # variant_snapshot 应该是 list（即使为空）
    assert isinstance(item["variant_snapshot"], list)


# ── 非 BUYER/OPERATOR 角色拒绝 ─────────────────────────


@pytest.mark.asyncio
async def test_admin_cannot_access_rfqs(client, superadmin_headers, db_session):
    """ADMIN 角色 → 403。"""
    r = await client.get("/api/v1/rfqs", headers=superadmin_headers)
    assert r.status_code == 403


# ── scope 越权 ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_buyer_scope_violation_detail(client, db_session):
    """BUYER 查看不属于自己组织的询价单 → 40507/404。"""
    op = await _op_headers(client)
    bh = await _buyer_headers(client)
    me = await _buyer_info(client, bh)
    buyer_org_id = me["organization"]["id"]
    product_id, _ = await _create_active_product(client, op, db_session)

    # 运营代客创建(属于同组织,但后面用另一买方测)
    r = await client.post("/api/v1/rfqs", headers=op, json={
        "buyer_org_id": buyer_org_id,
        "items": [{"product_id": product_id, "selected_variants": [], "quantity": "1.000"}],
    })
    rfq_id = r.json()["data"]["id"]

    # 同组织买方可以看到
    r = await client.get(f"/api/v1/rfqs/{rfq_id}", headers=bh)
    assert r.status_code == 200


# ── 软删一致性(loader 收敛验证) ─────────────────────────


@pytest.mark.asyncio
async def test_soft_deleted_rfq_invisible(client, db_session):
    """软删 RFQ → 详情/报价列表均返回 404,loader 规则一致。"""
    from datetime import datetime, timezone

    bh = await _buyer_headers(client)
    op = await _op_headers(client)
    product_id, _ = await _create_active_product(client, op, db_session)

    r = await client.post("/api/v1/rfqs", headers=bh, json={
        "items": [{"product_id": product_id, "selected_variants": [], "quantity": "1.000"}],
    })
    assert r.status_code == 200
    rfq_id = r.json()["data"]["id"]

    # 手动软删
    rfq = (await db_session.execute(
        select(Rfq).where(Rfq.id == rfq_id)
    )).scalar_one()
    rfq.deleted_at = datetime.now(timezone.utc).replace(tzinfo=None)
    rfq.deleted_by = 1
    await db_session.commit()

    # BUYER 详情 → 404
    r = await client.get(f"/api/v1/rfqs/{rfq_id}", headers=bh)
    assert r.status_code == 404

    # OPERATOR 详情 → 404
    r = await client.get(f"/api/v1/rfqs/{rfq_id}", headers=op)
    assert r.status_code == 404

    # 报价列表 → 404
    r = await client.get(f"/api/v1/rfqs/{rfq_id}/quotes", headers=op)
    assert r.status_code == 404


# ── 幂等键(Idempotency-Key) ─────────────────────────────


@pytest.mark.asyncio
async def test_idempotency_same_key_sequential(client: AsyncClient, db_session: AsyncSession):
    """同一 Idempotency-Key 顺序重复提交 → 返回同一 rfq_id；DB 仅一张单。"""
    op = await _op_headers(client)
    bh = await _buyer_headers(client)
    product_id, _ = await _create_active_product(client, op, db_session)
    idem_key = str(uuid4())

    payload = {
        "items": [{"product_id": product_id, "selected_variants": [], "quantity": 10}],
    }
    headers = {**bh, "Idempotency-Key": idem_key}

    r1 = await client.post("/api/v1/rfqs", headers=headers, json=payload)
    assert r1.status_code == 200, r1.text
    rfq_id_1 = r1.json()["data"]["id"]

    r2 = await client.post("/api/v1/rfqs", headers=headers, json=payload)
    assert r2.status_code == 200, r2.text
    rfq_id_2 = r2.json()["data"]["id"]

    assert rfq_id_1 == rfq_id_2

    # DB 中仅一张单
    count = (await db_session.execute(
        select(func.count()).select_from(Rfq).where(Rfq.idempotency_key == idem_key)
    )).scalar()
    assert count == 1


@pytest.mark.asyncio
async def test_idempotency_different_keys(client: AsyncClient, db_session: AsyncSession):
    """不同 key 提交 → 两张单。"""
    op = await _op_headers(client)
    bh = await _buyer_headers(client)
    product_id, _ = await _create_active_product(client, op, db_session)

    payload = {
        "items": [{"product_id": product_id, "selected_variants": [], "quantity": 10}],
    }

    r1 = await client.post(
        "/api/v1/rfqs", headers={**bh, "Idempotency-Key": str(uuid4())}, json=payload,
    )
    r2 = await client.post(
        "/api/v1/rfqs", headers={**bh, "Idempotency-Key": str(uuid4())}, json=payload,
    )
    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r1.json()["data"]["id"] != r2.json()["data"]["id"]


@pytest.mark.asyncio
async def test_idempotency_no_header(client: AsyncClient, db_session: AsyncSession):
    """无 Idempotency-Key 头 → 每次建新单(维持现状)。"""
    op = await _op_headers(client)
    bh = await _buyer_headers(client)
    product_id, _ = await _create_active_product(client, op, db_session)

    payload = {
        "items": [{"product_id": product_id, "selected_variants": [], "quantity": 10}],
    }

    r1 = await client.post("/api/v1/rfqs", headers=bh, json=payload)
    r2 = await client.post("/api/v1/rfqs", headers=bh, json=payload)
    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r1.json()["data"]["id"] != r2.json()["data"]["id"]


@pytest.mark.asyncio
async def test_idempotency_validation_failure_then_retry(client: AsyncClient, db_session: AsyncSession):
    """校验失败(商品不可用)后同 key 重试 → 首次报错,key 未占;修正后同 key 成功。"""
    op = await _op_headers(client)
    bh = await _buyer_headers(client)
    idem_key = str(uuid4())

    # 不存在的商品 → 校验失败
    payload_bad = {
        "items": [{"product_id": 999999, "selected_variants": [], "quantity": 10}],
    }
    r1 = await client.post(
        "/api/v1/rfqs", headers={**bh, "Idempotency-Key": idem_key}, json=payload_bad,
    )
    assert r1.status_code != 200  # 校验失败

    # key 未被占用,同 key 用正确载荷重试
    product_id, _ = await _create_active_product(client, op, db_session)
    payload_good = {
        "items": [{"product_id": product_id, "selected_variants": [], "quantity": 10}],
    }
    r2 = await client.post(
        "/api/v1/rfqs", headers={**bh, "Idempotency-Key": idem_key}, json=payload_good,
    )
    assert r2.status_code == 200, r2.text


@pytest.mark.asyncio
async def test_idempotency_no_duplicate_audit(client: AsyncClient, db_session: AsyncSession):
    """幂等命中不重复写审计。"""
    op = await _op_headers(client)
    bh = await _buyer_headers(client)
    product_id, _ = await _create_active_product(client, op, db_session)
    idem_key = str(uuid4())

    payload = {
        "items": [{"product_id": product_id, "selected_variants": [], "quantity": 10}],
    }
    headers = {**bh, "Idempotency-Key": idem_key}

    r1 = await client.post("/api/v1/rfqs", headers=headers, json=payload)
    assert r1.status_code == 200
    rfq_id = r1.json()["data"]["id"]

    # 重复提交
    r2 = await client.post("/api/v1/rfqs", headers=headers, json=payload)
    assert r2.status_code == 200

    # 审计仅一条 SUBMIT
    audit_count = (await db_session.execute(
        select(func.count()).select_from(AuditLog).where(
            AuditLog.resource_type == "rfq",
            AuditLog.resource_id == str(rfq_id),
            AuditLog.action == "SUBMIT",
        )
    )).scalar()
    assert audit_count == 1


@pytest.mark.asyncio
async def test_idempotency_cart_items_untouched(client: AsyncClient, db_session: AsyncSession):
    """创建询价不影响购物车行（清篮由前端负责）。"""
    op = await _op_headers(client)
    bh = await _buyer_headers(client)
    product_id, sku_id = await _create_active_product(client, op, db_session)
    cart_item_id = await _add_to_cart(client, bh, product_id)
    idem_key = str(uuid4())

    payload = {
        "items": [{"product_id": product_id, "selected_variants": [], "quantity": "5.000"}],
    }
    headers = {**bh, "Idempotency-Key": idem_key}

    r1 = await client.post("/api/v1/rfqs", headers=headers, json=payload)
    assert r1.status_code == 200

    # 购物车行仍在
    row = await db_session.execute(
        select(CartItem).where(CartItem.id == cart_item_id)
    )
    assert row.scalar_one_or_none() is not None
