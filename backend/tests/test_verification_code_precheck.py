"""发码前预检:注册发码先查邮箱占用、通用发码接口只服务 REGISTER、找回密码明说未注册。"""
from __future__ import annotations

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.db.models.user import User, UserStatus
from app.db.models.verification_code import VerificationCode
from tests.conftest import register_buyer_tz


@pytest.fixture
def sent(monkeypatch):
    """记录发信调用,不真发。"""
    from app.services import verification_service

    calls: list[str] = []

    def _fake_send(*, to_email, code, purpose):
        calls.append(to_email)
        return True

    monkeypatch.setattr(verification_service, "send_verification_code_email", _fake_send)
    return calls


async def _codes(db_session, email: str) -> list[VerificationCode]:
    rows = await db_session.execute(select(VerificationCode).where(VerificationCode.email == email))
    return list(rows.scalars().all())


def _error_codes(resp) -> list[int]:
    return [e["code"] for e in (resp.json().get("data") or {}).get("errors") or []]


@pytest.mark.asyncio
async def test_register_code_rejected_for_registered_email(client, db_session, sent, monkeypatch):
    """已注册邮箱发 REGISTER 码 → 40922,不写验证码行、不发信。"""
    monkeypatch.setattr(settings, "REQUIRE_EMAIL_VERIFICATION", True)
    email = (await register_buyer_tz(client))["email"]

    r = await client.post(
        "/api/v1/auth/verification-code/send",
        json={"email": f" {email} ", "purpose": "REGISTER"},
    )

    assert r.status_code == 409, r.text
    assert _error_codes(r) == [40922]
    assert await _codes(db_session, email) == []
    assert sent == []


@pytest.mark.asyncio
async def test_register_code_rejected_for_disabled_account_email(client, db_session, sent, monkeypatch):
    """停用账号仍占用邮箱(与注册提交、唯一索引口径一致)→ 同样 40922。"""
    monkeypatch.setattr(settings, "REQUIRE_EMAIL_VERIFICATION", True)
    email = (await register_buyer_tz(client))["email"]
    user = (await db_session.execute(select(User).where(User.email == email))).scalar_one()
    user.status = UserStatus.DISABLED
    await db_session.commit()

    r = await client.post(
        "/api/v1/auth/verification-code/send",
        json={"email": email, "purpose": "REGISTER"},
    )

    assert r.status_code == 409, r.text
    assert _error_codes(r) == [40922]
    assert sent == []


@pytest.mark.asyncio
async def test_register_code_sent_for_new_email(client, db_session, sent, monkeypatch):
    monkeypatch.setattr(settings, "REQUIRE_EMAIL_VERIFICATION", True)
    email = "precheck-new@example.com"

    r = await client.post(
        "/api/v1/auth/verification-code/send",
        json={"email": email, "purpose": "REGISTER"},
    )

    assert r.status_code == 200, r.text
    assert len(await _codes(db_session, email)) == 1
    assert sent == [email]


@pytest.mark.asyncio
async def test_generic_send_rejects_reset_password_purpose(client, db_session, sent):
    """找回密码走 /forgot-password;通用接口不再替任意邮箱发 RESET_PASSWORD 信。"""
    email = "precheck-reset@example.com"

    r = await client.post(
        "/api/v1/auth/verification-code/send",
        json={"email": email, "purpose": "RESET_PASSWORD"},
    )

    assert r.status_code == 422, r.text
    assert await _codes(db_session, email) == []
    assert sent == []


@pytest.mark.asyncio
async def test_forgot_password_unregistered_email_explicit(client, db_session, sent):
    email = "precheck-nobody@example.com"

    r = await client.post("/api/v1/auth/forgot-password", data={"email": email})

    assert r.status_code == 409, r.text
    assert _error_codes(r) == [40108]
    assert await _codes(db_session, email) == []
    assert sent == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status", "biz_code"),
    [(UserStatus.DISABLED, 40005), (UserStatus.DEACTIVATED, 40305)],
)
async def test_forgot_password_inactive_account_not_called_unregistered(
    client, db_session, sent, status, biz_code
):
    """邮箱被非 ACTIVE 账号占用:说"未注册"会与注册页"已注册"矛盾,复用登录的停用/注销码。"""
    email = (await register_buyer_tz(client))["email"]
    user = (await db_session.execute(select(User).where(User.email == email))).scalar_one()
    user.status = status
    await db_session.commit()

    r = await client.post("/api/v1/auth/forgot-password", data={"email": email})

    assert r.status_code == 403, r.text
    assert r.json()["code"] == biz_code
    assert sent == []
