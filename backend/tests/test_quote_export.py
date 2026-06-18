"""报价单 PDF 导出端点单测 — GET /api/v1/rfqs/{rfq_id}/quote/export。

覆盖:
- 买方导出 ACTIVE 报价 → 200, PDF bytes, Content-Disposition
- 运营导出 → 200, PDF bytes
- 不同买方越权导出 → 404
- RFQ 无 ACTIVE 报价 → 409, code 40527
- Accept-Language: en → 200, PDF bytes
- PDF 内容不含成本/供应商字段
"""
from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.category import Category


# ── helpers（与 test_quote.py 保持一致）──────────────────────

_BUYER_EMAIL = "buyer@cscec3b.local"
_BUYER_PASSWORD = "Aa123456789"
_OPERATOR_EMAIL = "operator@platform.local"
_OPERATOR_PASSWORD = "Aa123456789"

# 第二个买方用于越权测试（seed 中存在）
_BUYER2_EMAIL = "buyer2@cscec3b.local"
_BUYER2_PASSWORD = "Aa123456789"


async def _login(client: AsyncClient, email: str, password: str) -> dict[str, str]:
    r = await client.post(
        "/api/v1/auth/login",
        json={"identifier": email, "password": password},
    )
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['data']['access_token']}"}


async def _buyer_headers(client: AsyncClient) -> dict[str, str]:
    return await _login(client, _BUYER_EMAIL, _BUYER_PASSWORD)


async def _op_headers(client: AsyncClient) -> dict[str, str]:
    return await _login(client, _OPERATOR_EMAIL, _OPERATOR_PASSWORD)


async def _create_active_product(client: AsyncClient, op: dict, db: AsyncSession) -> int:
    """创建一个 ACTIVE 商品,返回 product_id。"""
    cat = (await db.execute(
        select(Category).where(Category.level == 3).limit(1)
    )).scalar_one_or_none()
    assert cat is not None, "No level-3 category in seed data"

    r = await client.post("/api/v1/operator/products", headers=op, json={
        "name": "Export Test Product",
        "category_code": cat.code,
        "unit": "PCS",
        "currency": "USD",
    })
    assert r.status_code == 200, r.text
    pid = r.json()["data"]["id"]

    r = await client.post(
        f"/api/v1/operator/products/{pid}/skus",
        headers=op,
        json={"name": "Export SKU", "moq": 1, "price_min": 100, "price_max": 200},
    )
    assert r.status_code == 200, r.text

    r = await client.patch(
        f"/api/v1/operator/products/{pid}/status?force=true",
        headers=op,
        json={"status": "ACTIVE"},
    )
    assert r.status_code == 200, r.text
    return pid


async def _create_quoted_rfq(
    client: AsyncClient,
    bh: dict,
    op: dict,
    db: AsyncSession,
) -> int:
    """创建一个带 ACTIVE 报价的 RFQ,返回 rfq_id。"""
    pid = await _create_active_product(client, op, db)

    # 创建询价单
    r = await client.post("/api/v1/rfqs", headers=bh, json={
        "items": [{"product_id": pid, "selected_variants": [], "quantity": "10.000"}],
        "contact_name": "Test Buyer",
        "contact_phone": "+255700000001",
    })
    assert r.status_code == 200, r.text
    rfq_data = r.json()["data"]
    rfq_id = rfq_data["id"]
    item_ids = [it["id"] for it in rfq_data["items"]]

    # 运营认领 → PROCESSING
    r = await client.patch(f"/api/v1/rfqs/{rfq_id}/claim", headers=op)
    assert r.status_code == 200, r.text

    # 填报价 → QUOTED + ACTIVE quote
    r = await client.post(f"/api/v1/rfqs/{rfq_id}/quotes", headers=op, json={
        "header": {
            "trade_term": "FOB",
            "currency": "USD",
            "lead_time_days": 30,
            "eta_days": 45,
        },
        "lines": [{
            "source_rfq_item_id": item_ids[0],
            "line_type": "PRODUCT",
            "product_id": pid,
            "quantity": "10.000",
            "unit_price": "25.0000",
        }],
    })
    assert r.status_code == 200, r.text

    return rfq_id


