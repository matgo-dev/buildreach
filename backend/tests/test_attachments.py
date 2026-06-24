"""附件功能测试 — 上传/下载/类型校验/scope/关联。"""
from __future__ import annotations

import io

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

# seed 账号(同 test_cart.py)
_BUYER_EMAIL = "buyer@cscec3b.local"
_BUYER_PASSWORD = "Aa123456789"
_OPERATOR_EMAIL = "operator@platform.local"
_OPERATOR_PASSWORD = "Aa123456789"
_SUPPLIER_EMAIL = "supplier@platform.local"
_SUPPLIER_PASSWORD = "Aa123456789"


async def _login(client: AsyncClient, email: str, password: str) -> dict[str, str]:
    r = await client.post("/api/v1/auth/login", json={"identifier": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['data']['access_token']}"}


async def _buyer_headers(client: AsyncClient) -> dict[str, str]:
    return await _login(client, _BUYER_EMAIL, _BUYER_PASSWORD)


async def _op_headers(client: AsyncClient) -> dict[str, str]:
    return await _login(client, _OPERATOR_EMAIL, _OPERATOR_PASSWORD)


def _make_jpeg(size: int = 1024) -> bytes:
    """生成合法 JPEG 数据。"""
    from PIL import Image
    img = Image.new("RGB", (50, 50), (128, 128, 128))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    data = buf.getvalue()
    # 填充至指定大小
    if len(data) < size:
        data += b"\x00" * (size - len(data))
    return data


def _make_pdf() -> bytes:
    """生成最小合法 PDF。"""
    return (
        b"%PDF-1.0\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj "
        b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj "
        b"3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R>>endobj\n"
        b"xref\n0 4\n0000000000 65535 f \n0000000009 00000 n \n"
        b"0000000058 00000 n \n0000000115 00000 n \n"
        b"trailer<</Size 4/Root 1 0 R>>\nstartxref\n193\n%%EOF\n"
    )


async def _upload_product_image(
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


# ── 上传测试 ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_upload_jpeg(client: AsyncClient):
    """上传合法 JPEG → 200,返回 attachment 数据。"""
    hdr = await _buyer_headers(client)
    data = _make_jpeg()
    r = await client.post(
        "/api/v1/attachments",
        headers=hdr,
        files={"file": ("test.jpg", data, "image/jpeg")},
    )
    assert r.status_code == 200, r.text
    att = r.json()["data"]
    assert att["id"] > 0
    assert att["original_filename"] == "test.jpg"
    assert att["content_type"] == "image/jpeg"
    assert att["download_url"].startswith("/api/v1/attachments/")


@pytest.mark.asyncio
async def test_upload_pdf(client: AsyncClient):
    """上传合法 PDF → 200。"""
    hdr = await _buyer_headers(client)
    data = _make_pdf()
    r = await client.post(
        "/api/v1/attachments",
        headers=hdr,
        files={"file": ("doc.pdf", data, "application/pdf")},
    )
    assert r.status_code == 200, r.text
    assert r.json()["data"]["content_type"] == "application/pdf"


@pytest.mark.asyncio
async def test_upload_fake_png_rejected(client: AsyncClient):
    """上传伪装文件(.png 实为 HTML) → 40523。"""
    hdr = await _buyer_headers(client)
    fake_html = b"<html><body>malicious</body></html>"
    r = await client.post(
        "/api/v1/attachments",
        headers=hdr,
        files={"file": ("evil.png", fake_html, "image/png")},
    )
    assert r.status_code == 422
    assert r.json()["code"] == 40523


@pytest.mark.asyncio
async def test_upload_exe_rejected(client: AsyncClient):
    """上传 .exe 非白名单扩展名 → 40523。"""
    hdr = await _buyer_headers(client)
    r = await client.post(
        "/api/v1/attachments",
        headers=hdr,
        files={"file": ("virus.exe", b"MZ\x90\x00", "application/octet-stream")},
    )
    assert r.status_code == 422
    assert r.json()["code"] == 40523


@pytest.mark.asyncio
async def test_upload_too_large(client: AsyncClient):
    """上传超大图片 → 40524。"""
    hdr = await _buyer_headers(client)
    # 6MB JPEG(超过 5MB 限制)
    big_data = _make_jpeg() + b"\x00" * (6 * 1024 * 1024)
    r = await client.post(
        "/api/v1/attachments",
        headers=hdr,
        files={"file": ("big.jpg", big_data, "image/jpeg")},
    )
    assert r.status_code == 413
    assert r.json()["code"] == 40524


# ── 下载 scope 测试 ──────────────────────────────────────


@pytest.mark.asyncio
async def test_download_own_orphan(client: AsyncClient):
    """上传者下载自己的孤儿附件(TTL 内) → 200。"""
    hdr = await _buyer_headers(client)
    data = _make_jpeg()
    r = await client.post(
        "/api/v1/attachments",
        headers=hdr,
        files={"file": ("photo.jpg", data, "image/jpeg")},
    )
    assert r.status_code == 200
    att_id = r.json()["data"]["id"]

    # 下载
    r2 = await client.get(f"/api/v1/attachments/{att_id}/download", headers=hdr)
    assert r2.status_code == 200
    assert "attachment" in r2.headers.get("content-disposition", "")
    assert r2.headers.get("x-content-type-options") == "nosniff"


@pytest.mark.asyncio
async def test_download_other_user_orphan_denied(client: AsyncClient):
    """其他买方下载他人孤儿附件 → 404。"""
    hdr = await _buyer_headers(client)
    data = _make_jpeg()
    r = await client.post(
        "/api/v1/attachments",
        headers=hdr,
        files={"file": ("photo.jpg", data, "image/jpeg")},
    )
    att_id = r.json()["data"]["id"]

    # 用运营账号下载(无 RFQ 归属,不是上传者)
    op_hdr = await _op_headers(client)
    r2 = await client.get(f"/api/v1/attachments/{att_id}/download", headers=op_hdr)
    assert r2.status_code == 404


@pytest.mark.asyncio
async def test_nonascii_filename_download(client: AsyncClient):
    """中文文件名下载 → 响应含 filename*=UTF-8'' 编码。"""
    hdr = await _buyer_headers(client)
    data = _make_jpeg()
    r = await client.post(
        "/api/v1/attachments",
        headers=hdr,
        files={"file": ("采购清单.jpg", data, "image/jpeg")},
    )
    assert r.status_code == 200
    att_id = r.json()["data"]["id"]

    r2 = await client.get(f"/api/v1/attachments/{att_id}/download", headers=hdr)
    assert r2.status_code == 200
    disp = r2.headers.get("content-disposition", "")
    assert "filename*=UTF-8''" in disp


# ── RFQ 关联测试 ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_rfq_create_with_attachments(client: AsyncClient, db_session: AsyncSession):
    """创建 RFQ 时关联附件 → 详情返回 attachments 列表。"""
    from sqlalchemy import select
    from app.db.models import Category

    hdr = await _buyer_headers(client)

    # 上传附件
    data = _make_jpeg()
    r = await client.post(
        "/api/v1/attachments",
        headers=hdr,
        files={"file": ("spec.jpg", data, "image/jpeg")},
    )
    assert r.status_code == 200
    att_id = r.json()["data"]["id"]

    # 创建可购商品
    op_hdr = await _op_headers(client)
    cat = (await db_session.execute(
        select(Category).where(Category.level == 3).limit(1)
    )).scalar_one_or_none()
    assert cat is not None

    r = await client.post("/api/v1/operator/products", headers=op_hdr, json={
        "name": "Attach Test Product",
        "category_code": cat.code,
        "unit": "PCS",
        "currency": "TZS",
    })
    assert r.status_code == 200, r.text
    product_id = r.json()["data"]["id"]
    await _upload_product_image(client, op_hdr, product_id)

    r = await client.patch(
        f"/api/v1/operator/products/{product_id}/status?force=true",
        headers=op_hdr,
        json={"status": "ACTIVE"},
    )
    assert r.status_code == 200, r.text

    # 创建 RFQ 带 attachment_ids
    r = await client.post("/api/v1/rfqs", headers=hdr, json={
        "items": [{"product_id": product_id, "quantity": 10}],
        "attachment_ids": [att_id],
    })
    assert r.status_code == 200, r.text
    rfq_data = r.json()["data"]
    assert len(rfq_data["attachments"]) == 1
    assert rfq_data["attachments"][0]["id"] == att_id

    # 详情也应返回附件
    rfq_id = rfq_data["id"]
    r = await client.get(f"/api/v1/rfqs/{rfq_id}", headers=hdr)
    assert r.status_code == 200
    assert len(r.json()["data"]["attachments"]) == 1

    # 附件已归属 RFQ 后,运营可下载
    r = await client.get(f"/api/v1/attachments/{att_id}/download", headers=op_hdr)
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_rfq_update_keeps_attachments(client: AsyncClient, db_session: AsyncSession):
    """RFQ update 保留已关联附件(幂等) → 不报错。"""
    from sqlalchemy import select
    from app.db.models import Category

    hdr = await _buyer_headers(client)

    # 上传 2 个附件
    att_ids = []
    for name in ("a.jpg", "b.jpg"):
        data = _make_jpeg()
        r = await client.post(
            "/api/v1/attachments",
            headers=hdr,
            files={"file": (name, data, "image/jpeg")},
        )
        assert r.status_code == 200
        att_ids.append(r.json()["data"]["id"])

    # 创建可购商品
    op_hdr = await _op_headers(client)
    cat = (await db_session.execute(
        select(Category).where(Category.level == 3).limit(1)
    )).scalar_one_or_none()

    r = await client.post("/api/v1/operator/products", headers=op_hdr, json={
        "name": "Attach Update Test",
        "category_code": cat.code,
        "unit": "PCS",
        "currency": "TZS",
    })
    product_id = r.json()["data"]["id"]
    await _upload_product_image(client, op_hdr, product_id)
    r = await client.patch(
        f"/api/v1/operator/products/{product_id}/status?force=true",
        headers=op_hdr,
        json={"status": "ACTIVE"},
    )
    assert r.status_code == 200, r.text

    # 创建 RFQ 为草稿
    r = await client.post("/api/v1/rfqs", headers=hdr, json={
        "items": [{"product_id": product_id, "quantity": 5}],
        "as_draft": True,
        "attachment_ids": att_ids,
    })
    assert r.status_code == 200
    rfq_id = r.json()["data"]["id"]

    # update: 保留第一个,去掉第二个
    r = await client.patch(f"/api/v1/rfqs/{rfq_id}", headers=hdr, json={
        "items": [{"product_id": product_id, "quantity": 5}],
        "attachment_ids": [att_ids[0]],
    })
    assert r.status_code == 200
    atts = r.json()["data"]["attachments"]
    assert len(atts) == 1
    assert atts[0]["id"] == att_ids[0]
