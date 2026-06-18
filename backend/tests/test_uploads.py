"""文件上传端点测试。"""
import io

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession


async def _buyer_headers(client: AsyncClient) -> dict:
    """复用 test_cart 的登录逻辑。"""
    from tests.test_cart import _buyer_headers as _bh
    return await _bh(client)


async def _op_headers(client: AsyncClient) -> dict:
    from tests.test_cart import _op_headers as _oh
    return await _oh(client)


@pytest.mark.asyncio
async def test_upload_valid_jpg(client: AsyncClient, db_session: AsyncSession):
    """合法 JPG 上传 → 200"""
    hdr = await _buyer_headers(client)
    # 最小合法 JPEG header
    jpeg_header = bytes([
        0xFF, 0xD8, 0xFF, 0xE0, 0x00, 0x10, 0x4A, 0x46, 0x49, 0x46, 0x00,
    ])
    fake_jpg = jpeg_header + b"\x00" * 100 + b"\xFF\xD9"
    resp = await client.post(
        "/api/v1/uploads/files",
        files={"file": ("test.jpg", io.BytesIO(fake_jpg), "image/jpeg")},
        headers=hdr,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["url"].startswith("/static/rfq-attachments/")
    assert data["url"].endswith(".jpg")
    assert data["filename"] == "test.jpg"


@pytest.mark.asyncio
async def test_upload_valid_pdf(client: AsyncClient, db_session: AsyncSession):
    """合法 PDF 上传 → 200"""
    hdr = await _buyer_headers(client)
    fake_pdf = b"%PDF-1.4 fake content"
    resp = await client.post(
        "/api/v1/uploads/files",
        files={"file": ("spec.pdf", io.BytesIO(fake_pdf), "application/pdf")},
        headers=hdr,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["url"].endswith(".pdf")


@pytest.mark.asyncio
async def test_upload_invalid_mime_422(client: AsyncClient, db_session: AsyncSession):
    """非白名单 MIME → 422"""
    hdr = await _buyer_headers(client)
    resp = await client.post(
        "/api/v1/uploads/files",
        files={"file": ("evil.exe", io.BytesIO(b"MZ\x00"), "application/x-msdownload")},
        headers=hdr,
    )
    assert resp.status_code == 422, resp.text


@pytest.mark.asyncio
async def test_upload_too_large_422(client: AsyncClient, db_session: AsyncSession):
    """超大文件 (6MB JPG) → 422"""
    hdr = await _buyer_headers(client)
    jpeg_header = bytes([0xFF, 0xD8, 0xFF, 0xE0, 0x00, 0x10, 0x4A, 0x46, 0x49, 0x46, 0x00])
    big_file = jpeg_header + b"\x00" * (6 * 1024 * 1024)
    resp = await client.post(
        "/api/v1/uploads/files",
        files={"file": ("big.jpg", io.BytesIO(big_file), "image/jpeg")},
        headers=hdr,
    )
    assert resp.status_code == 422, resp.text
