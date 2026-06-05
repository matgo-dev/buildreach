"""商品目录模块测试 — SPU + SKU 两层化。

覆盖：
- 买方接口两层口径 + 断层断言（不含供应商字段）
- 运营 SPU/SKU/阶梯价/图片/供货 增改删
- 默认 SKU 唯一性、阶梯价规则校验、上架校验（三条）
- 审计断言（写操作落审计、校验失败不落审计）
"""
from __future__ import annotations

import io

import pytest
import pytest_asyncio
from httpx import AsyncClient


# ── helper ──────────────────────────────────────────────────

async def _login_operator(client: AsyncClient) -> dict[str, str]:
    r = await client.post(
        "/api/v1/auth/login",
        json={"identifier": "operator@platform.local", "password": "Aa123456789"},
    )
    assert r.status_code == 200, r.text
    token = r.json()["data"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


async def _login_buyer(client: AsyncClient) -> dict[str, str]:
    r = await client.post(
        "/api/v1/auth/login",
        json={"identifier": "buyer@cscec3b.local", "password": "Aa123456789"},
    )
    assert r.status_code == 200, r.text
    token = r.json()["data"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


async def _get_first_category_code(client: AsyncClient) -> str:
    r = await client.get("/api/v1/categories?level=1&is_active=true")
    assert r.status_code == 200
    items = r.json()["data"]
    assert len(items) > 0, "No categories found — seed may not have run"
    return items[0]["code"]


async def _create_test_product(
    client: AsyncClient, headers: dict, category_code: str,
    spu_code: str = "TEST-SPU-001",
) -> int:
    """创建 SPU，返回 product id。"""
    r = await client.post(
        "/api/v1/operator/products",
        headers=headers,
        json={
            "category_code": category_code,
            "spu_code": spu_code,
            "name": "Test LED Panel 36W",
            "name_i18n": {"zh": "测试LED面板灯36W", "en": "Test LED Panel 36W"},
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


async def _create_test_sku(
    client: AsyncClient, headers: dict, product_id: int,
    sku_code: str = "TEST-SKU-001", is_default: bool = True,
    price_tiers: list | None = None,
) -> int:
    """创建 SKU，返回 sku id。"""
    payload = {
        "sku_code": sku_code,
        "unit": "pcs",
        "moq": 500,
        "price_min": 2.50,
        "price_max": 4.80,
        "currency": "TZS",
        "is_default": is_default,
        "status": "ACTIVE",
    }
    if price_tiers is not None:
        payload["price_tiers"] = price_tiers
    r = await client.post(
        f"/api/v1/operator/products/{product_id}/skus",
        headers=headers,
        json=payload,
    )
    assert r.status_code == 200, r.text
    assert r.json()["code"] == 0
    return r.json()["data"]["id"]


async def _upload_test_image(
    client: AsyncClient, headers: dict, product_id: int,
) -> int:
    """上传测试图片，返回 image id。"""
    from PIL import Image as PILImage
    buf = io.BytesIO()
    PILImage.new("RGB", (300, 300), color=(200, 100, 50)).save(buf, format="PNG")
    buf.seek(0)
    r = await client.post(
        f"/api/v1/operator/products/{product_id}/images",
        headers=headers,
        files={"file": ("test.png", buf, "image/png")},
    )
    assert r.status_code == 200, r.text
    return r.json()["data"]["id"]


async def _get_audit_count(client: AsyncClient, db_session) -> int:
    """直接查 audit_log 表行数。"""
    from sqlalchemy import text
    result = await db_session.execute(text("SELECT count(*) FROM audit_logs"))
    return result.scalar() or 0


# ── 买方接口：两层口径 + 断层断言 ────────────────────────

@pytest.mark.asyncio
async def test_public_products_list_no_auth(client: AsyncClient):
    """公开商品列表无需登录。"""
    r = await client.get("/api/v1/products")
    assert r.status_code == 200
    assert r.json()["code"] == 0
    assert "items" in r.json()["data"]


@pytest.mark.asyncio
async def test_public_products_only_active(client: AsyncClient):
    """公开列表只返回 ACTIVE SPU，DRAFT 不可见。"""
    headers = await _login_operator(client)
    cat_code = await _get_first_category_code(client)
    await _create_test_product(client, headers, cat_code, "PUB-DRAFT-001")

    r = await client.get("/api/v1/products?keyword=PUB-DRAFT-001")
    assert r.status_code == 200
    items = r.json()["data"]["items"]
    assert all(item["spu_code"] != "PUB-DRAFT-001" for item in items)


@pytest.mark.asyncio
async def test_public_product_detail_draft_404(client: AsyncClient):
    """公开详情：DRAFT 商品返回 404。"""
    headers = await _login_operator(client)
    cat_code = await _get_first_category_code(client)
    pid = await _create_test_product(client, headers, cat_code, "PUB-DETAIL-404")
    r = await client.get(f"/api/v1/products/{pid}")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_public_list_two_tier_fields(client: AsyncClient):
    """买方列表返回 SPU 字段 + 默认 SKU 展示价 + sku_count。"""
    headers = await _login_operator(client)
    cat_code = await _get_first_category_code(client)
    pid = await _create_test_product(client, headers, cat_code, "PUB-2TIER-001")
    sku_id = await _create_test_sku(client, headers, pid, "PUB-2TIER-SKU-001")
    await _upload_test_image(client, headers, pid)

    # 上架
    r = await client.patch(
        f"/api/v1/operator/products/{pid}/status",
        headers=headers, json={"status": "ACTIVE"},
    )
    assert r.status_code == 200, r.text

    # 买方列表
    r = await client.get("/api/v1/products?keyword=PUB-2TIER-001")
    assert r.status_code == 200
    items = r.json()["data"]["items"]
    assert len(items) >= 1
    item = next(i for i in items if i["spu_code"] == "PUB-2TIER-001")
    assert "spu_code" in item
    assert "price_min" in item
    assert "price_max" in item
    assert "sku_count" in item
    assert item["sku_count"] >= 1


@pytest.mark.asyncio
async def test_public_detail_two_tier_with_skus(client: AsyncClient):
    """买方详情返回 SPU + skus[] + images + attributes。"""
    headers = await _login_operator(client)
    cat_code = await _get_first_category_code(client)
    pid = await _create_test_product(client, headers, cat_code, "PUB-DETAIL-2T")
    await _create_test_sku(client, headers, pid, "PUB-DETAIL-SKU-2T")
    await _upload_test_image(client, headers, pid)

    await client.patch(
        f"/api/v1/operator/products/{pid}/status",
        headers=headers, json={"status": "ACTIVE"},
    )

    r = await client.get(f"/api/v1/products/{pid}")
    assert r.status_code == 200
    data = r.json()["data"]
    assert "skus" in data
    assert len(data["skus"]) >= 1
    assert "images" in data
    assert "attributes" in data

    # SKU 包含 price_tiers
    sku = data["skus"][0]
    assert "price_tiers" in sku
    assert "sku_code" in sku
    assert "moq" in sku


@pytest.mark.asyncio
async def test_public_isolation_no_supplier_fields(client: AsyncClient):
    """断层断言：买方列表和详情不含任何供应商字段。"""
    headers = await _login_operator(client)
    cat_code = await _get_first_category_code(client)
    pid = await _create_test_product(client, headers, cat_code, "PUB-ISO-001")
    await _create_test_sku(client, headers, pid, "PUB-ISO-SKU-001")
    await _upload_test_image(client, headers, pid)

    await client.patch(
        f"/api/v1/operator/products/{pid}/status",
        headers=headers, json={"status": "ACTIVE"},
    )

    _SUPPLIER_FIELDS = {
        "supplier_price", "supplier_currency", "cif_price_usd",
        "pvoc_status", "supplier_moq", "supplier_lead_time_days",
        "supplier_org_id", "supplier_org_name", "supplier_relations",
        "suppliers", "notes", "is_preferred", "has_coc",
    }

    def _assert_no_supplier(obj: dict, path: str = ""):
        for key in obj:
            assert key not in _SUPPLIER_FIELDS, (
                f"Supplier field '{key}' found in buyer response at {path}"
            )
            if isinstance(obj[key], dict):
                _assert_no_supplier(obj[key], f"{path}.{key}")
            elif isinstance(obj[key], list):
                for i, item in enumerate(obj[key]):
                    if isinstance(item, dict):
                        _assert_no_supplier(item, f"{path}.{key}[{i}]")

    # 列表
    r = await client.get("/api/v1/products?keyword=PUB-ISO-001")
    for item in r.json()["data"]["items"]:
        _assert_no_supplier(item, "list_item")

    # 详情
    r2 = await client.get(f"/api/v1/products/{pid}")
    _assert_no_supplier(r2.json()["data"], "detail")


# ── 运营 SPU CRUD ────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_product_success(client: AsyncClient):
    headers = await _login_operator(client)
    cat_code = await _get_first_category_code(client)
    pid = await _create_test_product(client, headers, cat_code)
    assert pid > 0


@pytest.mark.asyncio
async def test_create_product_duplicate_spu(client: AsyncClient):
    """SPU 编码重复 → 400 / 50003。"""
    headers = await _login_operator(client)
    cat_code = await _get_first_category_code(client)
    await _create_test_product(client, headers, cat_code, "DUP-SPU-001")

    r = await client.post(
        "/api/v1/operator/products",
        headers=headers,
        json={"category_code": cat_code, "spu_code": "DUP-SPU-001", "name": "Dup"},
    )
    assert r.status_code == 400
    assert r.json()["code"] == 50003


@pytest.mark.asyncio
async def test_create_product_no_permission(client: AsyncClient):
    headers = await _login_buyer(client)
    r = await client.post(
        "/api/v1/operator/products",
        headers=headers,
        json={"category_code": "01", "spu_code": "BUYER-NOPE", "name": "Fail"},
    )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_update_product(client: AsyncClient):
    headers = await _login_operator(client)
    cat_code = await _get_first_category_code(client)
    pid = await _create_test_product(client, headers, cat_code, "UPD-SPU-001")

    r = await client.put(
        f"/api/v1/operator/products/{pid}",
        headers=headers,
        json={"name": "Updated Name"},
    )
    assert r.status_code == 200
    assert r.json()["code"] == 0


@pytest.mark.asyncio
async def test_delete_draft_product(client: AsyncClient):
    headers = await _login_operator(client)
    cat_code = await _get_first_category_code(client)
    pid = await _create_test_product(client, headers, cat_code, "DEL-SPU-001")

    r = await client.delete(f"/api/v1/operator/products/{pid}", headers=headers)
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_operator_product_detail_two_tier(client: AsyncClient):
    """运营详情包含 skus[]、i18n、属性、图片。"""
    headers = await _login_operator(client)
    cat_code = await _get_first_category_code(client)
    pid = await _create_test_product(client, headers, cat_code, "OPR-DETAIL-001")
    await _create_test_sku(client, headers, pid, "OPR-DET-SKU-001")

    r = await client.get(f"/api/v1/operator/products/{pid}", headers=headers)
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["spu_code"] == "OPR-DETAIL-001"
    assert data["status"] == "DRAFT"
    assert "skus" in data
    assert len(data["skus"]) >= 1


# ── 运营 SKU CRUD ────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_sku_success(client: AsyncClient):
    headers = await _login_operator(client)
    cat_code = await _get_first_category_code(client)
    pid = await _create_test_product(client, headers, cat_code, "SKU-CREATE-001")
    sku_id = await _create_test_sku(client, headers, pid, "SKU-C-001")
    assert sku_id > 0


@pytest.mark.asyncio
async def test_create_sku_duplicate_code(client: AsyncClient):
    """SKU 编码重复 → 400 / 50003。"""
    headers = await _login_operator(client)
    cat_code = await _get_first_category_code(client)
    pid = await _create_test_product(client, headers, cat_code, "SKU-DUP-001")
    await _create_test_sku(client, headers, pid, "DUP-SKU-CODE")

    r = await client.post(
        f"/api/v1/operator/products/{pid}/skus",
        headers=headers,
        json={"sku_code": "DUP-SKU-CODE", "unit": "pcs", "moq": 1},
    )
    assert r.status_code == 400
    assert r.json()["code"] == 50003


@pytest.mark.asyncio
async def test_update_sku(client: AsyncClient):
    headers = await _login_operator(client)
    cat_code = await _get_first_category_code(client)
    pid = await _create_test_product(client, headers, cat_code, "SKU-UPD-001")
    sku_id = await _create_test_sku(client, headers, pid, "SKU-UPD-S001")

    r = await client.put(
        f"/api/v1/operator/products/{pid}/skus/{sku_id}",
        headers=headers,
        json={"moq": 100, "price_min": 3.00},
    )
    assert r.status_code == 200
    assert r.json()["code"] == 0


@pytest.mark.asyncio
async def test_delete_sku(client: AsyncClient):
    headers = await _login_operator(client)
    cat_code = await _get_first_category_code(client)
    pid = await _create_test_product(client, headers, cat_code, "SKU-DEL-001")
    sku_id = await _create_test_sku(client, headers, pid, "SKU-DEL-S001")

    r = await client.delete(
        f"/api/v1/operator/products/{pid}/skus/{sku_id}", headers=headers,
    )
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_list_skus(client: AsyncClient):
    headers = await _login_operator(client)
    cat_code = await _get_first_category_code(client)
    pid = await _create_test_product(client, headers, cat_code, "SKU-LIST-001")
    await _create_test_sku(client, headers, pid, "SKU-LIST-S001")
    await _create_test_sku(client, headers, pid, "SKU-LIST-S002", is_default=False)

    r = await client.get(
        f"/api/v1/operator/products/{pid}/skus", headers=headers,
    )
    assert r.status_code == 200
    items = r.json()["data"]
    assert len(items) == 2


@pytest.mark.asyncio
async def test_default_sku_uniqueness(client: AsyncClient):
    """设新默认 SKU 时，旧默认自动置 FALSE。"""
    headers = await _login_operator(client)
    cat_code = await _get_first_category_code(client)
    pid = await _create_test_product(client, headers, cat_code, "SKU-DEFAULT-001")
    sku1 = await _create_test_sku(client, headers, pid, "SKU-DEF-S001", is_default=True)
    sku2 = await _create_test_sku(client, headers, pid, "SKU-DEF-S002", is_default=True)

    # 查看 SKU 列表，只有一个 is_default=True
    r = await client.get(f"/api/v1/operator/products/{pid}/skus", headers=headers)
    items = r.json()["data"]
    default_count = sum(1 for s in items if s["is_default"])
    assert default_count == 1
    # 最后创建的应该是默认的
    default_sku = next(s for s in items if s["is_default"])
    assert default_sku["id"] == sku2


# ── 阶梯价 ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_sku_with_valid_price_tiers(client: AsyncClient):
    """创建 SKU 携带合法阶梯价。"""
    headers = await _login_operator(client)
    cat_code = await _get_first_category_code(client)
    pid = await _create_test_product(client, headers, cat_code, "TIER-VALID-001")

    tiers = [
        {"min_qty": 500, "max_qty": 999, "unit_price": 4.50, "currency": "TZS"},
        {"min_qty": 1000, "max_qty": None, "unit_price": 3.80, "currency": "TZS"},
    ]
    sku_id = await _create_test_sku(
        client, headers, pid, "TIER-V-S001", price_tiers=tiers,
    )

    # 查 SKU 列表确认阶梯价
    r = await client.get(f"/api/v1/operator/products/{pid}/skus", headers=headers)
    sku = next(s for s in r.json()["data"] if s["id"] == sku_id)
    assert len(sku["price_tiers"]) == 2
    assert sku["price_tiers"][0]["min_qty"] == 500


@pytest.mark.asyncio
async def test_price_tier_first_min_qty_must_equal_moq(client: AsyncClient):
    """首档 min_qty != moq → 400 / 50012。"""
    headers = await _login_operator(client)
    cat_code = await _get_first_category_code(client)
    pid = await _create_test_product(client, headers, cat_code, "TIER-MOQ-001")

    # moq=500, 但首档 min_qty=100
    tiers = [
        {"min_qty": 100, "max_qty": 499, "unit_price": 5.00},
        {"min_qty": 500, "max_qty": None, "unit_price": 4.00},
    ]
    r = await client.post(
        f"/api/v1/operator/products/{pid}/skus",
        headers=headers,
        json={"sku_code": "TIER-MOQ-S001", "unit": "pcs", "moq": 500, "price_tiers": tiers},
    )
    assert r.status_code == 400
    assert r.json()["code"] == 50012


@pytest.mark.asyncio
async def test_price_tier_must_be_continuous(client: AsyncClient):
    """阶梯价不连续 → 400 / 50012。"""
    headers = await _login_operator(client)
    cat_code = await _get_first_category_code(client)
    pid = await _create_test_product(client, headers, cat_code, "TIER-CONT-001")

    # gap: 500-999, then 1500-None (应该是 1000)
    tiers = [
        {"min_qty": 500, "max_qty": 999, "unit_price": 5.00},
        {"min_qty": 1500, "max_qty": None, "unit_price": 4.00},
    ]
    r = await client.post(
        f"/api/v1/operator/products/{pid}/skus",
        headers=headers,
        json={"sku_code": "TIER-CONT-S001", "unit": "pcs", "moq": 500, "price_tiers": tiers},
    )
    assert r.status_code == 400
    assert r.json()["code"] == 50012


@pytest.mark.asyncio
async def test_price_tier_must_decrease(client: AsyncClient):
    """阶梯价非递减 → 400 / 50012。"""
    headers = await _login_operator(client)
    cat_code = await _get_first_category_code(client)
    pid = await _create_test_product(client, headers, cat_code, "TIER-DEC-001")

    # 后档 unit_price >= 前档
    tiers = [
        {"min_qty": 500, "max_qty": 999, "unit_price": 4.00},
        {"min_qty": 1000, "max_qty": None, "unit_price": 5.00},
    ]
    r = await client.post(
        f"/api/v1/operator/products/{pid}/skus",
        headers=headers,
        json={"sku_code": "TIER-DEC-S001", "unit": "pcs", "moq": 500, "price_tiers": tiers},
    )
    assert r.status_code == 400
    assert r.json()["code"] == 50012


@pytest.mark.asyncio
async def test_price_tier_replace_on_update(client: AsyncClient):
    """编辑 SKU 时 price_tiers 整体替换。"""
    headers = await _login_operator(client)
    cat_code = await _get_first_category_code(client)
    pid = await _create_test_product(client, headers, cat_code, "TIER-REPL-001")

    tiers_v1 = [
        {"min_qty": 500, "max_qty": 999, "unit_price": 4.50},
        {"min_qty": 1000, "max_qty": None, "unit_price": 3.80},
    ]
    sku_id = await _create_test_sku(
        client, headers, pid, "TIER-R-S001", price_tiers=tiers_v1,
    )

    # 替换为单档
    tiers_v2 = [
        {"min_qty": 500, "max_qty": None, "unit_price": 4.00},
    ]
    r = await client.put(
        f"/api/v1/operator/products/{pid}/skus/{sku_id}",
        headers=headers,
        json={"price_tiers": tiers_v2},
    )
    assert r.status_code == 200

    # 验证
    r2 = await client.get(f"/api/v1/operator/products/{pid}/skus", headers=headers)
    sku = next(s for s in r2.json()["data"] if s["id"] == sku_id)
    assert len(sku["price_tiers"]) == 1


# ── 上架校验（三条）──────────────────────────────────────

@pytest.mark.asyncio
async def test_publish_no_sku_fails(client: AsyncClient):
    """上架无 SKU → 400 / 50004。"""
    headers = await _login_operator(client)
    cat_code = await _get_first_category_code(client)
    pid = await _create_test_product(client, headers, cat_code, "PUB-NOSKU-001")
    await _upload_test_image(client, headers, pid)

    r = await client.patch(
        f"/api/v1/operator/products/{pid}/status",
        headers=headers, json={"status": "ACTIVE"},
    )
    assert r.status_code == 400
    assert r.json()["code"] == 50004
    assert "SKU" in r.json()["message"]


@pytest.mark.asyncio
async def test_publish_no_image_fails(client: AsyncClient):
    """上架无图片 → 400 / 50004。"""
    headers = await _login_operator(client)
    cat_code = await _get_first_category_code(client)
    pid = await _create_test_product(client, headers, cat_code, "PUB-NOIMG-001")
    await _create_test_sku(client, headers, pid, "PUB-NOIMG-SKU")

    r = await client.patch(
        f"/api/v1/operator/products/{pid}/status",
        headers=headers, json={"status": "ACTIVE"},
    )
    assert r.status_code == 400
    assert r.json()["code"] == 50004
    assert "image" in r.json()["message"].lower()


@pytest.mark.asyncio
async def test_publish_sku_no_price_fails(client: AsyncClient):
    """上架 SKU 展示价为空 → 400 / 50004。"""
    headers = await _login_operator(client)
    cat_code = await _get_first_category_code(client)
    pid = await _create_test_product(client, headers, cat_code, "PUB-NOPRICE-001")
    await _upload_test_image(client, headers, pid)

    # 创建 SKU 不设价格
    r = await client.post(
        f"/api/v1/operator/products/{pid}/skus",
        headers=headers,
        json={"sku_code": "PUB-NP-SKU", "unit": "pcs", "moq": 100, "is_default": True},
    )
    assert r.status_code == 200

    r2 = await client.patch(
        f"/api/v1/operator/products/{pid}/status",
        headers=headers, json={"status": "ACTIVE"},
    )
    assert r2.status_code == 400
    assert r2.json()["code"] == 50004
    assert "price" in r2.json()["message"].lower()


@pytest.mark.asyncio
async def test_publish_success(client: AsyncClient):
    """满足三条件后上架成功。"""
    headers = await _login_operator(client)
    cat_code = await _get_first_category_code(client)
    pid = await _create_test_product(client, headers, cat_code, "PUB-OK-001")
    await _create_test_sku(client, headers, pid, "PUB-OK-SKU")
    await _upload_test_image(client, headers, pid)

    r = await client.patch(
        f"/api/v1/operator/products/{pid}/status",
        headers=headers, json={"status": "ACTIVE"},
    )
    assert r.status_code == 200
    assert r.json()["data"]["status"] == "ACTIVE"


# ── 图片 ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_upload_and_delete_image(client: AsyncClient):
    headers = await _login_operator(client)
    cat_code = await _get_first_category_code(client)
    pid = await _create_test_product(client, headers, cat_code, "IMG-SPU-001")

    img_id = await _upload_test_image(client, headers, pid)
    assert img_id > 0

    # 检查图片属性
    r = await client.get(f"/api/v1/operator/products/{pid}", headers=headers)
    images = r.json()["data"]["images"]
    assert len(images) >= 1
    assert images[0]["image_type"] == "MAIN"  # 第一张自动主图

    # 删除
    r2 = await client.delete(
        f"/api/v1/operator/products/{pid}/images/{img_id}", headers=headers,
    )
    assert r2.status_code == 200


@pytest.mark.asyncio
async def test_upload_image_with_sku_id(client: AsyncClient):
    """上传 SKU 级图片（sku_id 参数）。"""
    headers = await _login_operator(client)
    cat_code = await _get_first_category_code(client)
    pid = await _create_test_product(client, headers, cat_code, "IMG-SKU-001")
    sku_id = await _create_test_sku(client, headers, pid, "IMG-SKU-S001")

    from PIL import Image as PILImage
    buf = io.BytesIO()
    PILImage.new("RGB", (300, 300), color=(100, 200, 50)).save(buf, format="PNG")
    buf.seek(0)

    r = await client.post(
        f"/api/v1/operator/products/{pid}/images?sku_id={sku_id}",
        headers=headers,
        files={"file": ("sku.png", buf, "image/png")},
    )
    assert r.status_code == 200
    assert r.json()["data"]["sku_id"] == sku_id


# ── 供货关系（挂 SKU）────────────────────────────────────

@pytest.mark.asyncio
async def test_add_and_list_sku_supplier(client: AsyncClient):
    """绑定供应商到 SKU + 列表查询。"""
    headers = await _login_operator(client)
    cat_code = await _get_first_category_code(client)
    pid = await _create_test_product(client, headers, cat_code, "SUP-SKU-001")
    sku_id = await _create_test_sku(client, headers, pid, "SUP-SKU-S001")

    r = await client.post(
        f"/api/v1/operator/products/{pid}/skus/{sku_id}/suppliers",
        headers=headers,
        json={
            "supplier_org_id": 1,
            "supplier_price": 1.80,
            "supplier_currency": "CNY",
            "pvoc_status": "OBTAINED",
            "is_preferred": True,
        },
    )
    if r.status_code == 404:
        pytest.skip("No supplier org with id=1 in test DB")
    assert r.status_code == 200, r.text
    ps_id = r.json()["data"]["id"]

    r2 = await client.get(
        f"/api/v1/operator/products/{pid}/skus/{sku_id}/suppliers",
        headers=headers,
    )
    assert r2.status_code == 200
    items = r2.json()["data"]
    assert len(items) >= 1
    assert items[0]["supplier_currency"] == "CNY"
    assert items[0]["pvoc_status"] == "OBTAINED"


@pytest.mark.asyncio
async def test_duplicate_supplier_binding(client: AsyncClient):
    """重复绑定同一供应商到 SKU → 400 / 50007。"""
    headers = await _login_operator(client)
    cat_code = await _get_first_category_code(client)
    pid = await _create_test_product(client, headers, cat_code, "DUP-SUP-SKU-001")
    sku_id = await _create_test_sku(client, headers, pid, "DUP-SUP-SKU-S001")

    payload = {"supplier_org_id": 1, "supplier_price": 2.00}
    r1 = await client.post(
        f"/api/v1/operator/products/{pid}/skus/{sku_id}/suppliers",
        headers=headers, json=payload,
    )
    if r1.status_code == 404:
        pytest.skip("No supplier org with id=1")

    r2 = await client.post(
        f"/api/v1/operator/products/{pid}/skus/{sku_id}/suppliers",
        headers=headers, json=payload,
    )
    assert r2.status_code == 400
    assert r2.json()["code"] == 50007


# ── 审计断言 ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_audit_on_product_create(client: AsyncClient, db_session):
    """创建 SPU 后 audit_log 落一条。"""
    from sqlalchemy import text

    headers = await _login_operator(client)
    cat_code = await _get_first_category_code(client)

    before = (await db_session.execute(
        text("SELECT count(*) FROM audit_logs WHERE resource_type='product' AND action='CREATE'")
    )).scalar() or 0

    await _create_test_product(client, headers, cat_code, "AUDIT-CREATE-001")

    after = (await db_session.execute(
        text("SELECT count(*) FROM audit_logs WHERE resource_type='product' AND action='CREATE'")
    )).scalar() or 0
    assert after > before


@pytest.mark.asyncio
async def test_audit_on_sku_create(client: AsyncClient, db_session):
    """创建 SKU 后 audit_log 落一条。"""
    from sqlalchemy import text

    headers = await _login_operator(client)
    cat_code = await _get_first_category_code(client)
    pid = await _create_test_product(client, headers, cat_code, "AUDIT-SKU-001")

    before = (await db_session.execute(
        text("SELECT count(*) FROM audit_logs WHERE resource_type='product_sku' AND action='CREATE'")
    )).scalar() or 0

    await _create_test_sku(client, headers, pid, "AUDIT-SKU-S001")

    after = (await db_session.execute(
        text("SELECT count(*) FROM audit_logs WHERE resource_type='product_sku' AND action='CREATE'")
    )).scalar() or 0
    assert after > before


@pytest.mark.asyncio
async def test_audit_on_status_change(client: AsyncClient, db_session):
    """上下架后 audit_log 落一条 STATUS_CHANGE。"""
    from sqlalchemy import text

    headers = await _login_operator(client)
    cat_code = await _get_first_category_code(client)
    pid = await _create_test_product(client, headers, cat_code, "AUDIT-STATUS-001")
    await _create_test_sku(client, headers, pid, "AUDIT-STATUS-SKU")
    await _upload_test_image(client, headers, pid)

    before = (await db_session.execute(
        text("SELECT count(*) FROM audit_logs WHERE action='STATUS_CHANGE'")
    )).scalar() or 0

    await client.patch(
        f"/api/v1/operator/products/{pid}/status",
        headers=headers, json={"status": "ACTIVE"},
    )

    after = (await db_session.execute(
        text("SELECT count(*) FROM audit_logs WHERE action='STATUS_CHANGE'")
    )).scalar() or 0
    assert after > before


@pytest.mark.asyncio
async def test_no_audit_on_publish_validation_failure(client: AsyncClient, db_session):
    """上架校验失败不写审计。"""
    from sqlalchemy import text

    headers = await _login_operator(client)
    cat_code = await _get_first_category_code(client)
    pid = await _create_test_product(client, headers, cat_code, "AUDIT-NOLOG-001")

    before = (await db_session.execute(
        text("SELECT count(*) FROM audit_logs WHERE action='STATUS_CHANGE'")
    )).scalar() or 0

    r = await client.patch(
        f"/api/v1/operator/products/{pid}/status",
        headers=headers, json={"status": "ACTIVE"},
    )
    assert r.status_code == 400

    after = (await db_session.execute(
        text("SELECT count(*) FROM audit_logs WHERE action='STATUS_CHANGE'")
    )).scalar() or 0
    assert after == before


@pytest.mark.asyncio
async def test_no_audit_on_duplicate_supplier(client: AsyncClient, db_session):
    """重复绑定供应商不写审计。"""
    from sqlalchemy import text

    headers = await _login_operator(client)
    cat_code = await _get_first_category_code(client)
    pid = await _create_test_product(client, headers, cat_code, "AUDIT-NODUP-001")
    sku_id = await _create_test_sku(client, headers, pid, "AUDIT-NODUP-SKU")

    payload = {"supplier_org_id": 1, "supplier_price": 2.00}
    r1 = await client.post(
        f"/api/v1/operator/products/{pid}/skus/{sku_id}/suppliers",
        headers=headers, json=payload,
    )
    if r1.status_code == 404:
        pytest.skip("No supplier org with id=1")

    before = (await db_session.execute(
        text("SELECT count(*) FROM audit_logs")
    )).scalar() or 0

    r2 = await client.post(
        f"/api/v1/operator/products/{pid}/skus/{sku_id}/suppliers",
        headers=headers, json=payload,
    )
    assert r2.status_code == 400

    after = (await db_session.execute(
        text("SELECT count(*) FROM audit_logs")
    )).scalar() or 0
    assert after == before


# ── 品类属性模板 ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_attr_templates_endpoint(client: AsyncClient):
    cat_code = await _get_first_category_code(client)
    r = await client.get(f"/api/v1/categories/{cat_code}/attr-templates")
    assert r.status_code == 200
    assert r.json()["code"] == 0
    assert isinstance(r.json()["data"], list)
