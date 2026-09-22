"""邮箱身份不区分大小写:各入口统一归一化 + DB CHECK 兜底。"""
from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.config import settings
from app.db.models.user import User
from tests.conftest import _next_phone, register_buyer_tz


@pytest.fixture
def no_mail(monkeypatch):
    from app.services import verification_service

    monkeypatch.setattr(verification_service, "send_verification_code_email", lambda **kw: True)
    monkeypatch.setattr(verification_service, "_generate_code", lambda: "123456")


def _mixed(phone: str) -> str:
    return f"  Case.{phone.replace('+', '')}@Gmail.COM "


@pytest.mark.asyncio
async def test_buyer_register_stores_lowercase_and_login_ignores_case(client, db_session):
    phone = _next_phone()
    mixed = _mixed(phone)
    r = (await register_buyer_tz(client, phone=phone, email=mixed))["response"]
    assert r.status_code == 200, r.text

    stored = (await db_session.execute(
        select(User.email).where(User.phone == phone))).scalar_one()
    assert stored == mixed.strip().lower()

    login = await client.post(
        "/api/v1/auth/login",
        json={"identifier": stored.upper(), "password": "Aa123456789"},
    )
    assert login.status_code == 200, login.text


@pytest.mark.asyncio
async def test_register_rejects_case_variant_of_existing_email(client):
    phone = _next_phone()
    email = (await register_buyer_tz(client, phone=phone))["email"]
    r = (await register_buyer_tz(client, email=email.upper()))["response"]
    assert r.status_code == 409, r.text
    assert any(e["code"] == 40922 for e in r.json()["data"]["errors"])


@pytest.mark.asyncio
async def test_verification_flow_with_mixed_case_email(client, no_mail, monkeypatch):
    """发码/验码/注册三步大小写各异,仍对得上(token.sub 与注册邮箱同一归一口径)。"""
    monkeypatch.setattr(settings, "REQUIRE_EMAIL_VERIFICATION", True)
    phone = _next_phone()
    lower = f"flow.{phone.replace('+', '')}@gmail.com"

    send = await client.post("/api/v1/auth/verification-code/send",
                             json={"email": lower.upper(), "purpose": "REGISTER"})
    assert send.status_code == 200, send.text
    verify = await client.post("/api/v1/auth/verification-code/verify",
                               json={"email": f" {lower.title()} ", "code": "123456", "purpose": "REGISTER"})
    assert verify.status_code == 200, verify.text
    token = verify.json()["data"]["verification_token"]

    from tests.conftest import _make_test_image
    r = await client.post("/api/v1/auth/register/buyer", data={
        "phone": phone, "whatsapp": phone, "password": "Aa123456789", "name": "T",
        "email": lower.capitalize(), "verification_token": token,
    }, files=[("storefront_images", ("s.jpg", _make_test_image(), "image/jpeg"))])
    assert r.status_code == 200, r.text


@pytest.mark.asyncio
async def test_forgot_password_ignores_case(client, no_mail):
    email = (await register_buyer_tz(client))["email"]
    r = await client.post("/api/v1/auth/forgot-password", data={"email": email.upper()})
    assert r.status_code == 200, r.text


@pytest.mark.asyncio
async def test_db_rejects_non_normalized_email(db_session):
    """应用层漏归一化时由 DB CHECK 兜住,而不是悄悄存入大小写变体。"""
    db_session.add(User(email="Upper@gmail.com", name="x", password_hash="x", status="ACTIVE"))
    with pytest.raises(IntegrityError, match="ck_users_email_normalized"):
        await db_session.flush()
    await db_session.rollback()
