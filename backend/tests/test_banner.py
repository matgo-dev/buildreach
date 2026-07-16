"""Banner 运营管理关键路径集成测。

覆盖缝隙 bug:
- 上传端点权限门(banner:write)
- 上传落盘返回相对 key(banners/xxx,不含 /static、不含 uploads/)
- CRUD 落库 + 管理接口返回原始 key + image_full_url 完整路径
- 公开接口返回带前缀的完整路径
"""
from __future__ import annotations

import io

from httpx import AsyncClient


async def _login(client: AsyncClient, identifier: str) -> dict[str, str]:
    r = await client.post(
        "/api/v1/auth/login",
        json={"identifier": identifier, "password": "Aa123456789"},
    )
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['data']['access_token']}"}


def _png_bytes():
    from PIL import Image as PILImage
    buf = io.BytesIO()
    PILImage.new("RGB", (400, 200), color=(30, 80, 60)).save(buf, format="PNG")
    buf.seek(0)
    return buf


async def test_upload_requires_banner_write(client: AsyncClient):
    """买家无 banner:write，上传被拒。"""
    headers = await _login(client, "buyer@cscec3b.local")
    r = await client.post(
        "/api/v1/operator/banners/upload",
        headers=headers,
        files={"file": ("b.png", _png_bytes(), "image/png")},
    )
    assert r.status_code == 403, r.text


async def test_upload_returns_relative_key(client: AsyncClient):
    """运营上传成功，返回相对 key（banners/ 前缀，非 /static、非 uploads/）。"""
    headers = await _login(client, "operator@platform.local")
    r = await client.post(
        "/api/v1/operator/banners/upload",
        headers=headers,
        files={"file": ("b.png", _png_bytes(), "image/png")},
    )
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["image_url"].startswith("banners/")
    assert not data["image_url"].startswith("/static")
    assert not data["image_url"].startswith("uploads/")
    assert data["full_url"] == f"/static/{data['image_url']}"


async def test_crud_roundtrip_and_url_shape(client: AsyncClient):
    """创建 → 管理列表出现；管理接口 image_url 是相对 key、image_full_url 带前缀；公开接口带前缀。"""
    headers = await _login(client, "operator@platform.local")

    # 创建
    r = await client.post(
        "/api/v1/operator/banners",
        headers=headers,
        json={
            "image_url": "banners/unit-test.jpg",
            "title_zh": "集成测试轮播",
            "sort_order": 777,
            "is_active": True,
            "position": "home_carousel",
        },
    )
    assert r.status_code == 200, r.text
    created = r.json()["data"]
    banner_id = created["id"]
    # 管理接口:image_url 保持相对 key(可回传),image_full_url 带前缀
    assert created["image_url"] == "banners/unit-test.jpg"
    assert created["image_full_url"] == "/static/banners/unit-test.jpg"

    # 管理列表出现
    r = await client.get("/api/v1/operator/banners?position=home_carousel", headers=headers)
    assert r.status_code == 200
    ids = [b["id"] for b in r.json()["data"]]
    assert banner_id in ids

    # 公开接口:image_url 带完整前缀
    r = await client.get("/api/v1/banners?position=home_carousel")
    assert r.status_code == 200
    row = next(b for b in r.json()["data"] if b["title"] == "集成测试轮播")
    assert row["image_url"] == "/static/banners/unit-test.jpg"

    # 清理
    r = await client.delete(f"/api/v1/operator/banners/{banner_id}", headers=headers)
    assert r.status_code == 200


async def test_inactive_hidden_from_public(client: AsyncClient):
    """下架的 banner 不出现在公开接口。"""
    headers = await _login(client, "operator@platform.local")
    r = await client.post(
        "/api/v1/operator/banners",
        headers=headers,
        json={
            "image_url": "banners/hidden.jpg",
            "title_zh": "下架轮播",
            "is_active": False,
            "position": "home_carousel",
        },
    )
    banner_id = r.json()["data"]["id"]

    r = await client.get("/api/v1/banners?position=home_carousel")
    titles = [b["title"] for b in r.json()["data"]]
    assert "下架轮播" not in titles

    await client.delete(f"/api/v1/operator/banners/{banner_id}", headers=headers)
