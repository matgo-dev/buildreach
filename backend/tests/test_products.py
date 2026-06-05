"""商品目录模块测试。

覆盖：公开接口 + 运营 CRUD + 供货关系 + 图片 + 状态变更 + 权限校验。
"""
from __future__ import annotations

import io

import pytest
import pytest_asyncio
from httpx import AsyncClient


# ── helper ──────────────────────────────────────────────────

async def _login_operator(client: AsyncClient) -> dict[str, str]:
    """用 demo operator 账号登录，返回 headers。"""
    r = await client.post(
        "/api/v1/auth/login",
        json={"identifier": "operator@platform.local", "password": "Aa123456789"},
    )
    assert r.status_code == 200, r.text
    token = r.json()["data"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


async def _login_buyer(client: AsyncClient) -> dict[str, str]:
    """用 demo buyer 账号登录，返回 headers。"""
    r = await client.post(
        "/api/v1/auth/login",
        json={"identifier": "buyer@cscec3b.local", "password": "Aa123456789"},
    )
    assert r.status_code == 200, r.text
    token = r.json()["data"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


async def _get_first_category_code(client: AsyncClient) -> str:
    """获取第一个 L1 品类的 code。"""
    r = await client.get("/api/v1/categories?level=1&is_active=true")
    assert r.status_code == 200
    items = r.json()["data"]
    assert len(items) > 0, "No categories found — seed may not have run"
    return items[0]["code"]


async def _create_test_product(
    client: AsyncClient, headers: dict, category_code: str, sku: str = "TEST-SKU-001",
) -> int:
    """创建一个测试商品，返回 product id。"""
    r = await client.post(
        "/api/v1/operator/products",
        headers=headers,
        json={
            "category_code": category_code,
            "sku_code": sku,
            "name": "Test LED Panel 36W",
            "name_i18n": {"zh": "测试LED面板灯36W", "en": "Test LED Panel 36W"},
            "price_min": 2.50,
            "price_max": 4.80,
            "currency": "USD",
            "unit": "pcs",
            "moq": 500,
            "lead_time_days": 15,
            "origin": "China",
            "brand": "OEM",
            "certifications": ["PVoC", "CoC"],
            "is_featured": False,
            "status": "DRAFT",
        },
    )
    assert r.status_code == 200, r.text
    assert r.json()["code"] == 0
    return r.json()["data"]["id"]


# ── 公开接口 ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_public_products_list_no_auth(client: AsyncClient):
    """公开商品列表无需登录。"""
    r = await client.get("/api/v1/products")
    assert r.status_code == 200
    assert r.json()["code"] == 0
    assert "items" in r.json()["data"]


@pytest.mark.asyncio
async def test_public_products_only_active(client: AsyncClient):
    """公开列表只返回 ACTIVE 商品，DRAFT 不可见。"""
    headers = await _login_operator(client)
    cat_code = await _get_first_category_code(client)

    # 创建 DRAFT 商品
    pid = await _create_test_product(client, headers, cat_code, "PUB-DRAFT-001")

    # 公开列表不应包含此商品
    r = await client.get("/api/v1/products?keyword=PUB-DRAFT-001")
    assert r.status_code == 200
    items = r.json()["data"]["items"]
    assert all(item["sku_code"] != "PUB-DRAFT-001" for item in items)


@pytest.mark.asyncio
async def test_public_product_detail_draft_404(client: AsyncClient):
    """公开详情：DRAFT 商品返回 404。"""
    headers = await _login_operator(client)
    cat_code = await _get_first_category_code(client)
    pid = await _create_test_product(client, headers, cat_code, "PUB-DETAIL-404")

    r = await client.get(f"/api/v1/products/{pid}")
    assert r.status_code == 404


# ── 运营 CRUD ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_product_success(client: AsyncClient):
    """运营创建商品成功。"""
    headers = await _login_operator(client)
    cat_code = await _get_first_category_code(client)
    pid = await _create_test_product(client, headers, cat_code)
    assert pid > 0


@pytest.mark.asyncio
async def test_create_product_duplicate_sku(client: AsyncClient):
    """SKU 重复 → 400 / 50003。"""
    headers = await _login_operator(client)
    cat_code = await _get_first_category_code(client)

    await _create_test_product(client, headers, cat_code, "DUP-SKU-001")

    r = await client.post(
        "/api/v1/operator/products",
        headers=headers,
        json={
            "category_code": cat_code,
            "sku_code": "DUP-SKU-001",
            "name": "Duplicate",
            "price_min": 1.00,
            "price_max": 2.00,
            "unit": "pcs",
            "moq": 1,
        },
    )
    assert r.status_code == 400
    assert r.json()["code"] == 50003


@pytest.mark.asyncio
async def test_create_product_no_permission(client: AsyncClient):
    """非 OPERATOR 角色（BUYER）创建商品 → 403。"""
    headers = await _login_buyer(client)
    r = await client.post(
        "/api/v1/operator/products",
        headers=headers,
        json={
            "category_code": "01",
            "sku_code": "BUYER-NOPE",
            "name": "Should Fail",
            "price_min": 1.00,
            "price_max": 2.00,
            "unit": "pcs",
            "moq": 1,
        },
    )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_update_product(client: AsyncClient):
    """运营编辑商品成功。"""
    headers = await _login_operator(client)
    cat_code = await _get_first_category_code(client)
    pid = await _create_test_product(client, headers, cat_code, "UPD-001")

    r = await client.put(
        f"/api/v1/operator/products/{pid}",
        headers=headers,
        json={"name": "Updated Name", "price_min": 3.00},
    )
    assert r.status_code == 200
    assert r.json()["code"] == 0


@pytest.mark.asyncio
async def test_delete_draft_product(client: AsyncClient):
    """删除 DRAFT 商品成功。"""
    headers = await _login_operator(client)
    cat_code = await _get_first_category_code(client)
    pid = await _create_test_product(client, headers, cat_code, "DEL-001")

    r = await client.delete(f"/api/v1/operator/products/{pid}", headers=headers)
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_operator_product_detail(client: AsyncClient):
    """运营查看商品详情。"""
    headers = await _login_operator(client)
    cat_code = await _get_first_category_code(client)
    pid = await _create_test_product(client, headers, cat_code, "DETAIL-001")

    r = await client.get(f"/api/v1/operator/products/{pid}", headers=headers)
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["sku_code"] == "DETAIL-001"
    assert data["status"] == "DRAFT"
    assert "suppliers" in data


# ── 状态变更 ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_publish_without_image_fails(client: AsyncClient):
    """上架需要图片，无图片 → 400 / 50004。"""
    headers = await _login_operator(client)
    cat_code = await _get_first_category_code(client)
    pid = await _create_test_product(client, headers, cat_code, "NOPIC-001")

    r = await client.patch(
        f"/api/v1/operator/products/{pid}/status",
        headers=headers,
        json={"status": "ACTIVE"},
    )
    assert r.status_code == 400
    assert r.json()["code"] == 50004


# ── 供货关系 ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_add_and_list_supplier(client: AsyncClient):
    """绑定供应商 + 列表查询。"""
    headers = await _login_operator(client)
    cat_code = await _get_first_category_code(client)
    pid = await _create_test_product(client, headers, cat_code, "SUP-001")

    # 需要一个已有的 supplier_org。从种子数据拿（credit seed 会建 4 家 supplier）
    # 直接用 id=1 试试
    r = await client.post(
        f"/api/v1/operator/products/{pid}/suppliers",
        headers=headers,
        json={
            "supplier_org_id": 1,
            "supplier_price": 1.80,
            "supplier_moq": 200,
            "has_pvoc": True,
            "is_preferred": True,
        },
    )
    # 如果 supplier_org_id=1 不存在会 404，跳过
    if r.status_code == 404:
        pytest.skip("No supplier org with id=1 in test DB")
    assert r.status_code == 200, r.text
    ps_id = r.json()["data"]["id"]

    # 列表
    r2 = await client.get(f"/api/v1/operator/products/{pid}/suppliers", headers=headers)
    assert r2.status_code == 200
    items = r2.json()["data"]
    assert len(items) >= 1
    assert items[0]["supplier_price"] == 1.80


@pytest.mark.asyncio
async def test_duplicate_supplier_binding(client: AsyncClient):
    """重复绑定同一供应商 → 400 / 50007。"""
    headers = await _login_operator(client)
    cat_code = await _get_first_category_code(client)
    pid = await _create_test_product(client, headers, cat_code, "DUP-SUP-001")

    payload = {"supplier_org_id": 1, "supplier_price": 2.00}
    r1 = await client.post(f"/api/v1/operator/products/{pid}/suppliers", headers=headers, json=payload)
    if r1.status_code == 404:
        pytest.skip("No supplier org with id=1")

    r2 = await client.post(f"/api/v1/operator/products/{pid}/suppliers", headers=headers, json=payload)
    assert r2.status_code == 400
    assert r2.json()["code"] == 50007


# ── 图片 ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_upload_and_delete_image(client: AsyncClient):
    """上传图片 + 删除图片。"""
    headers = await _login_operator(client)
    cat_code = await _get_first_category_code(client)
    pid = await _create_test_product(client, headers, cat_code, "IMG-001")

    # 构造一个最小的 PNG
    png_bytes = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
        b"\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00"
        b"\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00"
        b"\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
    )

    r = await client.post(
        f"/api/v1/operator/products/{pid}/images",
        headers=headers,
        files={"file": ("test.png", io.BytesIO(png_bytes), "image/png")},
    )
    assert r.status_code == 200, r.text
    img_id = r.json()["data"]["id"]
    assert r.json()["data"]["url"].endswith(".png")

    # 删除
    r2 = await client.delete(f"/api/v1/operator/products/{pid}/images/{img_id}", headers=headers)
    assert r2.status_code == 200


# ── 品类属性模板 ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_attr_templates_endpoint(client: AsyncClient):
    """品类属性模板接口返回 200。"""
    cat_code = await _get_first_category_code(client)
    r = await client.get(f"/api/v1/categories/{cat_code}/attr-templates")
    assert r.status_code == 200
    assert r.json()["code"] == 0
    # 当前无种子数据，应返回空列表
    assert isinstance(r.json()["data"], list)
