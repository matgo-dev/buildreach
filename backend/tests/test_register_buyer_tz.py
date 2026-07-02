"""T2 · 坦桑尼亚买方注册测试。"""
from __future__ import annotations

import pytest
from sqlalchemy import select

from tests.conftest import register_buyer_tz, _make_test_image, _next_phone, _make_verification_token
from app.db.models.buyer_org_image import BuyerOrgImage, BuyerOrgImageType
from app.db.models.buyer_organization import BuyerOrganization
from app.db.models.user import User


async def _post_buyer(client, *, phone=None, whatsapp=None, email=None):
    """直发买方注册请求;phone/whatsapp 为 None 时不放入表单(模拟前端不填)。"""
    if email is None:
        email = f"contact{_next_phone().replace('+', '')}@gmail.com"
    data = {
        "password": "Aa123456789",
        "name": "Test",
        "company_name": "Shop",
        "address": "Dar es Salaam",
        "business_category_codes": "01",
        "email": email,
        "verification_token": _make_verification_token(email),
    }
    if phone is not None:
        data["phone"] = phone
    if whatsapp is not None:
        data["whatsapp"] = whatsapp
    r = await client.post(
        "/api/v1/auth/register/buyer",
        data=data,
        files=[("storefront_images", ("shop.jpg", _make_test_image(), "image/jpeg"))],
    )
    return r, email


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
    """缺少 FastAPI 必填 Form 字段(password)→ 422(Form 解析层拦截)。"""
    img = _make_test_image()
    # 缺 password(Form(...) 必填)→ FastAPI 自身校验,先于 handler 报 422
    r = await client.post(
        "/api/v1/auth/register/buyer",
        data={
            "phone": _next_phone(),
            "name": "Test",
            "company_name": "Shop",
            "business_category_codes": "01",
            "email": f"buyertz{_next_phone().replace('+', '')}@example.com",
        },
        files=[("storefront_images", ("shop.jpg", img, "image/jpeg"))],
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_register_buyer_phone_only_succeeds(client):
    """只填手机号、不填 WhatsApp → 二选一通过,注册成功。"""
    r, _ = await _post_buyer(client, phone=_next_phone(), whatsapp=None)
    assert r.status_code == 200, r.text


@pytest.mark.asyncio
async def test_register_buyer_whatsapp_only_stores_null_phone(client, db_session):
    """只填 WhatsApp、不填手机号 → 注册成功,且 phone 落库为 NULL(非空串)。"""
    r, email = await _post_buyer(client, phone=None, whatsapp=_next_phone())
    assert r.status_code == 200, r.text
    user = (
        await db_session.execute(select(User).where(User.email == email))
    ).scalar_one()
    assert user.phone is None
    assert user.whatsapp


@pytest.mark.asyncio
async def test_register_buyer_missing_both_contacts_rejected(client):
    """手机号与 WhatsApp 都不填 → 409,字段级错误 code 42211。"""
    r, _ = await _post_buyer(client, phone=None, whatsapp=None)
    assert r.status_code == 409, r.text
    errors = r.json()["data"]["errors"]
    assert any(e["code"] == 42211 and e["field"] == "phone" for e in errors)


@pytest.mark.asyncio
async def test_register_buyer_empty_string_contacts_rejected(client):
    """手机号与 WhatsApp 传空串 → 与不填等价,409 code 42211。"""
    r, _ = await _post_buyer(client, phone="  ", whatsapp="")
    assert r.status_code == 409, r.text
    errors = r.json()["data"]["errors"]
    assert any(e["code"] == 42211 for e in errors)


@pytest.mark.asyncio
async def test_register_buyer_two_whatsapp_only_no_phone_collision(client):
    """两个仅填 WhatsApp 的买方(phone 均为 NULL)→ 不撞 uq_users_phone 唯一索引。"""
    r1, _ = await _post_buyer(client, phone=None, whatsapp=_next_phone())
    assert r1.status_code == 200, r1.text
    r2, _ = await _post_buyer(client, phone=None, whatsapp=_next_phone())
    assert r2.status_code == 200, r2.text


@pytest.mark.asyncio
async def test_register_buyer_no_image(client):
    """不传店面图片 → 可选字段,请求正常到达业务层(非 422)。"""
    phone = _next_phone()
    email = f"buyertz{phone.replace('+', '')}@example.com"
    r = await client.post(
        "/api/v1/auth/register/buyer",
        data={
            "phone": phone,
            "password": "Aa123456789",
            "name": "Test",
            "company_name": "Shop",
            "address": "Dar es Salaam",
            "business_category_codes": "01",
            "email": email,
            "whatsapp": phone,
            "verification_token": _make_verification_token(email),
        },
    )
    assert r.status_code != 422


@pytest.mark.asyncio
async def test_register_buyer_invalid_phone_format(client):
    """非 +255 格式手机号 → 409(MultipleValidationError)。"""
    img = _make_test_image()
    email = f"badphone{_next_phone().replace('+', '')}@example.com"
    r = await client.post(
        "/api/v1/auth/register/buyer",
        data={
            "phone": "13800138000",
            "password": "Aa123456789",
            "name": "Test",
            "company_name": "Shop",
            "address": "Dar es Salaam",
            "business_category_codes": "01",
            "email": email,
            "whatsapp": "13800138000",
            "verification_token": _make_verification_token(email),
        },
        files=[("storefront_images", ("shop.jpg", img, "image/jpeg"))],
    )
    assert r.status_code == 409


@pytest.mark.asyncio
async def test_register_buyer_invalid_image_content_returns_field_error(client):
    """图片扩展名合法但内容非法 → 返回字段级聚合错误。"""
    phone = _next_phone()
    email = f"badimage{phone.replace('+', '')}@gmail.com"
    r = await client.post(
        "/api/v1/auth/register/buyer",
        data={
            "phone": phone,
            "password": "Aa123456789",
            "name": "Bad Image User",
            "company_name": "Bad Image Shop",
            "address": "Dar es Salaam",
            "business_category_codes": "01",
            "email": email,
            "whatsapp": phone,
            "verification_token": _make_verification_token(email),
        },
        files=[("storefront_images", ("shop.jpg", b"not an image", "image/jpeg"))],
    )

    assert r.status_code == 409
    error = r.json()["data"]["errors"][0]
    assert error["field"] == "storefront_images[0]"
    assert error["code"] == 42206


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


@pytest.mark.asyncio
async def test_register_buyer_images_saved_to_private_uploads(client, db_session, tmp_path, monkeypatch):
    """门店照和证照图片都写入 private_uploads,不进入公开 uploads。"""
    from app.services import _buyer_utils

    public_root = tmp_path / "uploads"
    private_root = tmp_path / "private_uploads"
    monkeypatch.setattr(_buyer_utils, "UPLOAD_BASE_DIR", public_root)
    monkeypatch.setattr(_buyer_utils, "PRIVATE_UPLOAD_BASE_DIR", private_root)

    company_name = f"Private Shop {_next_phone().replace('+', '')}"
    result = await register_buyer_tz(
        client,
        company_name=company_name,
        with_license=True,
    )
    assert result["response"].status_code == 200, result["response"].text

    org = (
        await db_session.execute(
            select(BuyerOrganization).where(BuyerOrganization.name == company_name)
        )
    ).scalar_one()
    images = (
        await db_session.execute(
            select(BuyerOrgImage).where(BuyerOrgImage.buyer_org_id == org.id)
        )
    ).scalars().all()

    by_type = {img.image_type: img for img in images}
    storefront = by_type[BuyerOrgImageType.STOREFRONT]
    license_img = by_type[BuyerOrgImageType.LICENSE]

    assert storefront.image_key.startswith("buyer_orgs/storefront/")
    assert license_img.image_key.startswith("buyer_orgs/licenses/")
    assert (private_root / storefront.image_key).is_file()
    assert (private_root / license_img.image_key).is_file()
    assert not (public_root / storefront.image_key).exists()
    assert not (public_root / license_img.image_key).exists()
