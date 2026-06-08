"""商品目录模块测试 — v2 i18n 分列模式。

覆盖：
- 买方接口两层口径 + 断层断言（不含供应商字段）
- 运营 SPU/SKU/阶梯价/图片/供货 增改删
- 默认 SKU 唯一性、阶梯价规则校验、上架校验（三条）
- 审计断言（写操作落审计、校验失败不落审计）
- v2 i18n 断言（分列字段 + source_lang + trans_meta）
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


async def _get_first_category_code(client: AsyncClient, level: int = 3) -> str:
    """获取第一个有效品类 code。默认 L3(叶子),可按需指定层级。"""
    r = await client.get(f"/api/v1/categories?level={level}&is_active=true")
    assert r.status_code == 200
    items = r.json()["data"]
    assert len(items) > 0, f"No level-{level} categories found — seed may not have run"
    return items[0]["code"]


async def _create_test_product(
    client: AsyncClient, headers: dict, category_code: str,
    spu_code: str = "TEST-SPU-001",
) -> int:
    """创建 SPU，返回 product id。v2 i18n: 传单语言值 + source_lang。"""
    r = await client.post(
        "/api/v1/operator/products",
        headers=headers,
        json={
            "category_code": category_code,
            "spu_code": spu_code,
            "name": "测试LED面板灯36W",
            "origin": "中国",
            "brand": "OEM",
            "certifications": ["PVoC", "CoC"],
            "is_featured": False,
            "status": "DRAFT",
            "source_lang": "zh",
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
    payload = {
        "sku_code": sku_code,
        "unit": "PCS",
        "moq": 500,
        "price_min": 2.50,
        "price_max": 4.80,
        "currency": "TZS",
        "is_default": is_default,
        "status": "ACTIVE",
        "source_lang": "zh",
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


# ── 买方接口：两层口径 + 断层断言 ────────────────────────

@pytest.mark.asyncio
async def test_public_products_list_no_auth(client: AsyncClient):
    r = await client.get("/api/v1/products")
    assert r.status_code == 200
    assert r.json()["code"] == 0
    assert "items" in r.json()["data"]


@pytest.mark.asyncio
async def test_public_products_only_active(client: AsyncClient):
    headers = await _login_operator(client)
    cat_code = await _get_first_category_code(client)
    await _create_test_product(client, headers, cat_code, "PUB-DRAFT-001")

    r = await client.get("/api/v1/products?keyword=PUB-DRAFT-001")
    assert r.status_code == 200
    items = r.json()["data"]["items"]
    assert all(item["spu_code"] != "PUB-DRAFT-001" for item in items)


@pytest.mark.asyncio
async def test_public_product_detail_draft_404(client: AsyncClient):
    headers = await _login_operator(client)
    cat_code = await _get_first_category_code(client)
    pid = await _create_test_product(client, headers, cat_code, "PUB-DETAIL-404")
    r = await client.get(f"/api/v1/products/{pid}")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_public_list_two_tier_fields(client: AsyncClient):
    headers = await _login_operator(client)
    cat_code = await _get_first_category_code(client)
    pid = await _create_test_product(client, headers, cat_code, "PUB-2TIER-001")
    await _create_test_sku(client, headers, pid, "PUB-2TIER-SKU-001")
    await _upload_test_image(client, headers, pid)

    r = await client.patch(
        f"/api/v1/operator/products/{pid}/status",
        headers=headers, json={"status": "ACTIVE"},
    )
    assert r.status_code == 200, r.text

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

    sku = data["skus"][0]
    assert "price_tiers" in sku
    assert "sku_code" in sku
    assert "moq" in sku


@pytest.mark.asyncio
async def test_public_isolation_no_supplier_fields(client: AsyncClient):
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

    r = await client.get("/api/v1/products?keyword=PUB-ISO-001")
    for item in r.json()["data"]["items"]:
        _assert_no_supplier(item, "list_item")

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
    headers = await _login_operator(client)
    cat_code = await _get_first_category_code(client)
    await _create_test_product(client, headers, cat_code, "DUP-SPU-001")

    r = await client.post(
        "/api/v1/operator/products",
        headers=headers,
        json={"category_code": cat_code, "spu_code": "DUP-SPU-001", "name": "Dup", "source_lang": "zh"},
    )
    assert r.status_code == 400
    assert r.json()["code"] == 40202


@pytest.mark.asyncio
async def test_create_product_no_permission(client: AsyncClient):
    headers = await _login_buyer(client)
    r = await client.post(
        "/api/v1/operator/products",
        headers=headers,
        json={"category_code": "01", "spu_code": "BUYER-NOPE", "name": "Fail", "source_lang": "zh"},
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
        json={"name": "更新后的名称"},
    )
    assert r.status_code == 200
    assert r.json()["code"] == 0


@pytest.mark.asyncio
async def test_update_product_rejects_category_code(client: AsyncClient):
    """普通商品编辑不允许改类目;类目迁移需走单独设计。"""
    headers = await _login_operator(client)
    cat_code = await _get_first_category_code(client)
    pid = await _create_test_product(client, headers, cat_code, "UPD-CAT-LOCK")

    r = await client.put(
        f"/api/v1/operator/products/{pid}",
        headers=headers,
        json={"category_code": "01"},
    )
    assert r.status_code == 422
    assert r.json()["code"] == 42200


@pytest.mark.asyncio
async def test_delete_draft_product(client: AsyncClient):
    headers = await _login_operator(client)
    cat_code = await _get_first_category_code(client)
    pid = await _create_test_product(client, headers, cat_code, "DEL-SPU-001")

    r = await client.delete(f"/api/v1/operator/products/{pid}", headers=headers)
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_operator_product_detail_v2_i18n(client: AsyncClient):
    """运营详情包含 v2 i18n 分列字段: *_zh, *_en, source_lang。"""
    headers = await _login_operator(client)
    cat_code = await _get_first_category_code(client)
    pid = await _create_test_product(client, headers, cat_code, "OPR-I18N-001")
    await _create_test_sku(client, headers, pid, "OPR-I18N-SKU-001")

    r = await client.get(f"/api/v1/operator/products/{pid}", headers=headers)
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["spu_code"] == "OPR-I18N-001"
    assert data["status"] == "DRAFT"
    # v2 i18n 分列
    assert "name_zh" in data
    assert "name_en" in data
    assert "source_lang" in data
    assert data["source_lang"] == "zh"
    assert data["name_zh"] == "测试LED面板灯36W"
    # name_en 由 mock 翻译填充(mock 返回原文)
    assert data["name_en"] is not None
    assert "skus" in data
    assert len(data["skus"]) >= 1
    # SKU 也有 v2 i18n
    sku = data["skus"][0]
    assert "source_lang" in sku


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
    headers = await _login_operator(client)
    cat_code = await _get_first_category_code(client)
    pid = await _create_test_product(client, headers, cat_code, "SKU-DUP-001")
    await _create_test_sku(client, headers, pid, "DUP-SKU-CODE")

    r = await client.post(
        f"/api/v1/operator/products/{pid}/skus",
        headers=headers,
        json={"sku_code": "DUP-SKU-CODE", "unit": "PCS", "moq": 1, "source_lang": "zh"},
    )
    assert r.status_code == 400
    assert r.json()["code"] == 40203


@pytest.mark.asyncio
@pytest.mark.parametrize("bad_unit", ["pcs", "件", "INVALID"])
async def test_create_sku_invalid_unit_rejected(client: AsyncClient, bad_unit: str):
    """非法 unit code（小写 / 中文 / 未注册值）被 422 拒绝。"""
    headers = await _login_operator(client)
    cat_code = await _get_first_category_code(client)
    pid = await _create_test_product(client, headers, cat_code, f"UNIT-BAD-{bad_unit}")

    r = await client.post(
        f"/api/v1/operator/products/{pid}/skus",
        headers=headers,
        json={"sku_code": f"UNIT-BAD-SKU-{bad_unit}", "unit": bad_unit, "moq": 100, "source_lang": "zh"},
    )
    assert r.status_code == 422
    assert r.json()["code"] == 42200


@pytest.mark.asyncio
async def test_create_sku_rejects_invalid_price_range(client: AsyncClient):
    headers = await _login_operator(client)
    cat_code = await _get_first_category_code(client)
    pid = await _create_test_product(client, headers, cat_code, "SKU-BAD-PRICE")

    r = await client.post(
        f"/api/v1/operator/products/{pid}/skus",
        headers=headers,
        json={
            "sku_code": "SKU-BAD-PRICE-S001",
            "unit": "PCS",
            "moq": 100,
            "price_min": 5.00,
            "price_max": 3.00,
            "source_lang": "zh",
        },
    )
    assert r.status_code == 400
    assert r.json()["code"] == 40217


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
async def test_update_sku_rejects_invalid_lead_time_range(client: AsyncClient):
    headers = await _login_operator(client)
    cat_code = await _get_first_category_code(client)
    pid = await _create_test_product(client, headers, cat_code, "SKU-BAD-LEAD")
    sku_id = await _create_test_sku(client, headers, pid, "SKU-BAD-LEAD-S001")

    r = await client.put(
        f"/api/v1/operator/products/{pid}/skus/{sku_id}",
        headers=headers,
        json={"lead_time_min": 30, "lead_time_max": 7},
    )
    assert r.status_code == 400
    assert r.json()["code"] == 40217


@pytest.mark.asyncio
async def test_update_sku_requires_product_ownership(client: AsyncClient):
    headers = await _login_operator(client)
    cat_code = await _get_first_category_code(client)
    pid1 = await _create_test_product(client, headers, cat_code, "SKU-OWN-P1")
    pid2 = await _create_test_product(client, headers, cat_code, "SKU-OWN-P2")
    sku1 = await _create_test_sku(client, headers, pid1, "SKU-OWN-P1-S001")

    r = await client.put(
        f"/api/v1/operator/products/{pid2}/skus/{sku1}",
        headers=headers,
        json={"moq": 200},
    )
    assert r.status_code == 404


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
async def test_delete_sku_requires_product_ownership(client: AsyncClient):
    headers = await _login_operator(client)
    cat_code = await _get_first_category_code(client)
    pid1 = await _create_test_product(client, headers, cat_code, "SKU-DEL-OWN-P1")
    pid2 = await _create_test_product(client, headers, cat_code, "SKU-DEL-OWN-P2")
    sku1 = await _create_test_sku(client, headers, pid1, "SKU-DEL-OWN-S001")

    r = await client.delete(
        f"/api/v1/operator/products/{pid2}/skus/{sku1}",
        headers=headers,
    )
    assert r.status_code == 404


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
    headers = await _login_operator(client)
    cat_code = await _get_first_category_code(client)
    pid = await _create_test_product(client, headers, cat_code, "SKU-DEFAULT-001")
    sku1 = await _create_test_sku(client, headers, pid, "SKU-DEF-S001", is_default=True)
    sku2 = await _create_test_sku(client, headers, pid, "SKU-DEF-S002", is_default=True)

    r = await client.get(f"/api/v1/operator/products/{pid}/skus", headers=headers)
    items = r.json()["data"]
    default_count = sum(1 for s in items if s["is_default"])
    assert default_count == 1
    default_sku = next(s for s in items if s["is_default"])
    assert default_sku["id"] == sku2


# ── 阶梯价 ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_sku_with_valid_price_tiers(client: AsyncClient):
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

    r = await client.get(f"/api/v1/operator/products/{pid}/skus", headers=headers)
    sku = next(s for s in r.json()["data"] if s["id"] == sku_id)
    assert len(sku["price_tiers"]) == 2
    assert sku["price_tiers"][0]["min_qty"] == 500


@pytest.mark.asyncio
async def test_price_tier_first_min_qty_must_equal_moq(client: AsyncClient):
    headers = await _login_operator(client)
    cat_code = await _get_first_category_code(client)
    pid = await _create_test_product(client, headers, cat_code, "TIER-MOQ-001")

    tiers = [
        {"min_qty": 100, "max_qty": 499, "unit_price": 5.00},
        {"min_qty": 500, "max_qty": None, "unit_price": 4.00},
    ]
    r = await client.post(
        f"/api/v1/operator/products/{pid}/skus",
        headers=headers,
        json={"sku_code": "TIER-MOQ-S001", "unit": "PCS", "moq": 500, "price_tiers": tiers, "source_lang": "zh"},
    )
    assert r.status_code == 400
    assert r.json()["code"] == 40211


@pytest.mark.asyncio
async def test_price_tier_must_be_continuous(client: AsyncClient):
    headers = await _login_operator(client)
    cat_code = await _get_first_category_code(client)
    pid = await _create_test_product(client, headers, cat_code, "TIER-CONT-001")

    tiers = [
        {"min_qty": 500, "max_qty": 999, "unit_price": 5.00},
        {"min_qty": 1500, "max_qty": None, "unit_price": 4.00},
    ]
    r = await client.post(
        f"/api/v1/operator/products/{pid}/skus",
        headers=headers,
        json={"sku_code": "TIER-CONT-S001", "unit": "PCS", "moq": 500, "price_tiers": tiers, "source_lang": "zh"},
    )
    assert r.status_code == 400
    assert r.json()["code"] == 40211


@pytest.mark.asyncio
async def test_price_tier_must_decrease(client: AsyncClient):
    headers = await _login_operator(client)
    cat_code = await _get_first_category_code(client)
    pid = await _create_test_product(client, headers, cat_code, "TIER-DEC-001")

    tiers = [
        {"min_qty": 500, "max_qty": 999, "unit_price": 4.00},
        {"min_qty": 1000, "max_qty": None, "unit_price": 5.00},
    ]
    r = await client.post(
        f"/api/v1/operator/products/{pid}/skus",
        headers=headers,
        json={"sku_code": "TIER-DEC-S001", "unit": "PCS", "moq": 500, "price_tiers": tiers, "source_lang": "zh"},
    )
    assert r.status_code == 400
    assert r.json()["code"] == 40211


@pytest.mark.asyncio
async def test_price_tier_replace_on_update(client: AsyncClient):
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

    tiers_v2 = [
        {"min_qty": 500, "max_qty": None, "unit_price": 4.00},
    ]
    r = await client.put(
        f"/api/v1/operator/products/{pid}/skus/{sku_id}",
        headers=headers,
        json={"price_tiers": tiers_v2},
    )
    assert r.status_code == 200

    r2 = await client.get(f"/api/v1/operator/products/{pid}/skus", headers=headers)
    sku = next(s for s in r2.json()["data"] if s["id"] == sku_id)
    assert len(sku["price_tiers"]) == 1


# ── 上架校验（三条）──────────────────────────────────────

@pytest.mark.asyncio
async def test_publish_no_sku_fails(client: AsyncClient):
    headers = await _login_operator(client)
    cat_code = await _get_first_category_code(client)
    pid = await _create_test_product(client, headers, cat_code, "PUB-NOSKU-001")
    await _upload_test_image(client, headers, pid)

    r = await client.patch(
        f"/api/v1/operator/products/{pid}/status",
        headers=headers, json={"status": "ACTIVE"},
    )
    assert r.status_code == 400
    assert r.json()["code"] == 40204
    assert "SKU" in r.json()["message"]


@pytest.mark.asyncio
async def test_publish_no_image_fails(client: AsyncClient):
    headers = await _login_operator(client)
    cat_code = await _get_first_category_code(client)
    pid = await _create_test_product(client, headers, cat_code, "PUB-NOIMG-001")
    await _create_test_sku(client, headers, pid, "PUB-NOIMG-SKU")

    r = await client.patch(
        f"/api/v1/operator/products/{pid}/status",
        headers=headers, json={"status": "ACTIVE"},
    )
    assert r.status_code == 400
    assert r.json()["code"] == 40204
    assert "image" in r.json()["message"].lower()


@pytest.mark.asyncio
async def test_publish_sku_no_price_fails(client: AsyncClient):
    headers = await _login_operator(client)
    cat_code = await _get_first_category_code(client)
    pid = await _create_test_product(client, headers, cat_code, "PUB-NOPRICE-001")
    await _upload_test_image(client, headers, pid)

    r = await client.post(
        f"/api/v1/operator/products/{pid}/skus",
        headers=headers,
        json={"sku_code": "PUB-NP-SKU", "unit": "PCS", "moq": 100, "is_default": True, "source_lang": "zh"},
    )
    assert r.status_code == 200

    r2 = await client.patch(
        f"/api/v1/operator/products/{pid}/status",
        headers=headers, json={"status": "ACTIVE"},
    )
    assert r2.status_code == 400
    assert r2.json()["code"] == 40204
    assert "price" in r2.json()["message"].lower()


@pytest.mark.asyncio
async def test_publish_success(client: AsyncClient):
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

    r = await client.get(f"/api/v1/operator/products/{pid}", headers=headers)
    images = r.json()["data"]["images"]
    assert len(images) >= 1
    assert images[0]["image_type"] == "MAIN"

    r2 = await client.delete(
        f"/api/v1/operator/products/{pid}/images/{img_id}", headers=headers,
    )
    assert r2.status_code == 200


@pytest.mark.asyncio
async def test_upload_image_with_sku_id(client: AsyncClient):
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
    assert r2.json()["code"] == 40206


@pytest.mark.asyncio
async def test_sku_supplier_requires_product_and_sku_ownership(client: AsyncClient):
    headers = await _login_operator(client)
    cat_code = await _get_first_category_code(client)
    pid1 = await _create_test_product(client, headers, cat_code, "SUP-OWN-P1")
    pid2 = await _create_test_product(client, headers, cat_code, "SUP-OWN-P2")
    sku1 = await _create_test_sku(client, headers, pid1, "SUP-OWN-P1-S001")
    sku2 = await _create_test_sku(client, headers, pid2, "SUP-OWN-P2-S001")

    create_resp = await client.post(
        f"/api/v1/operator/products/{pid1}/skus/{sku1}/suppliers",
        headers=headers,
        json={"supplier_org_id": 1, "supplier_price": 2.00},
    )
    if create_resp.status_code == 404:
        pytest.skip("No supplier org with id=1")
    assert create_resp.status_code == 200, create_resp.text
    ps_id = create_resp.json()["data"]["id"]

    list_resp = await client.get(
        f"/api/v1/operator/products/{pid2}/skus/{sku1}/suppliers",
        headers=headers,
    )
    assert list_resp.status_code == 404

    update_resp = await client.put(
        f"/api/v1/operator/products/{pid2}/skus/{sku2}/suppliers/{ps_id}",
        headers=headers,
        json={"supplier_price": 3.00},
    )
    assert update_resp.status_code == 404

    delete_resp = await client.delete(
        f"/api/v1/operator/products/{pid2}/skus/{sku2}/suppliers/{ps_id}",
        headers=headers,
    )
    assert delete_resp.status_code == 404


# ── 审计断言（通过 audit API 查询）────────────────────────

async def _get_audit_admin_headers(client: AsyncClient) -> dict[str, str]:
    from app.core.config import settings
    r = await client.post(
        "/api/v1/auth/login",
        json={"identifier": settings.SUPER_ADMIN_EMAIL, "password": settings.SUPER_ADMIN_INITIAL_PASSWORD},
    )
    assert r.status_code == 200
    token = r.json()["data"]["access_token"]
    h = {"Authorization": f"Bearer {token}"}

    new_pw = "TestNewPass_999!"
    r2 = await client.post("/api/v1/auth/change-password", headers=h, json={
        "old_password": settings.SUPER_ADMIN_INITIAL_PASSWORD, "new_password": new_pw,
    })
    assert r2.status_code == 200

    r3 = await client.post("/api/v1/auth/login", json={
        "identifier": settings.SUPER_ADMIN_EMAIL, "password": new_pw,
    })
    assert r3.status_code == 200
    return {"Authorization": f"Bearer {r3.json()['data']['access_token']}"}


async def _query_audit_count(
    client: AsyncClient, admin_headers: dict,
    resource_type: str | None = None, action: str | None = None,
) -> int:
    params = {}
    if resource_type:
        params["resource_type"] = resource_type
    if action:
        params["action"] = action
    r = await client.get("/api/v1/admin/audit-logs", headers=admin_headers, params=params)
    assert r.status_code == 200, r.text
    return r.json()["data"]["total"]


@pytest.mark.asyncio
async def test_audit_on_product_create(client: AsyncClient):
    admin_h = await _get_audit_admin_headers(client)
    op_h = await _login_operator(client)
    cat_code = await _get_first_category_code(client)

    before = await _query_audit_count(client, admin_h, resource_type="product", action="CREATE")
    await _create_test_product(client, op_h, cat_code, "AUDIT-CREATE-001")
    after = await _query_audit_count(client, admin_h, resource_type="product", action="CREATE")
    assert after > before


@pytest.mark.asyncio
async def test_audit_on_sku_create(client: AsyncClient):
    admin_h = await _get_audit_admin_headers(client)
    op_h = await _login_operator(client)
    cat_code = await _get_first_category_code(client)
    pid = await _create_test_product(client, op_h, cat_code, "AUDIT-SKU-001")

    before = await _query_audit_count(client, admin_h, resource_type="product_sku", action="CREATE")
    await _create_test_sku(client, op_h, pid, "AUDIT-SKU-S001")
    after = await _query_audit_count(client, admin_h, resource_type="product_sku", action="CREATE")
    assert after > before


@pytest.mark.asyncio
async def test_audit_on_status_change(client: AsyncClient):
    admin_h = await _get_audit_admin_headers(client)
    op_h = await _login_operator(client)
    cat_code = await _get_first_category_code(client)
    pid = await _create_test_product(client, op_h, cat_code, "AUDIT-STATUS-001")
    await _create_test_sku(client, op_h, pid, "AUDIT-STATUS-SKU")
    await _upload_test_image(client, op_h, pid)

    before = await _query_audit_count(client, admin_h, action="STATUS_CHANGE")
    await client.patch(
        f"/api/v1/operator/products/{pid}/status",
        headers=op_h, json={"status": "ACTIVE"},
    )
    after = await _query_audit_count(client, admin_h, action="STATUS_CHANGE")
    assert after > before


@pytest.mark.asyncio
async def test_no_audit_on_publish_validation_failure(client: AsyncClient):
    admin_h = await _get_audit_admin_headers(client)
    op_h = await _login_operator(client)
    cat_code = await _get_first_category_code(client)
    pid = await _create_test_product(client, op_h, cat_code, "AUDIT-NOLOG-001")

    before = await _query_audit_count(client, admin_h, action="STATUS_CHANGE")
    r = await client.patch(
        f"/api/v1/operator/products/{pid}/status",
        headers=op_h, json={"status": "ACTIVE"},
    )
    assert r.status_code == 400
    after = await _query_audit_count(client, admin_h, action="STATUS_CHANGE")
    assert after == before


@pytest.mark.asyncio
async def test_no_audit_on_duplicate_supplier(client: AsyncClient):
    admin_h = await _get_audit_admin_headers(client)
    op_h = await _login_operator(client)
    cat_code = await _get_first_category_code(client)
    pid = await _create_test_product(client, op_h, cat_code, "AUDIT-NODUP-001")
    sku_id = await _create_test_sku(client, op_h, pid, "AUDIT-NODUP-SKU")

    payload = {"supplier_org_id": 1, "supplier_price": 2.00}
    r1 = await client.post(
        f"/api/v1/operator/products/{pid}/skus/{sku_id}/suppliers",
        headers=op_h, json=payload,
    )
    if r1.status_code == 404:
        pytest.skip("No supplier org with id=1")

    before = await _query_audit_count(client, admin_h)
    r2 = await client.post(
        f"/api/v1/operator/products/{pid}/skus/{sku_id}/suppliers",
        headers=op_h, json=payload,
    )
    assert r2.status_code == 400
    after = await _query_audit_count(client, admin_h)
    assert after == before


# ── 品类属性模板 ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_attr_templates_endpoint(client: AsyncClient):
    headers = await _login_operator(client)
    cat_code = await _get_first_category_code(client)
    r = await client.get(
        f"/api/v1/operator/products/attr-templates/{cat_code}",
        headers=headers,
    )
    assert r.status_code == 200
    assert r.json()["code"] == 0
    assert isinstance(r.json()["data"], list)


# ── 属性模板祖先链继承 ────────────────────────────────────

async def _seed_template_hierarchy(db_session):
    """构建 3 级品类 + 各级属性模板,用于祖先链继承测试。"""
    from sqlalchemy import text
    from app.db.base import _utcnow
    from app.db.models.category import Category
    from app.db.models.attr_template import AttrTemplate

    now = _utcnow()

    # 插入测试品类(T 前缀避免与 seed 冲突)
    for code, name, level, parent in [
        ("T1", "测试一级", 1, None),
        ("T1.001", "测试二级", 2, "T1"),
        ("T1.001.001", "测试三级", 3, "T1.001"),
    ]:
        db_session.add(Category(
            code=code, name_zh=name, level=level, parent_code=parent,
            sort_order=0, is_active=True, created_at=now, updated_at=now,
        ))
    await db_session.flush()

    # L1 模板: 2 个属性
    db_session.add(AttrTemplate(
        category_code="T1", attr_key="brand", display_name="品牌",
        attr_type="text", sort_order=10, scope="SPU",
    ))
    db_session.add(AttrTemplate(
        category_code="T1", attr_key="cert", display_name="认证",
        attr_type="text", sort_order=20, scope="SPU",
    ))
    # L2 模板: 1 个属性
    db_session.add(AttrTemplate(
        category_code="T1.001", attr_key="material", display_name="材质",
        attr_type="text", sort_order=10, scope="SKU",
    ))
    # L3 模板: 1 个属性 + 1 个覆盖 L1 的 brand
    db_session.add(AttrTemplate(
        category_code="T1.001.001", attr_key="thickness", display_name="厚度",
        attr_type="text", sort_order=10, scope="SKU",
    ))
    db_session.add(AttrTemplate(
        category_code="T1.001.001", attr_key="brand", display_name="品牌(L3覆盖)",
        attr_type="select", sort_order=20, scope="SPU",
    ))
    await db_session.commit()


@pytest.mark.asyncio
async def test_attr_template_l3_inherits_l1(client: AsyncClient, db_session):
    """L3 分类能继承到 L1 的模板(不再返回空)。"""
    await _seed_template_hierarchy(db_session)
    headers = await _login_operator(client)

    r = await client.get(
        "/api/v1/operator/products/attr-templates/T1.001.001",
        headers=headers,
    )
    assert r.status_code == 200
    keys = [t["attr_key"] for t in r.json()["data"]]
    # L1(brand, cert) + L2(material) + L3(thickness, brand覆盖) → 去重后 4 个
    assert len(keys) == 4
    assert "brand" in keys
    assert "cert" in keys
    assert "material" in keys
    assert "thickness" in keys


@pytest.mark.asyncio
async def test_attr_template_leaf_overrides_ancestor(client: AsyncClient, db_session):
    """同一 attr_key 在多级出现时,取最深(L3)版本。"""
    await _seed_template_hierarchy(db_session)
    headers = await _login_operator(client)

    r = await client.get(
        "/api/v1/operator/products/attr-templates/T1.001.001",
        headers=headers,
    )
    data = r.json()["data"]
    brand = next(t for t in data if t["attr_key"] == "brand")
    # L3 覆盖 L1:display_name 和 attr_type 应为 L3 版本
    assert brand["display_name"] == "品牌(L3覆盖)"
    assert brand["attr_type"] == "select"


@pytest.mark.asyncio
async def test_attr_template_sorted_by_level_then_sort_order(client: AsyncClient, db_session):
    """返回按 level 升序(L1→L2→L3),同级按 sort_order 升序。"""
    await _seed_template_hierarchy(db_session)
    headers = await _login_operator(client)

    r = await client.get(
        "/api/v1/operator/products/attr-templates/T1.001.001",
        headers=headers,
    )
    keys = [t["attr_key"] for t in r.json()["data"]]
    # L1: cert(brand 被 L3 覆盖,不出现在 L1 位置) → L2: material → L3: thickness, brand
    assert keys == ["cert", "material", "thickness", "brand"]


@pytest.mark.asyncio
async def test_attr_template_l1_only_returns_own(client: AsyncClient, db_session):
    """传 L1 分类只返回其自身模板,无祖先。"""
    await _seed_template_hierarchy(db_session)
    headers = await _login_operator(client)

    r = await client.get(
        "/api/v1/operator/products/attr-templates/T1",
        headers=headers,
    )
    keys = [t["attr_key"] for t in r.json()["data"]]
    assert keys == ["brand", "cert"]


@pytest.mark.asyncio
async def test_attr_template_nonexistent_code_returns_empty(client: AsyncClient):
    """传不存在的 code 返回空列表。"""
    headers = await _login_operator(client)

    r = await client.get(
        "/api/v1/operator/products/attr-templates/DOES_NOT_EXIST",
        headers=headers,
    )
    assert r.status_code == 200
    assert r.json()["data"] == []


# ── 属性治理(v0.8) ────────────────────────────────────────


async def _create_product_in_test_category(
    client: AsyncClient, headers: dict, db_session,
    spu_code: str,
) -> tuple[int, str]:
    """在测试品类 T1.001.001 下创建商品,返回 (product_id, category_code)。
    需先调用 _seed_template_hierarchy 建立测试品类和模板。
    """
    cat_code = "T1.001.001"
    pid = await _create_test_product(client, headers, cat_code, spu_code)
    return pid, cat_code


@pytest.mark.asyncio
async def test_attr_spu_level_create_and_read(client: AsyncClient, db_session):
    """SPU 级属性(scope=SPU)通过 update_product 创建/读出,unit/sort_order/display_name 从模板取。"""
    await _seed_template_hierarchy(db_session)
    headers = await _login_operator(client)
    pid, _ = await _create_product_in_test_category(client, headers, db_session, "ATTR-SPU-001")

    r = await client.put(
        f"/api/v1/operator/products/{pid}",
        headers=headers,
        json={"attributes": [
            {"attr_key": "brand", "attr_value": "OEM"},
        ]},
    )
    assert r.status_code == 200

    r2 = await client.get(f"/api/v1/operator/products/{pid}", headers=headers)
    attrs = r2.json()["data"]["attributes"]
    assert len(attrs) == 1
    assert attrs[0]["attr_key"] == "brand"
    assert attrs[0]["attr_value"] == "OEM"
    assert attrs[0]["display_name"] == "品牌(L3覆盖)"
    assert attrs[0]["sku_id"] is None


@pytest.mark.asyncio
async def test_attr_sku_level_via_sku_create(client: AsyncClient, db_session):
    """SKU 级属性通过 SkuCreate.attributes 创建,落库为 SKU 级。"""
    await _seed_template_hierarchy(db_session)
    headers = await _login_operator(client)
    pid, _ = await _create_product_in_test_category(client, headers, db_session, "ATTR-SKU-002")

    r = await client.post(
        f"/api/v1/operator/products/{pid}/skus",
        headers=headers,
        json={
            "unit": "PCS", "moq": 100,
            "attributes": [
                {"attr_key": "thickness", "attr_value": "2mm"},
            ],
        },
    )
    assert r.status_code == 200
    sku_id = r.json()["data"]["id"]

    # 商品详情中 SKU 应有属性
    detail = (await client.get(f"/api/v1/operator/products/{pid}", headers=headers)).json()["data"]
    sku = next(s for s in detail["skus"] if s["id"] == sku_id)
    assert len(sku["attributes"]) == 1
    assert sku["attributes"][0]["attr_key"] == "thickness"
    assert sku["attributes"][0]["attr_value"] == "2mm"


@pytest.mark.asyncio
async def test_attr_sku_level_via_sku_update(client: AsyncClient, db_session):
    """SKU 级属性通过 SkuUpdate.attributes 编辑(整体替换)。"""
    await _seed_template_hierarchy(db_session)
    headers = await _login_operator(client)
    pid, _ = await _create_product_in_test_category(client, headers, db_session, "ATTR-SKUUP-001")

    # 创建 SKU 带属性
    r = await client.post(
        f"/api/v1/operator/products/{pid}/skus",
        headers=headers,
        json={
            "unit": "PCS", "moq": 50,
            "attributes": [
                {"attr_key": "thickness", "attr_value": "1mm"},
            ],
        },
    )
    sku_id = r.json()["data"]["id"]

    # 编辑 SKU 属性(整体替换)
    r2 = await client.put(
        f"/api/v1/operator/products/{pid}/skus/{sku_id}",
        headers=headers,
        json={
            "attributes": [
                {"attr_key": "material", "attr_value": "铝合金"},
                {"attr_key": "thickness", "attr_value": "3mm"},
            ],
        },
    )
    assert r2.status_code == 200

    detail = (await client.get(f"/api/v1/operator/products/{pid}", headers=headers)).json()["data"]
    sku = next(s for s in detail["skus"] if s["id"] == sku_id)
    keys = {a["attr_key"] for a in sku["attributes"]}
    assert keys == {"material", "thickness"}


@pytest.mark.asyncio
async def test_attr_key_not_in_template_rejected(client: AsyncClient, db_session):
    """传模板外的 attr_key 触发 40213。"""
    await _seed_template_hierarchy(db_session)
    headers = await _login_operator(client)
    pid, _ = await _create_product_in_test_category(client, headers, db_session, "ATTR-INV-001")

    r = await client.put(
        f"/api/v1/operator/products/{pid}",
        headers=headers,
        json={"attributes": [
            {"attr_key": "不存在的属性", "attr_value": "xxx"},
        ]},
    )
    assert r.status_code == 400
    assert r.json()["code"] == 40213


@pytest.mark.asyncio
async def test_attr_scope_mismatch_sku_attr_on_spu(client: AsyncClient, db_session):
    """SKU 级属性(scope=SKU)放到商品级 → 40215。"""
    await _seed_template_hierarchy(db_session)
    headers = await _login_operator(client)
    pid, _ = await _create_product_in_test_category(client, headers, db_session, "ATTR-MIS-001")

    # thickness 是 SKU 级属性,不能放商品级
    r = await client.put(
        f"/api/v1/operator/products/{pid}",
        headers=headers,
        json={"attributes": [
            {"attr_key": "thickness", "attr_value": "2mm"},
        ]},
    )
    assert r.status_code == 400
    assert r.json()["code"] == 40215


@pytest.mark.asyncio
async def test_attr_scope_mismatch_spu_attr_on_sku(client: AsyncClient, db_session):
    """SPU 级属性(scope=SPU)放到 SKU 级 → 40215。"""
    await _seed_template_hierarchy(db_session)
    headers = await _login_operator(client)
    pid, _ = await _create_product_in_test_category(client, headers, db_session, "ATTR-MIS-002")

    r = await client.post(
        f"/api/v1/operator/products/{pid}/skus",
        headers=headers,
        json={
            "unit": "PCS", "moq": 10,
            "attributes": [
                {"attr_key": "brand", "attr_value": "OEM"},
            ],
        },
    )
    assert r.status_code == 400
    assert r.json()["code"] == 40215


@pytest.mark.asyncio
async def test_attr_spu_update_does_not_delete_sku_attrs(client: AsyncClient, db_session):
    """商品属性整体替换只影响 SPU 级,SKU 级属性不受影响。"""
    await _seed_template_hierarchy(db_session)
    headers = await _login_operator(client)
    pid, _ = await _create_product_in_test_category(client, headers, db_session, "ATTR-ISOL-001")

    # 先创建 SPU 级属性
    await client.put(
        f"/api/v1/operator/products/{pid}",
        headers=headers,
        json={"attributes": [{"attr_key": "cert", "attr_value": "CE"}]},
    )

    # 创建 SKU 带属性
    r = await client.post(
        f"/api/v1/operator/products/{pid}/skus",
        headers=headers,
        json={
            "unit": "PCS", "moq": 100,
            "attributes": [{"attr_key": "thickness", "attr_value": "5mm"}],
        },
    )
    sku_id = r.json()["data"]["id"]

    # 替换 SPU 属性
    await client.put(
        f"/api/v1/operator/products/{pid}",
        headers=headers,
        json={"attributes": [{"attr_key": "brand", "attr_value": "ABC"}]},
    )

    # SKU 属性应保留
    detail = (await client.get(f"/api/v1/operator/products/{pid}", headers=headers)).json()["data"]
    assert len(detail["attributes"]) == 1
    assert detail["attributes"][0]["attr_key"] == "brand"
    sku = next(s for s in detail["skus"] if s["id"] == sku_id)
    assert len(sku["attributes"]) == 1
    assert sku["attributes"][0]["attr_key"] == "thickness"


@pytest.mark.asyncio
async def test_attr_cascade_delete_with_sku(client: AsyncClient, db_session):
    """删除 SKU 时其 SKU 级属性级联删除,SPU 级属性保留。"""
    await _seed_template_hierarchy(db_session)
    headers = await _login_operator(client)
    pid, _ = await _create_product_in_test_category(client, headers, db_session, "ATTR-CASC-001")

    # SPU 级属性
    await client.put(
        f"/api/v1/operator/products/{pid}",
        headers=headers,
        json={"attributes": [{"attr_key": "cert", "attr_value": "CE"}]},
    )

    # 创建 SKU 带属性
    r = await client.post(
        f"/api/v1/operator/products/{pid}/skus",
        headers=headers,
        json={
            "unit": "PCS", "moq": 100,
            "attributes": [{"attr_key": "thickness", "attr_value": "3mm"}],
        },
    )
    sku_id = r.json()["data"]["id"]

    # 删除 SKU
    await client.delete(f"/api/v1/operator/products/{pid}/skus/{sku_id}", headers=headers)

    # SKU 级属性应已级联删除,SPU 级属性保留
    detail = (await client.get(f"/api/v1/operator/products/{pid}", headers=headers)).json()["data"]
    assert len(detail["attributes"]) == 1
    assert detail["attributes"][0]["attr_key"] == "cert"


@pytest.mark.asyncio
async def test_attr_template_returns_scope(client: AsyncClient, db_session):
    """get_attr_templates 返回含 scope 字段。"""
    await _seed_template_hierarchy(db_session)
    headers = await _login_operator(client)

    r = await client.get(
        "/api/v1/operator/products/attr-templates/T1",
        headers=headers,
    )
    data = r.json()["data"]
    assert len(data) == 2
    for t in data:
        assert "scope" in t


# ── 品类子树筛选 ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_by_l1_returns_subtree(client: AsyncClient, db_session):
    """按 L1 品类筛选,返回该 L1 下所有层级的商品。"""
    headers = await _login_operator(client)

    # 取 L3 叶子品类(格式 XX.YYY.ZZZ),从中推导 L1 code
    l3_code = await _get_first_category_code(client, level=3)
    l1_code = l3_code.split(".")[0]

    pid = await _create_test_product(client, headers, l3_code, spu_code="TREE-L3-001")

    # 按 L1 筛选,应包含挂在 L3 的商品
    r = await client.get(
        f"/api/v1/operator/products?category_code={l1_code}",
        headers=headers,
    )
    assert r.status_code == 200
    body = r.json()["data"]
    ids = [p["id"] for p in body["items"]]
    assert pid in ids
    assert body["total"] >= 1


@pytest.mark.asyncio
async def test_list_by_l2_returns_subtree(client: AsyncClient, db_session):
    """按 L2 品类筛选,返回该 L2 下的商品。"""
    headers = await _login_operator(client)

    l3_code = await _get_first_category_code(client, level=3)
    parts = l3_code.split(".")
    l2_code = f"{parts[0]}.{parts[1]}"

    pid = await _create_test_product(client, headers, l3_code, spu_code="TREE-L2-001")

    r = await client.get(
        f"/api/v1/operator/products?category_code={l2_code}",
        headers=headers,
    )
    assert r.status_code == 200
    body = r.json()["data"]
    ids = [p["id"] for p in body["items"]]
    assert pid in ids


@pytest.mark.asyncio
async def test_list_by_l3_exact_match(client: AsyncClient, db_session):
    """按 L3 品类筛选,精确匹配(含自身)。"""
    headers = await _login_operator(client)
    l3_code = await _get_first_category_code(client, level=3)

    pid = await _create_test_product(client, headers, l3_code, spu_code="TREE-L3-EXACT")

    r = await client.get(
        f"/api/v1/operator/products?category_code={l3_code}",
        headers=headers,
    )
    assert r.status_code == 200
    body = r.json()["data"]
    ids = [p["id"] for p in body["items"]]
    assert pid in ids


@pytest.mark.asyncio
async def test_list_by_nonexistent_category_returns_empty(client: AsyncClient, db_session):
    """不存在的品类 code 筛选,返回空。"""
    headers = await _login_operator(client)
    r = await client.get(
        "/api/v1/operator/products?category_code=99.999.999",
        headers=headers,
    )
    assert r.status_code == 200
    body = r.json()["data"]
    assert body["items"] == []
    assert body["total"] == 0


@pytest.mark.asyncio
async def test_public_list_subtree_filter(client: AsyncClient, db_session):
    """公开列表同样支持子树筛选。"""
    headers = await _login_operator(client)
    l3_code = await _get_first_category_code(client, level=3)
    l1_code = l3_code.split(".")[0]

    pid = await _create_test_product(client, headers, l3_code, spu_code="PUB-TREE-001")
    # 上架
    await _create_test_sku(client, headers, pid, sku_code="PUB-TREE-SKU")
    await _upload_test_image(client, headers, pid)
    await client.patch(
        f"/api/v1/operator/products/{pid}/status",
        headers=headers,
        json={"status": "ACTIVE"},
    )

    buyer_headers = await _login_buyer(client)
    r = await client.get(
        f"/api/v1/products?category_code={l1_code}",
        headers=buyer_headers,
    )
    assert r.status_code == 200
    body = r.json()["data"]
    ids = [p["id"] for p in body["items"]]
    assert pid in ids


# ── 叶子校验 ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_product_with_l1_rejected(client: AsyncClient, db_session):
    """用 L1 品类建商品,被拒(40216)。"""
    headers = await _login_operator(client)
    l1_code = await _get_first_category_code(client, level=1)

    r = await client.post(
        "/api/v1/operator/products",
        headers=headers,
        json={
            "category_code": l1_code,
            "name": "Reject-L1",
            "source_lang": "zh",
        },
    )
    assert r.status_code == 400
    assert r.json()["code"] == 40216
    assert r.json()["message_key"] == "error.product.category_not_leaf"


@pytest.mark.asyncio
async def test_create_product_with_l2_rejected(client: AsyncClient, db_session):
    """用 L2 品类建商品,被拒(40216)。"""
    headers = await _login_operator(client)
    l3_code = await _get_first_category_code(client, level=3)
    parts = l3_code.split(".")
    l2_code = f"{parts[0]}.{parts[1]}"

    r = await client.post(
        "/api/v1/operator/products",
        headers=headers,
        json={
            "category_code": l2_code,
            "name": "Reject-L2",
            "source_lang": "zh",
        },
    )
    assert r.status_code == 400
    assert r.json()["code"] == 40216


@pytest.mark.asyncio
async def test_create_product_with_l3_passes(client: AsyncClient, db_session):
    """用 L3 品类建商品,通过。"""
    headers = await _login_operator(client)
    l3_code = await _get_first_category_code(client, level=3)

    r = await client.post(
        "/api/v1/operator/products",
        headers=headers,
        json={
            "category_code": l3_code,
            "spu_code": "LEAF-OK-001",
            "name": "Leaf OK",
            "source_lang": "zh",
        },
    )
    assert r.status_code == 200
    assert r.json()["code"] == 0


# ── 聚合保存 SKU 归属校验 ────────────────────────────────

def _sku_payload(**overrides) -> dict:
    """构造聚合保存 SKU 子项的最小有效载荷。"""
    base = {
        "unit": "PCS",
        "moq": 100,
        "price_min": 1.00,
        "price_max": 3.00,
        "currency": "TZS",
        "source_lang": "zh",
    }
    base.update(overrides)
    return base


@pytest.mark.asyncio
async def test_aggregate_save_reject_nonexistent_sku_id(client: AsyncClient, db_session):
    """带不存在的 SKU id → 404,无新 SKU 落库,整笔回滚。"""
    headers = await _login_operator(client)
    cat = await _get_first_category_code(client)
    pid = await _create_test_product(client, headers, cat, spu_code="AGG-OWN-001")

    # 先建一条真实 SKU
    real_sku_id = await _create_test_sku(client, headers, pid, sku_code="AGG-SKU-R1")

    # 聚合保存: 保留真实 SKU + 插入一条带不存在 id 的 SKU
    fake_id = 999999
    r = await client.put(
        f"/api/v1/operator/products/{pid}/aggregate",
        headers=headers,
        json={
            "skus": [
                _sku_payload(id=real_sku_id),
                _sku_payload(id=fake_id),
            ],
        },
    )
    assert r.status_code == 404

    # 断言无新 SKU 落库（仍然只有最初的 1 条）
    r2 = await client.get(f"/api/v1/operator/products/{pid}/skus", headers=headers)
    assert r2.status_code == 200
    assert len(r2.json()["data"]) == 1


@pytest.mark.asyncio
async def test_aggregate_save_reject_foreign_sku_id(client: AsyncClient, db_session):
    """带另一商品 SKU id → 404,另一商品 SKU 未受影响。"""
    headers = await _login_operator(client)
    cat = await _get_first_category_code(client)

    pid_a = await _create_test_product(client, headers, cat, spu_code="AGG-OWN-A")
    pid_b = await _create_test_product(client, headers, cat, spu_code="AGG-OWN-B")

    sku_a = await _create_test_sku(client, headers, pid_a, sku_code="AGG-SKU-A1")
    sku_b = await _create_test_sku(client, headers, pid_b, sku_code="AGG-SKU-B1")

    # 对商品 A 聚合保存，传入商品 B 的 SKU id
    r = await client.put(
        f"/api/v1/operator/products/{pid_a}/aggregate",
        headers=headers,
        json={
            "skus": [
                _sku_payload(id=sku_a),
                _sku_payload(id=sku_b),  # 外来 id
            ],
        },
    )
    assert r.status_code == 404

    # 商品 B 的 SKU 未被修改/删除
    r2 = await client.get(f"/api/v1/operator/products/{pid_b}/skus", headers=headers)
    assert r2.status_code == 200
    skus_b = r2.json()["data"]
    assert len(skus_b) == 1
    assert skus_b[0]["id"] == sku_b


@pytest.mark.asyncio
async def test_aggregate_save_new_sku_without_id(client: AsyncClient, db_session):
    """不带 id → 仍新建;带本商品已有 id → 仍更新。回归测试。"""
    headers = await _login_operator(client)
    cat = await _get_first_category_code(client)
    pid = await _create_test_product(client, headers, cat, spu_code="AGG-OWN-REG")
    existing_sku = await _create_test_sku(client, headers, pid, sku_code="AGG-SKU-E1")

    # 聚合保存: 更新已有 + 新建一条
    r = await client.put(
        f"/api/v1/operator/products/{pid}/aggregate",
        headers=headers,
        json={
            "skus": [
                _sku_payload(id=existing_sku, moq=200),  # 更新
                _sku_payload(moq=300),                    # 新建（无 id）
            ],
        },
    )
    assert r.status_code == 200
    assert r.json()["code"] == 0

    # 确认有 2 条 SKU
    r2 = await client.get(f"/api/v1/operator/products/{pid}/skus", headers=headers)
    assert r2.status_code == 200
    assert len(r2.json()["data"]) == 2


# ── 图片操作：状态校验 + 归属校验 ──────────────────────────


async def _make_active_product_with_image(client: AsyncClient, headers: dict, cat: str, spu_code: str):
    """创建 DRAFT 商品 + SKU + 图片，然后上架，返回 (product_id, image_id)。"""
    pid = await _create_test_product(client, headers, cat, spu_code)
    await _create_test_sku(client, headers, pid, sku_code=f"{spu_code}-SKU")
    img_id = await _upload_test_image(client, headers, pid)
    # 上架
    r = await client.patch(
        f"/api/v1/operator/products/{pid}/status",
        headers=headers,
        json={"status": "ACTIVE"},
    )
    assert r.status_code == 200, r.text
    return pid, img_id


@pytest.mark.asyncio
async def test_upload_image_blocked_when_active(client: AsyncClient):
    """ACTIVE 商品不能上传图片。"""
    headers = await _login_operator(client)
    cat = await _get_first_category_code(client)
    pid, _ = await _make_active_product_with_image(client, headers, cat, "IMG-ACT-UP")

    from PIL import Image as PILImage
    buf = io.BytesIO()
    PILImage.new("RGB", (100, 100), color=(0, 255, 0)).save(buf, format="PNG")
    buf.seek(0)
    r = await client.post(
        f"/api/v1/operator/products/{pid}/images",
        headers=headers,
        files={"file": ("new.png", buf, "image/png")},
    )
    assert r.status_code == 400
    assert r.json()["code"] == 40207  # ProductNotEditableError


@pytest.mark.asyncio
async def test_delete_image_blocked_when_active(client: AsyncClient):
    """ACTIVE 商品不能删图片。"""
    headers = await _login_operator(client)
    cat = await _get_first_category_code(client)
    pid, img_id = await _make_active_product_with_image(client, headers, cat, "IMG-ACT-DEL")

    r = await client.delete(
        f"/api/v1/operator/products/{pid}/images/{img_id}",
        headers=headers,
    )
    assert r.status_code == 400
    assert r.json()["code"] == 40207


@pytest.mark.asyncio
async def test_set_main_image_blocked_when_active(client: AsyncClient):
    """ACTIVE 商品不能设主图。"""
    headers = await _login_operator(client)
    cat = await _get_first_category_code(client)
    pid, img_id = await _make_active_product_with_image(client, headers, cat, "IMG-ACT-MAIN")

    r = await client.patch(
        f"/api/v1/operator/products/{pid}/images/{img_id}/set-main",
        headers=headers,
    )
    assert r.status_code == 400
    assert r.json()["code"] == 40207


@pytest.mark.asyncio
async def test_sort_images_blocked_when_active(client: AsyncClient):
    """ACTIVE 商品不能排序图片。"""
    headers = await _login_operator(client)
    cat = await _get_first_category_code(client)
    pid, img_id = await _make_active_product_with_image(client, headers, cat, "IMG-ACT-SORT")

    r = await client.patch(
        f"/api/v1/operator/products/{pid}/images/sort",
        headers=headers,
        json=[img_id],
    )
    assert r.status_code == 400
    assert r.json()["code"] == 40207


@pytest.mark.asyncio
async def test_delete_image_wrong_product_id(client: AsyncClient):
    """删图片传错 product_id 应返回 404。"""
    headers = await _login_operator(client)
    cat = await _get_first_category_code(client)

    # 创建两个不同商品
    pid_a = await _create_test_product(client, headers, cat, "IMG-OWN-A")
    pid_b = await _create_test_product(client, headers, cat, "IMG-OWN-B")
    img_a = await _upload_test_image(client, headers, pid_a)

    # 用 pid_b 去删 pid_a 的图片 → 404
    r = await client.delete(
        f"/api/v1/operator/products/{pid_b}/images/{img_a}",
        headers=headers,
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_force_ignored_when_debug_api_disabled(client: AsyncClient):
    """ENABLE_DEBUG_API=False 时 force=true 无效，上架校验仍执行。"""
    from app.core.config import settings
    headers = await _login_operator(client)
    cat = await _get_first_category_code(client)

    # 创建无 SKU/图片的空商品
    pid = await _create_test_product(client, headers, cat, "FORCE-GATE-001")

    original_val = settings.ENABLE_DEBUG_API
    try:
        # 模拟生产环境
        object.__setattr__(settings, "ENABLE_DEBUG_API", False)
        r = await client.patch(
            f"/api/v1/operator/products/{pid}/status?force=true",
            headers=headers,
            json={"status": "ACTIVE"},
        )
        # 缺少 SKU/图片，校验应失败
        assert r.status_code == 400
    finally:
        object.__setattr__(settings, "ENABLE_DEBUG_API", original_val)


@pytest.mark.asyncio
async def test_sku_status_toggle_on_active_product(client: AsyncClient):
    """ACTIVE 商品下可以切换 SKU 状态（运营操作，不受可编辑限制）。"""
    headers = await _login_operator(client)
    cat = await _get_first_category_code(client)
    pid, _ = await _make_active_product_with_image(client, headers, cat, "SKU-TOGGLE-ACT")

    # 拿到唯一的 SKU
    skus_r = await client.get(f"/api/v1/operator/products/{pid}/skus", headers=headers)
    sku_id = skus_r.json()["data"][0]["id"]

    # ACTIVE 商品下停售 SKU → 应成功，不报 ProductNotEditableError
    r = await client.patch(
        f"/api/v1/operator/products/{pid}/skus/{sku_id}/status",
        headers=headers,
        json={"status": "INACTIVE"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["data"]["status"] == "INACTIVE"


@pytest.mark.asyncio
async def test_deactivate_last_sku_auto_delists_product(client: AsyncClient):
    """停售 ACTIVE 商品下最后一个在售 SKU → 商品自动下架。"""
    headers = await _login_operator(client)
    cat = await _get_first_category_code(client)
    pid, _ = await _make_active_product_with_image(client, headers, cat, "SKU-LAST-DELIST")

    skus_r = await client.get(f"/api/v1/operator/products/{pid}/skus", headers=headers)
    sku_id = skus_r.json()["data"][0]["id"]

    r = await client.patch(
        f"/api/v1/operator/products/{pid}/skus/{sku_id}/status",
        headers=headers,
        json={"status": "INACTIVE"},
    )
    assert r.status_code == 200
    assert r.json()["data"]["product_auto_delisted"] is True

    # 确认商品已自动变为 INACTIVE
    detail = await client.get(f"/api/v1/operator/products/{pid}", headers=headers)
    assert detail.json()["data"]["status"] == "INACTIVE"
