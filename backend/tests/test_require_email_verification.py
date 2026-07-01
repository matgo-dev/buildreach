"""REQUIRE_EMAIL_VERIFICATION 开关:买方注册邮箱验证门控。"""
from __future__ import annotations

import pytest

from app.core.config import settings
from tests.conftest import _make_test_image, _next_phone, register_buyer_tz


def _buyer_form(phone: str) -> tuple[dict, list]:
    email = f"buyertz{phone.replace('+', '')}@gmail.com"
    data = {
        "phone": phone,
        "password": "Aa123456789",
        "name": "Test User",
        "company_name": "Test Shop",
        "address": "Dar es Salaam",
        "business_category_codes": "01",
        "email": email,
        "whatsapp": phone,
        # 故意不带 verification_token
    }
    files = [("storefront_images", ("shop.jpg", _make_test_image(), "image/jpeg"))]
    return data, files


@pytest.mark.asyncio
async def test_config_endpoint_exposes_flag(client):
    """GET /api/v1/config 返回 auth.require_email_verification + contact。"""
    r = await client.get("/api/v1/config")
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert "contact" in data
    assert data["auth"]["require_email_verification"] == settings.REQUIRE_EMAIL_VERIFICATION


@pytest.mark.asyncio
async def test_register_without_token_rejected_when_on(client, monkeypatch):
    """flag=on 时,注册不带 verification_token → 40106 校验错误。"""
    monkeypatch.setattr(settings, "REQUIRE_EMAIL_VERIFICATION", True)
    data, files = _buyer_form(_next_phone())
    r = await client.post("/api/v1/auth/register/buyer", data=data, files=files)
    assert r.status_code != 200
    body = r.json()
    errs = (body.get("data") or {}).get("errors") or []
    assert any(e.get("code") == 40106 for e in errs), body


@pytest.mark.asyncio
async def test_register_without_token_ok_when_off(client, monkeypatch):
    """flag=off 时,注册不带 verification_token → 200 且自动登录。"""
    monkeypatch.setattr(settings, "REQUIRE_EMAIL_VERIFICATION", False)
    data, files = _buyer_form(_next_phone())
    r = await client.post("/api/v1/auth/register/buyer", data=data, files=files)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["code"] == 0
    assert body["data"]["access_token"]


@pytest.mark.asyncio
async def test_register_with_token_still_ok_when_off(client, monkeypatch):
    """flag=off 时,即使前端误传 token 也被忽略,注册照常成功。"""
    monkeypatch.setattr(settings, "REQUIRE_EMAIL_VERIFICATION", False)
    result = await register_buyer_tz(client)  # helper 会带上 token
    assert result["response"].status_code == 200, result["response"].text


@pytest.mark.asyncio
async def test_send_register_code_rejected_when_off(client, monkeypatch):
    """flag=off 时,发送 REGISTER 验证码 → 40008 拒绝。"""
    monkeypatch.setattr(settings, "REQUIRE_EMAIL_VERIFICATION", False)
    r = await client.post(
        "/api/v1/auth/verification-code/send",
        json={"email": "someone@gmail.com", "purpose": "REGISTER"},
    )
    assert r.status_code == 400, r.text
    assert r.json()["code"] == 40008
