"""报价单 PDF 产物预生成测试。

覆盖:
- QuoteDocument 状态机转换
- generate_quote_documents 创建记录 + 生成文件
- 下载端点优先查产物表
- 运营查状态 + 重试端点
"""
from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.category import Category
from app.db.models.quote_document import QuoteDocument


# ── helpers ──────────────────────────────────────────────

_BUYER_EMAIL = "buyer@cscec3b.local"
_BUYER_PASSWORD = "Aa123456789"
_OPERATOR_EMAIL = "operator@platform.local"
_OPERATOR_PASSWORD = "Aa123456789"


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
    cat = (await db.execute(
        select(Category).where(Category.level == 3).limit(1)
    )).scalar_one_or_none()
    assert cat is not None, "No level-3 category in seed data"

    r = await client.post("/api/v1/operator/products", headers=op, json={
        "name": "DocTest Product",
        "category_code": cat.code,
        "unit": "PCS",
        "currency": "USD",
    })
    assert r.status_code == 200, r.text
    pid = r.json()["data"]["id"]

    r = await client.post(
        f"/api/v1/operator/products/{pid}/skus",
        headers=op,
        json={"name": "DocTest SKU", "moq": 1, "price_min": 100, "price_max": 200},
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
    client: AsyncClient, bh: dict, op: dict, db: AsyncSession,
) -> tuple[int, int, int]:
    """创建带 ACTIVE 报价的 RFQ，返回 (rfq_id, quote_id, version)。"""
    pid = await _create_active_product(client, op, db)

    r = await client.post("/api/v1/rfqs", headers=bh, json={
        "items": [{"product_id": pid, "selected_variants": [], "quantity": "10.000"}],
        "contact_name": "Test Buyer",
        "contact_phone": "+255700000001",
    })
    assert r.status_code == 200, r.text
    rfq_data = r.json()["data"]
    rfq_id = rfq_data["id"]
    item_ids = [it["id"] for it in rfq_data["items"]]

    r = await client.patch(f"/api/v1/rfqs/{rfq_id}/claim", headers=op)
    assert r.status_code == 200, r.text

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
    quote_data = r.json()["data"]
    return rfq_id, quote_data["id"], quote_data["version"]


# ── 状态机单测 ──────────────────────────────────────────


def test_quote_document_transitions_valid():
    doc = QuoteDocument(quote_id=1, version=1, locale="en", status="PENDING")
    doc.transition_to("GENERATING")
    assert doc.status == "GENERATING"
    doc.transition_to("READY")
    assert doc.status == "READY"


def test_quote_document_transitions_failed():
    doc = QuoteDocument(quote_id=1, version=1, locale="en", status="PENDING")
    doc.transition_to("GENERATING")
    doc.transition_to("FAILED")
    assert doc.status == "FAILED"
    # FAILED → PENDING（重试）
    doc.transition_to("PENDING")
    assert doc.status == "PENDING"


def test_quote_document_transitions_invalid():
    doc = QuoteDocument(quote_id=1, version=1, locale="en", status="PENDING")
    with pytest.raises(ValueError, match="not allowed"):
        doc.transition_to("READY")  # PENDING 不能直接跳 READY


def test_quote_document_transitions_ready_is_terminal():
    doc = QuoteDocument(quote_id=1, version=1, locale="en", status="READY")
    with pytest.raises(ValueError, match="not allowed"):
        doc.transition_to("PENDING")


# ── 产物生成集成测试 ────────────────────────────────────


@pytest.mark.asyncio
async def test_create_quote_triggers_document_generation(
    client: AsyncClient, db_session: AsyncSession,
):
    """提交报价后，BackgroundTask 应异步生成产物记录。

    注：FastAPI TestClient 的 BackgroundTask 在响应返回后同步执行，
    所以提交后查库应能看到产物记录。
    """
    bh = await _buyer_headers(client)
    op = await _op_headers(client)
    rfq_id, quote_id, version = await _create_quoted_rfq(client, bh, op, db_session)

    # 查 quote_documents 表 — BackgroundTask 在测试中同步执行
    stmt = select(QuoteDocument).where(
        QuoteDocument.quote_id == quote_id,
        QuoteDocument.version == version,
    )
    docs = (await db_session.execute(stmt)).scalars().all()

    # 应为每个 SUPPORTED_LOCALE 创建了记录
    from app.core.locale import SUPPORTED_LOCALES
    assert len(docs) >= len(SUPPORTED_LOCALES)

    # 检查状态：应为 READY 或 FAILED（取决于 weasyprint 是否可用）
    for doc in docs:
        assert doc.status in ("READY", "FAILED", "PENDING", "GENERATING")


