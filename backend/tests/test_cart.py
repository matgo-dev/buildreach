"""购物车 API 单测。

覆盖:加购合并、scope 越权(404)、数量校验、
商品不可购(不存在/下架)、组织缺失、GET 无副作用、写操作返整车。
SPU 化改造：cart_items 以 product_id + selected_variants 为核心。
"""
from __future__ import annotations

from decimal import Decimal

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.cart import Cart
from app.db.models.category import Category
from app.db.models.product import Product


# ── helpers ─────────────────────────────────────────────

# seed 数据
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


async def _create_purchasable_product(
    client: AsyncClient, op: dict, db: AsyncSession,
) -> int:
    """创建一个可购 Product(ACTIVE SPU),返回 product_id。"""
    cat = (await db.execute(
        select(Category).where(Category.level == 3).limit(1)
    )).scalar_one_or_none()
    assert cat is not None, "No level-3 category in seed data"

    r = await client.post("/api/v1/operator/products", headers=op, json={
        "name": "Cart Test Product",
        "category_code": cat.code,
        "unit": "PCS",
        "currency": "TZS",
    })
    assert r.status_code == 200, r.text
    product_id = r.json()["data"]["id"]

    r = await client.patch(
        f"/api/v1/operator/products/{product_id}/status?force=true",
        headers=op,
        json={"status": "ACTIVE"},
    )
    assert r.status_code == 200, r.text
    return product_id


# ── tests ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_empty_cart(client, db_session):
    """GET /cart 无车返回虚拟空车,不落库。"""
    headers = await _buyer_headers(client)
    me = await _buyer_info(client, headers)

    r = await client.get("/api/v1/cart", headers=headers)
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["id"] is None
    assert data["items"] == []

    # 确认没创建 cart 记录
    row = await db_session.execute(
        select(Cart).where(
            Cart.buyer_org_id == me["organization"]["id"],
            Cart.buyer_user_id == me["id"],
        )
    )
    assert row.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_add_item_creates_cart(client, db_session):
    """POST /cart/items 首次加购创建真实 cart。"""
    headers = await _buyer_headers(client)
    op = await _op_headers(client)
    product_id = await _create_purchasable_product(client, op, db_session)

    r = await client.post("/api/v1/cart/items", headers=headers, json={
        "product_id": product_id, "quantity": "5.000",
    })
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["id"] is not None
    assert len(data["items"]) == 1
    assert data["items"][0]["product_id"] == product_id
    assert Decimal(data["items"][0]["quantity"]) == Decimal("5.000")


@pytest.mark.asyncio
async def test_add_same_product_merges_quantity(client, db_session):
    """同 SPU + 相同变体 重复加购合并数量。"""
    headers = await _buyer_headers(client)
    op = await _op_headers(client)
    product_id = await _create_purchasable_product(client, op, db_session)

    await client.post("/api/v1/cart/items", headers=headers, json={
        "product_id": product_id, "quantity": "3.000",
    })
    r = await client.post("/api/v1/cart/items", headers=headers, json={
        "product_id": product_id, "quantity": "2.000",
    })
    assert r.status_code == 200
    data = r.json()["data"]
    assert len(data["items"]) == 1
    assert Decimal(data["items"][0]["quantity"]) == Decimal("5.000")


@pytest.mark.asyncio
async def test_add_same_product_different_variant_order_merges(client, db_session):
    """同 SPU + 相同变体(不同传入顺序)合并数量。"""
    headers = await _buyer_headers(client)
    op = await _op_headers(client)
    product_id = await _create_purchasable_product(client, op, db_session)

    variants_a = [
        {"attr_name": "color", "value": "red"},
        {"attr_name": "size", "value": "large"},
    ]
    variants_b = [
        {"attr_name": "size", "value": "large"},
        {"attr_name": "color", "value": "red"},
    ]

    await client.post("/api/v1/cart/items", headers=headers, json={
        "product_id": product_id, "selected_variants": variants_a, "quantity": "3.000",
    })
    r = await client.post("/api/v1/cart/items", headers=headers, json={
        "product_id": product_id, "selected_variants": variants_b, "quantity": "2.000",
    })
    assert r.status_code == 200
    data = r.json()["data"]
    # 应该合并为一行
    product_items = [i for i in data["items"] if i["product_id"] == product_id]
    assert len(product_items) == 1
    assert Decimal(product_items[0]["quantity"]) == Decimal("5.000")


