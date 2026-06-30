"""报价单 PDF 产物预生成测试。

覆盖:
- QuoteDocument 状态机转换
- 产物记录创建（幂等）
- 下载端点对产物状态的响应（READY/GENERATING/FAILED/兜底）
- 运营查状态 + 重试端点
"""
from __future__ import annotations

import io

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
        select(Category).where(Category.is_leaf == True, Category.is_active == True).limit(1)
    )).scalar_one_or_none()
    assert cat is not None, "No leaf category in seed data"

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

    from PIL import Image as PILImage
    buf = io.BytesIO()
    PILImage.new("RGB", (300, 300), color=(200, 100, 50)).save(buf, format="PNG")
    buf.seek(0)
    r = await client.post(
        f"/api/v1/operator/products/{pid}/images",
        headers=op,
        files={"file": ("test.png", buf, "image/png")},
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
    doc.transition_to("PENDING")
    assert doc.status == "PENDING"


def test_quote_document_transitions_invalid():
    doc = QuoteDocument(quote_id=1, version=1, locale="en", status="PENDING")
    with pytest.raises(ValueError, match="not allowed"):
        doc.transition_to("READY")


def test_quote_document_transitions_ready_is_terminal():
    doc = QuoteDocument(quote_id=1, version=1, locale="en", status="READY")
    with pytest.raises(ValueError, match="not allowed"):
        doc.transition_to("PENDING")


# ── 产物记录创建测试 ────────────────────────────────────


@pytest.mark.asyncio
async def test_ensure_document_record_idempotent(
    client: AsyncClient, db_session: AsyncSession,
):
    """_ensure_document_record 幂等：重复调用不创建重复记录。"""
    from app.services.quote_export import _ensure_document_record

    bh = await _buyer_headers(client)
    op = await _op_headers(client)
    rfq_id, quote_id, version = await _create_quoted_rfq(client, bh, op, db_session)

    doc1 = await _ensure_document_record(db_session, quote_id, version, "en")
    await db_session.commit()
    assert doc1.status == "PENDING"

    doc2 = await _ensure_document_record(db_session, quote_id, version, "en")
    assert doc2.id == doc1.id

    doc3 = await _ensure_document_record(db_session, quote_id, version, "zh")
    await db_session.commit()
    assert doc3.id != doc1.id


# ── 下载端点状态响应测试 ──────────────────────────────────


@pytest.mark.asyncio
async def test_download_generating_returns_202(
    client: AsyncClient, db_session: AsyncSession,
):
    """当产物 GENERATING 时，下载端点返回 202 JSON。"""
    bh = await _buyer_headers(client)
    op = await _op_headers(client)
    rfq_id, quote_id, version = await _create_quoted_rfq(client, bh, op, db_session)

    doc = QuoteDocument(
        quote_id=quote_id, version=version, locale="en", status="GENERATING",
    )
    db_session.add(doc)
    await db_session.commit()

    r = await client.get(
        f"/api/v1/rfqs/{rfq_id}/quote/export",
        headers={**bh, "Accept-Language": "en"},
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

    doc = QuoteDocument(
        quote_id=quote_id, version=version, locale="en",
        status="FAILED", error_message="test error",
    )
    db_session.add(doc)
    await db_session.commit()

    r = await client.get(
        f"/api/v1/rfqs/{rfq_id}/quote/export",
        headers={**bh, "Accept-Language": "en"},
    )
    assert r.status_code == 422
    body = r.json()
    assert body["code"] == 42210


@pytest.mark.asyncio
async def test_download_no_record_falls_back(
    client: AsyncClient, db_session: AsyncSession,
):
    """无产物记录时兜底现场生成（过渡期）。需 weasyprint 系统依赖。"""
    try:
        from weasyprint import HTML  # noqa: F401
    except OSError:
        pytest.skip("WeasyPrint system libs not available")

    bh = await _buyer_headers(client)
    op = await _op_headers(client)
    rfq_id, _, _ = await _create_quoted_rfq(client, bh, op, db_session)

    r = await client.get(
        f"/api/v1/rfqs/{rfq_id}/quote/export",
        headers=bh,
    )
    assert r.status_code == 200
    assert "application/pdf" in r.headers.get("content-type", "")


# ── 运营端点测试 ────────────────────────────────────────


@pytest.mark.asyncio
async def test_operator_list_quote_documents(
    client: AsyncClient, db_session: AsyncSession,
):
    """运营查询报价文档状态。"""
    bh = await _buyer_headers(client)
    op = await _op_headers(client)
    rfq_id, quote_id, version = await _create_quoted_rfq(client, bh, op, db_session)

    for locale in ("zh", "en"):
        db_session.add(QuoteDocument(
            quote_id=quote_id, version=version, locale=locale, status="READY",
        ))
    await db_session.commit()

    r = await client.get(
        f"/api/v1/rfqs/{rfq_id}/quote-documents",
        headers=op,
    )
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert isinstance(data, list)
    assert len(data) >= 2


@pytest.mark.asyncio
async def test_operator_retry_resets_failed_status(
    client: AsyncClient, db_session: AsyncSession,
):
    """运营重试：FAILED 记录应重置为 PENDING。

    直接调用 service 函数验证状态重置逻辑，避免通过 API 触发
    BackgroundTask（它会尝试加载 WeasyPrint 系统库导致卡死）。
    """
    from app.services.quote_export import retry_failed_documents

    bh = await _buyer_headers(client)
    op = await _op_headers(client)
    rfq_id, quote_id, version = await _create_quoted_rfq(client, bh, op, db_session)

    db_session.add(QuoteDocument(
        quote_id=quote_id, version=version, locale="sw",
        status="FAILED", error_message="font missing",
    ))
    await db_session.commit()

    count = await retry_failed_documents(db_session, quote_id, version, rfq_id)
    assert count == 1

    # 验证状态已重置为 PENDING
    stmt = select(QuoteDocument).where(
        QuoteDocument.quote_id == quote_id,
        QuoteDocument.locale == "sw",
    )
    doc = (await db_session.execute(stmt)).scalar_one()
    assert doc.status == "PENDING"


@pytest.mark.asyncio
async def test_operator_retry_api_returns_count(
    client: AsyncClient, db_session: AsyncSession,
):
    """运营重试 API 返回重试数量。

    注：retry API 会触发 BackgroundTask → generate_quote_documents
    → WeasyPrint 渲染。本地 macOS 无 WeasyPrint 系统库时 BackgroundTask
    会卡死（session 阻塞），跳过此测试。重试逻辑已在上面的 service 层测试覆盖。
    """
    try:
        from weasyprint import HTML  # noqa: F401
    except OSError:
        pytest.skip("WeasyPrint system libs not available — retry API test skipped")

    bh = await _buyer_headers(client)
    op = await _op_headers(client)
    rfq_id, quote_id, version = await _create_quoted_rfq(client, bh, op, db_session)

    db_session.add(QuoteDocument(
        quote_id=quote_id, version=version, locale="sw",
        status="FAILED", error_message="font missing",
    ))
    await db_session.commit()

    r = await client.post(
        f"/api/v1/rfqs/{rfq_id}/quote-documents/retry",
        headers=op,
    )
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["retried"] >= 1