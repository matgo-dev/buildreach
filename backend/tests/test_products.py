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
        "unit": "pcs",
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
    assert r.json()["code"] == 50003


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
        json={"sku_code": "DUP-SKU-CODE", "unit": "pcs", "moq": 1, "source_lang": "zh"},
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
        json={"sku_code": "TIER-MOQ-S001", "unit": "pcs", "moq": 500, "price_tiers": tiers, "source_lang": "zh"},
    )
    assert r.status_code == 400
    assert r.json()["code"] == 50012


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
        json={"sku_code": "TIER-CONT-S001", "unit": "pcs", "moq": 500, "price_tiers": tiers, "source_lang": "zh"},
    )
    assert r.status_code == 400
    assert r.json()["code"] == 50012


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
        json={"sku_code": "TIER-DEC-S001", "unit": "pcs", "moq": 500, "price_tiers": tiers, "source_lang": "zh"},
    )
    assert r.status_code == 400
    assert r.json()["code"] == 50012


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
    assert r.json()["code"] == 50004
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
    assert r.json()["code"] == 50004
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
        json={"sku_code": "PUB-NP-SKU", "unit": "pcs", "moq": 100, "is_default": True, "source_lang": "zh"},
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
    assert r2.json()["code"] == 50007


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
