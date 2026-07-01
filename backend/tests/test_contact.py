"""客服联系 — WhatsApp 端点 + 解析函数测试。"""
from __future__ import annotations

from unittest.mock import patch

import pytest
from httpx import AsyncClient

from app.services.contact import resolve_whatsapp_link


# ---- 单元测试:resolve_whatsapp_link ----

class TestResolveWhatsappLink:
    def test_normal_number(self):
        with patch("app.services.contact.settings") as mock_s:
            mock_s.WHATSAPP_DEFAULT_NUMBER = "+255 697 123 456"
            assert resolve_whatsapp_link() == "https://wa.me/255697123456"

    def test_dash_separated(self):
        with patch("app.services.contact.settings") as mock_s:
            mock_s.WHATSAPP_DEFAULT_NUMBER = "255-697-123456"
            assert resolve_whatsapp_link() == "https://wa.me/255697123456"

    def test_international_prefix_00(self):
        with patch("app.services.contact.settings") as mock_s:
            mock_s.WHATSAPP_DEFAULT_NUMBER = "00255697123456"
            assert resolve_whatsapp_link() == "https://wa.me/255697123456"

    def test_empty_string(self):
        with patch("app.services.contact.settings") as mock_s:
            mock_s.WHATSAPP_DEFAULT_NUMBER = ""
            assert resolve_whatsapp_link() is None

    def test_only_symbols(self):
        with patch("app.services.contact.settings") as mock_s:
            mock_s.WHATSAPP_DEFAULT_NUMBER = "+  - "
            assert resolve_whatsapp_link() is None

    def test_context_param_ignored(self):
        with patch("app.services.contact.settings") as mock_s:
            mock_s.WHATSAPP_DEFAULT_NUMBER = "+255697123456"
            assert resolve_whatsapp_link(context={"locale": "sw"}) == "https://wa.me/255697123456"


# ---- 集成测试:GET /api/v1/contact/whatsapp ----

@pytest.mark.asyncio
async def test_whatsapp_endpoint_configured(client: AsyncClient):
    """号码已配置 → 返回链接和原始号码。"""
    with patch("app.services.contact.settings") as mock_s, \
         patch("app.api.v1.contact.settings") as mock_s2:
        mock_s.WHATSAPP_DEFAULT_NUMBER = "+255 697 123 456"
        mock_s2.WHATSAPP_DEFAULT_NUMBER = "+255 697 123 456"
        resp = await client.get("/api/v1/contact/whatsapp")
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    assert body["data"]["whatsapp_link"] == "https://wa.me/255697123456"
    assert body["data"]["number"] == "+255 697 123 456"


@pytest.mark.asyncio
async def test_whatsapp_endpoint_not_configured(client: AsyncClient):
    """号码未配置 → data 字段为 null。"""
    with patch("app.services.contact.settings") as mock_s, \
         patch("app.api.v1.contact.settings") as mock_s2:
        mock_s.WHATSAPP_DEFAULT_NUMBER = ""
        mock_s2.WHATSAPP_DEFAULT_NUMBER = ""
        resp = await client.get("/api/v1/contact/whatsapp")
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    assert body["data"]["whatsapp_link"] is None
    assert body["data"]["number"] is None


@pytest.mark.asyncio
async def test_whatsapp_endpoint_no_auth_required(client: AsyncClient):
    """端点无需登录,未携带 token 也应 200。"""
    with patch("app.services.contact.settings") as mock_s, \
         patch("app.api.v1.contact.settings") as mock_s2:
        mock_s.WHATSAPP_DEFAULT_NUMBER = "+255123456789"
        mock_s2.WHATSAPP_DEFAULT_NUMBER = "+255123456789"
        resp = await client.get("/api/v1/contact/whatsapp")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_contact_info_includes_wechat_runtime_config(client: AsyncClient):
    """联系方式统一从后端运行时配置返回,供前端客服入口使用。

    payload 由 app.services.contact.build_contact_payload() 统一构建,
    故所有字段均从 app.services.contact.settings 读取。
    """
    with patch("app.services.contact.settings") as mock_s:
        mock_s.WHATSAPP_DEFAULT_NUMBER = "+255 697 123 456"
        mock_s.CONTACT_EMAIL = "support@example.com"
        mock_s.WECHAT_ID = "Matgo_Service"
        mock_s.WECHAT_QR_IMAGE = "/contact/wechat-qr.png"
        resp = await client.get("/api/v1/contact/info")

    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    assert body["data"] == {
        "whatsapp_link": "https://wa.me/255697123456",
        "whatsapp_number": "+255 697 123 456",
        "wechat_id": "Matgo_Service",
        "wechat_qr_image": "/contact/wechat-qr.png",
        "email": "support@example.com",
    }


@pytest.mark.asyncio
async def test_contact_info_blank_wechat_config_returns_null(client: AsyncClient):
    """微信未配置时前端拿到 null,从而隐藏 WeChat 入口。"""
    with patch("app.services.contact.settings") as mock_s:
        mock_s.WHATSAPP_DEFAULT_NUMBER = "+255 697 123 456"
        mock_s.CONTACT_EMAIL = "support@example.com"
        mock_s.WECHAT_ID = "  "
        mock_s.WECHAT_QR_IMAGE = ""
        resp = await client.get("/api/v1/contact/info")

    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    assert body["data"]["wechat_id"] is None
    assert body["data"]["wechat_qr_image"] is None