@pytest.mark.asyncio
async def test_update_item_quantity(client, db_session):
    """PATCH /cart/items/{item_id} 改量。"""
    headers = await _buyer_headers(client)
    op = await _op_headers(client)
    product_id = await _create_purchasable_product(client, op, db_session)

    r = await client.post("/api/v1/cart/items", headers=headers, json={
        "product_id": product_id, "quantity": "5.000",
    })
    item_id = r.json()["data"]["items"][0]["item_id"]

    r = await client.patch(f"/api/v1/cart/items/{item_id}", headers=headers, json={
        "quantity": "10.000",
    })
    assert r.status_code == 200
    assert Decimal(r.json()["data"]["items"][0]["quantity"]) == Decimal("10.000")


@pytest.mark.asyncio
async def test_remove_item(client, db_session):
    """DELETE /cart/items/{item_id} 删行。"""
    headers = await _buyer_headers(client)
    op = await _op_headers(client)
    product_id = await _create_purchasable_product(client, op, db_session)

    r = await client.post("/api/v1/cart/items", headers=headers, json={
        "product_id": product_id, "quantity": "5.000",
    })
    item_id = r.json()["data"]["items"][0]["item_id"]

    r = await client.delete(f"/api/v1/cart/items/{item_id}", headers=headers)
    assert r.status_code == 200
    assert len(r.json()["data"]["items"]) == 0


@pytest.mark.asyncio
async def test_clear_cart(client, db_session):
    """DELETE /cart/items 清空。"""
    headers = await _buyer_headers(client)
    op = await _op_headers(client)
    product_id = await _create_purchasable_product(client, op, db_session)

    await client.post("/api/v1/cart/items", headers=headers, json={
        "product_id": product_id, "quantity": "5.000",
    })
    r = await client.delete("/api/v1/cart/items", headers=headers)
    assert r.status_code == 200
    assert len(r.json()["data"]["items"]) == 0


@pytest.mark.asyncio
async def test_product_not_available_nonexistent(client, db_session):
    """加购不存在的商品 → 40501。"""
    headers = await _buyer_headers(client)

    r = await client.post("/api/v1/cart/items", headers=headers, json={
        "product_id": 999999, "quantity": "1.000",
    })
    assert r.status_code == 422
    assert r.json()["code"] == 40501


@pytest.mark.asyncio
async def test_product_inactive_not_available(client, db_session):
    """加购下架商品 → 40501。"""
    headers = await _buyer_headers(client)
    op = await _op_headers(client)
    product_id = await _create_purchasable_product(client, op, db_session)

    # 下架商品
    r = await client.patch(
        f"/api/v1/operator/products/{product_id}/status",
        headers=op,
        json={"status": "INACTIVE"},
    )
    assert r.status_code == 200

    r = await client.post("/api/v1/cart/items", headers=headers, json={
        "product_id": product_id, "quantity": "1.000",
    })
    assert r.status_code == 422
    assert r.json()["code"] == 40501


@pytest.mark.asyncio
async def test_quantity_zero_rejected(client, db_session):
    """数量 ≤0 → 422(Pydantic gt=0 校验)。"""
    headers = await _buyer_headers(client)

    r = await client.post("/api/v1/cart/items", headers=headers, json={
        "product_id": 1, "quantity": "0",
    })
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_scope_violation_returns_403(client, superadmin_headers, db_session):
    """非 BUYER 角色尝试操作购物车 → 403(被 require_any_role 挡)。"""
    r = await client.patch("/api/v1/cart/items/1", headers=superadmin_headers, json={
        "quantity": "99.000",
    })
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_get_shows_unavailable_product(client, db_session):
    """GET 展示:下架商品的行不消失但标记不可购。"""
    headers = await _buyer_headers(client)
    op = await _op_headers(client)
    product_id = await _create_purchasable_product(client, op, db_session)

    await client.post("/api/v1/cart/items", headers=headers, json={
        "product_id": product_id, "quantity": "5.000",
    })

    # 下架商品
    r = await client.patch(
        f"/api/v1/operator/products/{product_id}/status",
        headers=op,
        json={"status": "INACTIVE"},
    )
    assert r.status_code == 200

    r = await client.get("/api/v1/cart", headers=headers)
    assert r.status_code == 200
    items = r.json()["data"]["items"]
    assert len(items) >= 1
    target = [i for i in items if i["product_id"] == product_id]
    assert len(target) == 1
    assert target[0]["is_purchasable"] is False
    assert target[0]["unavailable_reason"] == "PRODUCT_INACTIVE"


