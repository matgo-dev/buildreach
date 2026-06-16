"""T2 · 坦桑尼亚买方注册测试。"""
from __future__ import annotations

import pytest

from tests.conftest import register_buyer_tz, _make_test_image, _next_phone


@pytest.mark.asyncio
async def test_register_buyer_creates_org(client):
    """注册成功 → 创建 BuyerOrg,返回 TokenOut(自动登录)。"""
    result = await register_buyer_tz(client)
    r = result["response"]
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["code"] == 0
    assert body["data"]["access_token"]


@pytest.mark.asyncio
async def test_register_buyer_duplicate_phone(client):
    """同一手机号重复注册 → 409。"""
    phone = _next_phone()
    await register_buyer_tz(client, phone=phone)
    result = await register_buyer_tz(client, phone=phone)
    assert result["response"].status_code == 409


@pytest.mark.asyncio
async def test_register_buyer_missing_required_fields(client):
    """缺少必填字段 → 422(FastAPI Form 必填字段缺失)。"""
    img = _make_test_image()
    # 缺 address → FastAPI 自身校验
    r = await client.post(
        "/api/v1/auth/register/buyer",
        data={
            "phone": _next_phone(),
            "password": "Aa123456789!",
            "name": "Test",
            "company_name": "Shop",
            "business_category_codes": "01",
        },
        files=[("storefront_images", ("shop.jpg", img, "image/jpeg"))],
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_register_buyer_no_image(client):
    """缺少店面图片 → 422(FastAPI File 必填字段缺失)。"""
    r = await client.post(
        "/api/v1/auth/register/buyer",
        data={
            "phone": _next_phone(),
            "password": "Aa123456789!",
            "name": "Test",
            "company_name": "Shop",
            "address": "Dar es Salaam",
            "business_category_codes": "01",
        },
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_register_buyer_invalid_phone_format(client):
    """非 +255 格式手机号 → 409(MultipleValidationError)。"""
    img = _make_test_image()
    r = await client.post(
        "/api/v1/auth/register/buyer",
        data={
            "phone": "13800138000",  # 中国号码格式
            "password": "Aa123456789!",
            "name": "Test",
            "company_name": "Shop",
            "address": "Dar es Salaam",
            "business_category_codes": "01",
        },
        files=[("storefront_images", ("shop.jpg", img, "image/jpeg"))],
    )
    assert r.status_code == 409


@pytest.mark.asyncio
async def test_register_buyer_weak_password(client):
    """弱密码 → 409(MultipleValidationError)。"""
    result = await register_buyer_tz(client, password="abc")
    assert result["response"].status_code == 409


@pytest.mark.asyncio
async def test_register_buyer_with_optional_email(client):
    """带可选 email 注册成功。"""
    unique_email = f"buyertz{_next_phone().replace('+', '')}@gmail.com"
    result = await register_buyer_tz(client, email=unique_email)
    assert result["response"].status_code == 200, result["response"].text


@pytest.mark.asyncio
async def test_register_buyer_auto_login_token_works(client):
    """注册返回的 token 可直接访问 /me。"""
    result = await register_buyer_tz(client)
    token = result["response"].json()["data"]["access_token"]
    me = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    data = me.json()["data"]
    assert "BUYER" in data["roles"]
    assert data["organization"]["type"] == "BUYER_ORG"