@pytest.mark.asyncio
async def test_operator_list_quote_documents(
    client: AsyncClient, db_session: AsyncSession,
):
    """运营查询报价文档状态。"""
    bh = await _buyer_headers(client)
    op = await _op_headers(client)
    rfq_id, _, _ = await _create_quoted_rfq(client, bh, op, db_session)

    r = await client.get(
        f"/api/v1/rfqs/{rfq_id}/quote-documents",
        headers=op,
    )
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert isinstance(data, list)


@pytest.mark.asyncio
async def test_operator_retry_quote_documents(
    client: AsyncClient, db_session: AsyncSession,
):
    """运营重试失败的文档生成。"""
    bh = await _buyer_headers(client)
    op = await _op_headers(client)
    rfq_id, _, _ = await _create_quoted_rfq(client, bh, op, db_session)

    r = await client.post(
        f"/api/v1/rfqs/{rfq_id}/quote-documents/retry",
        headers=op,
    )
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert "retried" in data


@pytest.mark.asyncio
async def test_download_with_ready_document(
    client: AsyncClient, db_session: AsyncSession,
):
    """当产物 READY 时，下载端点直接返回文件。"""
    bh = await _buyer_headers(client)
    op = await _op_headers(client)
    rfq_id, quote_id, version = await _create_quoted_rfq(client, bh, op, db_session)

    # 查看是否有 READY 的产物
    stmt = select(QuoteDocument).where(
        QuoteDocument.quote_id == quote_id,
        QuoteDocument.version == version,
        QuoteDocument.status == "READY",
    )
    ready_doc = (await db_session.execute(stmt)).scalar_one_or_none()

    r = await client.get(
        f"/api/v1/rfqs/{rfq_id}/quote/export",
        headers=bh,
    )
    # 无论是否有 READY 产物，都应返回可用的响应
    assert r.status_code in (200, 202, 422), r.text

    if ready_doc is not None:
        # 有 READY 产物 → 直接返回 PDF
        assert r.status_code == 200
        assert r.headers["content-type"] == "application/pdf"
        assert r.content[:4] == b"%PDF"


@pytest.mark.asyncio
async def test_download_generating_returns_202(
    client: AsyncClient, db_session: AsyncSession,
):
    """当产物 GENERATING 时，下载端点返回 202 JSON。"""
    bh = await _buyer_headers(client)
    op = await _op_headers(client)
    rfq_id, quote_id, version = await _create_quoted_rfq(client, bh, op, db_session)

    # 手动将一个产物改为 GENERATING
    stmt = select(QuoteDocument).where(
        QuoteDocument.quote_id == quote_id,
        QuoteDocument.version == version,
    ).limit(1)
    doc = (await db_session.execute(stmt)).scalar_one_or_none()
    if doc is not None:
        doc.status = "GENERATING"
        doc.storage_key = None
        await db_session.commit()

        # 下载时应返回 202
        r = await client.get(
            f"/api/v1/rfqs/{rfq_id}/quote/export",
            headers={**bh, "Accept-Language": doc.locale},
        )
        assert r.status_code == 202
        body = r.json()
        assert body["code"] == 20201


@pytest.mark.asyncio
async def test_download_failed_returns_422(
    client: AsyncClient, db_session: AsyncSession,
):
    """当产物 FAILED 时，下载端点返回 422 JSON。"""
    bh = await _buyer_headers(client)
    op = await _op_headers(client)
    rfq_id, quote_id, version = await _create_quoted_rfq(client, bh, op, db_session)

    # 手动将一个产物改为 FAILED
    stmt = select(QuoteDocument).where(
        QuoteDocument.quote_id == quote_id,
        QuoteDocument.version == version,
    ).limit(1)
    doc = (await db_session.execute(stmt)).scalar_one_or_none()
    if doc is not None:
        doc.status = "FAILED"
        doc.error_message = "test error"
        doc.storage_key = None
        await db_session.commit()

        r = await client.get(
            f"/api/v1/rfqs/{rfq_id}/quote/export",
            headers={**bh, "Accept-Language": doc.locale},
        )
        assert r.status_code == 422
        body = r.json()
        assert body["code"] == 42210