@pytest.mark.asyncio
async def test_no_buyer_role_403(client, superadmin_headers, db_session):
    """非 BUYER 角色 → 403。"""
    r = await client.get("/api/v1/cart", headers=superadmin_headers)
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_write_returns_full_cart_dto(client, db_session):
    """写操作返回完整 CartPublic,含所有 DTO 字段,不含供应商/成本。"""
    headers = await _buyer_headers(client)
    op = await _op_headers(client)
    product_id = await _create_purchasable_product(client, op, db_session)

    r = await client.post("/api/v1/cart/items", headers=headers, json={
        "product_id": product_id, "quantity": "5.000",
    })
    assert r.status_code == 200
    item = r.json()["data"]["items"][0]

    # DTO 字段完整性
    for key in ("item_id", "product_id", "selected_variants",
                "is_purchasable", "unavailable_reason", "unit", "moq"):
        assert key in item, f"Missing key: {key}"

    # 不含供应商/成本/报价
    item_str = str(item).lower()
    assert "supplier" not in item_str
    assert "cost" not in item_str


@pytest.mark.asyncio
async def test_different_variants_create_separate_lines(client, db_session):
    """同 SPU 不同变体产生两行，各自数量独立。"""
    headers = await _buyer_headers(client)
    op = await _op_headers(client)
    product_id = await _create_purchasable_product(client, op, db_session)

    variants_a = [{"attr_name": "material", "value": "red oak"}]
    variants_b = [{"attr_name": "material", "value": "pine"}]

    await client.post("/api/v1/cart/items", headers=headers, json={
        "product_id": product_id, "selected_variants": variants_a, "quantity": "3.000",
    })
    r = await client.post("/api/v1/cart/items", headers=headers, json={
        "product_id": product_id, "selected_variants": variants_b, "quantity": "5.000",
    })
    assert r.status_code == 200
    data = r.json()["data"]
    product_items = [i for i in data["items"] if i["product_id"] == product_id]
    assert len(product_items) == 2, "同 SPU 不同变体应产生两行"
    quantities = sorted([Decimal(i["quantity"]) for i in product_items])
    assert quantities == [Decimal("3.000"), Decimal("5.000")]


@pytest.mark.asyncio
async def test_same_variant_different_order_merges(client, db_session):
    """同 SPU 同变体（传入顺序不同）累加到同一行，验证 fingerprint 规范化。"""
    headers = await _buyer_headers(client)
    op = await _op_headers(client)
    product_id = await _create_purchasable_product(client, op, db_session)

    variants_a = [
        {"attr_name": "material", "value": "red oak"},
        {"attr_name": "thickness", "value": "5mm"},
    ]
    variants_b = [
        {"attr_name": "thickness", "value": "5mm"},
        {"attr_name": "material", "value": "red oak"},
    ]

    await client.post("/api/v1/cart/items", headers=headers, json={
        "product_id": product_id, "selected_variants": variants_a, "quantity": "3.000",
    })
    r = await client.post("/api/v1/cart/items", headers=headers, json={
        "product_id": product_id, "selected_variants": variants_b, "quantity": "2.000",
    })
    assert r.status_code == 200
    data = r.json()["data"]
    product_items = [i for i in data["items"] if i["product_id"] == product_id]
    assert len(product_items) == 1, "同变体不同顺序应合并为一行"
    assert Decimal(product_items[0]["quantity"]) == Decimal("5.000")


@pytest.mark.asyncio
async def test_selected_variants_in_response(client, db_session):
    """加购带变体时,响应包含 selected_variants 和 variant_display。"""
    headers = await _buyer_headers(client)
    op = await _op_headers(client)
    product_id = await _create_purchasable_product(client, op, db_session)

    variants = [{"attr_name": "color", "value": "red"}]
    r = await client.post("/api/v1/cart/items", headers=headers, json={
        "product_id": product_id, "selected_variants": variants, "quantity": "2.000",
    })
    assert r.status_code == 200, r.text
    item = r.json()["data"]["items"][0]
    assert item["selected_variants"] == [{"attr_name": "color", "value": "red"}]
    assert item["variant_display"] is not None
    assert "color" in item["variant_display"]


# ── Task 2: 变体编辑扩展测试 ────────────────────────────────