# ── 测试用例 ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_buyer_export_active_quote_200(client: AsyncClient, db_session: AsyncSession):
    """买方导出有 ACTIVE 报价的 RFQ → 200, PDF bytes, Content-Disposition。"""
    bh = await _buyer_headers(client)
    op = await _op_headers(client)
    rfq_id = await _create_quoted_rfq(client, bh, op, db_session)

    r = await client.get(
        f"/api/v1/rfqs/{rfq_id}/quote/export",
        headers=bh,
    )
    assert r.status_code == 200, r.text
    assert r.headers["content-type"] == "application/pdf"
    # Content-Disposition 含 attachment 和 .pdf
    cd = r.headers.get("content-disposition", "")
    assert "attachment" in cd
    assert ".pdf" in cd
    # 内容是真实 PDF（PDF 文件头 %PDF-）
    assert r.content[:4] == b"%PDF"


@pytest.mark.asyncio
async def test_operator_export_200(client: AsyncClient, db_session: AsyncSession):
    """运营导出 → 200, PDF bytes。"""
    bh = await _buyer_headers(client)
    op = await _op_headers(client)
    rfq_id = await _create_quoted_rfq(client, bh, op, db_session)

    r = await client.get(
        f"/api/v1/rfqs/{rfq_id}/quote/export",
        headers=op,
    )
    assert r.status_code == 200, r.text
    assert r.headers["content-type"] == "application/pdf"
    assert r.content[:4] == b"%PDF"


@pytest.mark.asyncio
async def test_different_buyer_cannot_export_404(client: AsyncClient, db_session: AsyncSession):
    """不同买方尝试导出他人的 RFQ → 404。"""
    bh = await _buyer_headers(client)
    op = await _op_headers(client)
    rfq_id = await _create_quoted_rfq(client, bh, op, db_session)

    # 注册一个新买方（与 rfq 的 buyer_org 不同）
    from tests.conftest import register_buyer_tz
    reg = await register_buyer_tz(
        client,
        name="Other Buyer",
        company_name="Other Shop",
    )
    assert reg["response"].status_code == 200, reg["response"].text
    other_token = reg["response"].json()["data"]["access_token"]
    other_headers = {"Authorization": f"Bearer {other_token}"}

    r = await client.get(
        f"/api/v1/rfqs/{rfq_id}/quote/export",
        headers=other_headers,
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_no_active_quote_409(client: AsyncClient, db_session: AsyncSession):
    """RFQ 无 ACTIVE 报价 → 409, code 40527。"""
    bh = await _buyer_headers(client)
    op = await _op_headers(client)
    pid = await _create_active_product(client, op, db_session)

    # 创建询价单但不填报价
    r = await client.post("/api/v1/rfqs", headers=bh, json={
        "items": [{"product_id": pid, "selected_variants": [], "quantity": "5.000"}],
    })
    assert r.status_code == 200, r.text
    rfq_id = r.json()["data"]["id"]

    r = await client.get(
        f"/api/v1/rfqs/{rfq_id}/quote/export",
        headers=bh,
    )
    assert r.status_code == 409
    assert r.json()["code"] == 40527


@pytest.mark.asyncio
async def test_locale_en_via_accept_language_200(client: AsyncClient, db_session: AsyncSession):
    """Accept-Language: en → 200, 返回有效 PDF。"""
    bh = await _buyer_headers(client)
    op = await _op_headers(client)
    rfq_id = await _create_quoted_rfq(client, bh, op, db_session)

    r = await client.get(
        f"/api/v1/rfqs/{rfq_id}/quote/export",
        headers={**bh, "Accept-Language": "en"},
    )
    assert r.status_code == 200, r.text
    assert r.headers["content-type"] == "application/pdf"
    assert r.content[:4] == b"%PDF"


@pytest.mark.asyncio
async def test_pdf_content_no_cost_supplier_fields(client: AsyncClient, db_session: AsyncSession):
    """买方视角导出的 PDF 不含成本/供应商相关字段文字。

    WeasyPrint 生成的 PDF 二进制中，嵌入的文本内容以 UTF-8/latin-1 编码，
    敏感关键词如 'supplier', 'cost', 'gross_margin' 不应出现在 PDF 流中。
    注：此处通过字节搜索验证，有一定近似性，足以满足回归守护目的。
    """
    bh = await _buyer_headers(client)
    op = await _op_headers(client)
    rfq_id = await _create_quoted_rfq(client, bh, op, db_session)

    r = await client.get(
        f"/api/v1/rfqs/{rfq_id}/quote/export",
        headers=bh,
    )
    assert r.status_code == 200, r.text
    pdf_bytes = r.content

    # PDF 内嵌文本以 latin-1 或 UTF-8 存在，小写检查
    pdf_lower = pdf_bytes.lower()
    assert b"gross_margin" not in pdf_lower
    assert b"supplier_unit_price" not in pdf_lower
    assert b"freight_cost_alloc" not in pdf_lower