@pytest.mark.asyncio
async def test_update_item_no_fields_422(client, db_session):
    """PATCH 两者皆不传 → 422"""
    hdr = await _buyer_headers(client)
    op = await _op_headers(client)
    pid = await _create_purchasable_product(client, op, db_session)
    await client.post("/api/v1/cart/items", json={"product_id": pid, "selected_variants": [], "quantity": 1}, headers=hdr)
    cart = (await client.get("/api/v1/cart", headers=hdr)).json()["data"]
    item_id = cart["items"][0]["item_id"]

    resp = await client.patch(f"/api/v1/cart/items/{item_id}", json={}, headers=hdr)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_update_item_variant_success(client, db_session):
    """PATCH 改变体成功 → 200"""
    hdr = await _buyer_headers(client)
    op = await _op_headers(client)
    pid = await _create_purchasable_product(client, op, db_session)
    # 加购空变体行
    await client.post("/api/v1/cart/items", json={"product_id": pid, "selected_variants": [], "quantity": 1}, headers=hdr)
    cart = (await client.get("/api/v1/cart", headers=hdr)).json()["data"]
    item_id = cart["items"][0]["item_id"]

    # 改变体
    new_variants = [{"attr_name": "color", "value": "red"}]
    resp = await client.patch(f"/api/v1/cart/items/{item_id}", json={"selected_variants": new_variants}, headers=hdr)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_update_item_only_quantity(client, db_session):
    """PATCH 仅改量 → 200，变体不变"""
    hdr = await _buyer_headers(client)
    op = await _op_headers(client)
    pid = await _create_purchasable_product(client, op, db_session)
    await client.post("/api/v1/cart/items", json={"product_id": pid, "selected_variants": [], "quantity": 1}, headers=hdr)
    cart = (await client.get("/api/v1/cart", headers=hdr)).json()["data"]
    item_id = cart["items"][0]["item_id"]

    resp = await client.patch(f"/api/v1/cart/items/{item_id}", json={"quantity": 5}, headers=hdr)
    assert resp.status_code == 200
    updated = resp.json()["data"]["items"]
    matched = [i for i in updated if i["item_id"] == item_id]
    assert len(matched) == 1
    assert float(matched[0]["quantity"]) == 5.0


@pytest.mark.asyncio
async def test_update_item_duplicate_variant_409(client, db_session):
    """PATCH 改为篮中已有规格 → 409 / 40520"""
    hdr = await _buyer_headers(client)
    op = await _op_headers(client)
    pid = await _create_purchasable_product(client, op, db_session)
    v1 = [{"attr_name": "color", "value": "red"}]
    v2 = [{"attr_name": "color", "value": "blue"}]
    await client.post("/api/v1/cart/items", json={"product_id": pid, "selected_variants": v1, "quantity": 1}, headers=hdr)
    await client.post("/api/v1/cart/items", json={"product_id": pid, "selected_variants": v2, "quantity": 1}, headers=hdr)
    cart = (await client.get("/api/v1/cart", headers=hdr)).json()["data"]
    # 找 blue 行（按 selected_variants 查找）
    blue_item = [
        i for i in cart["items"]
        if any(v.get("value") == "blue" for v in (i.get("selected_variants") or []))
    ]
    if not blue_item:
        # 变体未归一化成功时取第二行
        blue_item = [cart["items"][1]]
    item_id = blue_item[0]["item_id"]

    # 把 blue 改成 red → 重复 → 409
    resp = await client.patch(f"/api/v1/cart/items/{item_id}", json={"selected_variants": v1}, headers=hdr)
    assert resp.status_code == 409
    assert resp.json()["code"] == 40520


@pytest.mark.asyncio
async def test_update_item_zero_quantity_rejected(client, db_session):
    """PATCH 改量为 0 → 422 (Pydantic gt=0 拦截)"""
    hdr = await _buyer_headers(client)
    op = await _op_headers(client)
    pid = await _create_purchasable_product(client, op, db_session)
    await client.post("/api/v1/cart/items", json={"product_id": pid, "selected_variants": [], "quantity": 1}, headers=hdr)
    cart = (await client.get("/api/v1/cart", headers=hdr)).json()["data"]
    item_id = cart["items"][0]["item_id"]

    resp = await client.patch(f"/api/v1/cart/items/{item_id}", json={"quantity": 0}, headers=hdr)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_update_item_other_user_404(client, db_session):
    """越权改他人行项 → 403/404"""
    hdr = await _buyer_headers(client)
    op = await _op_headers(client)
    pid = await _create_purchasable_product(client, op, db_session)
    await client.post("/api/v1/cart/items", json={"product_id": pid, "selected_variants": [], "quantity": 1}, headers=hdr)
    cart = (await client.get("/api/v1/cart", headers=hdr)).json()["data"]
    item_id = cart["items"][0]["item_id"]

    # 运营身份无 buyer org → 403/404
    op_hdr = await _op_headers(client)
    resp = await client.patch(f"/api/v1/cart/items/{item_id}", json={"quantity": 5}, headers=op_hdr)
    assert resp.status_code in (403, 404)
