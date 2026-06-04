"""T2 · 采购方注册按统一社会信用代码识别企业。"""
from __future__ import annotations

import pytest
from sqlalchemy import select

from app.db.models.buyer_member import BuyerMember
from app.db.models.buyer_organization import BuyerOrganization
from app.db.models.user import User


def _payload(*, email="a@cscec3b.com", username=None, phone=None,
             company_name="测试集团", usc="91110000MA01ABCD23") -> dict:
    p = {
        "email": email,
        "name": "Alice",
        "password": "Aa123456789",
        "company_name": company_name,
        "unified_social_credit_code": usc,
    }
    if username is not None:
        p["username"] = username
    if phone is not None:
        p["phone"] = phone
    return p


@pytest.mark.asyncio
async def test_register_buyer_creates_new_org_when_usc_not_seen(client, db_session):
    """信用代码首次出现 → 新建 BuyerOrg,用户成为 owner。"""
    r = await client.post(
        "/api/v1/auth/register/buyer",
        json=_payload(email="founder@new.com", company_name="新公司", usc="91320500NEWFOUND01"),
    )
    assert r.status_code == 200, r.text

    row = await db_session.execute(
        select(BuyerOrganization).where(
            BuyerOrganization.unified_social_credit_code == "91320500NEWFOUND01"
        )
    )
    org = row.scalar_one()
    assert org.name == "新公司"

    user_row = await db_session.execute(select(User).where(User.email == "founder@new.com"))
    user = user_row.scalar_one()
    mem_row = await db_session.execute(
        select(BuyerMember).where(BuyerMember.user_id == user.id)
    )
    mem = mem_row.scalar_one()
    assert mem.buyer_org_id == org.id
    assert mem.is_owner is True


@pytest.mark.asyncio
async def test_register_buyer_joins_existing_org_when_usc_matches(client, db_session):
    """第二个用户用同一 USC 注册 → 加入已存在组织,is_owner=False。"""
    usc = "91320500JOINTEST01"
    r1 = await client.post(
        "/api/v1/auth/register/buyer",
        json=_payload(email="owner@x.com", company_name="共享公司", usc=usc),
    )
    assert r1.status_code == 200, r1.text

    r2 = await client.post(
        "/api/v1/auth/register/buyer",
        json=_payload(email="member@x.com", phone="13911119000",
                      company_name="共享公司", usc=usc),
    )
    assert r2.status_code == 200, r2.text

    row = await db_session.execute(
        select(BuyerOrganization).where(BuyerOrganization.unified_social_credit_code == usc)
    )
    orgs = row.scalars().all()
    assert len(orgs) == 1  # 没有重复组织

    user_row = await db_session.execute(select(User).where(User.email == "member@x.com"))
    user = user_row.scalar_one()
    mem_row = await db_session.execute(
        select(BuyerMember).where(BuyerMember.user_id == user.id)
    )
    mem = mem_row.scalar_one()
    assert mem.buyer_org_id == orgs[0].id
    assert mem.is_owner is False


@pytest.mark.asyncio
async def test_register_buyer_company_name_mismatch_uses_db_name(client, db_session):
    """同一 USC 第二个用户填了不同公司名 → 沿用 DB 已有名字,不阻断。"""
    usc = "91320500MISMATCH01"
    await client.post(
        "/api/v1/auth/register/buyer",
        json=_payload(email="first@x.com", company_name="正确公司", usc=usc),
    )
    r2 = await client.post(
        "/api/v1/auth/register/buyer",
        json=_payload(email="second@x.com", phone="13922229000",
                      company_name="错的名字", usc=usc),
    )
    assert r2.status_code == 200

    row = await db_session.execute(
        select(BuyerOrganization).where(BuyerOrganization.unified_social_credit_code == usc)
    )
    org = row.scalar_one()
    assert org.name == "正确公司"  # DB 中的名字未被覆盖


@pytest.mark.asyncio
async def test_register_buyer_invalid_usc_format(client):
    """USC 必须 18 位大写字母+数字。"""
    cases = [
        ("ABC", "太短"),
        ("a" * 18, "小写字母"),
        ("1" * 17, "17 位"),
        ("1" * 19, "19 位"),
        ("9132050012345!!!67", "含非法字符"),
    ]
    for bad_usc, _label in cases:
        r = await client.post(
            "/api/v1/auth/register/buyer",
            json=_payload(email=f"bad{hash(bad_usc)}@x.com", usc=bad_usc),
        )
        assert r.status_code == 422, f"{_label} 应被拒,实际: {r.status_code}"


@pytest.mark.asyncio
async def test_register_buyer_audit_extra_has_usc_and_owner(client, db_session):
    """注册审计日志的 extra 应含 is_owner / org_created / USC。"""
    from app.db.models.audit_log import AuditLog

    usc = "91320500AUDITTEST1"
    await client.post(
        "/api/v1/auth/register/buyer",
        json=_payload(email="audit@x.com", company_name="审计公司", usc=usc),
    )
    row = await db_session.execute(
        select(AuditLog).where(AuditLog.user_email == "audit@x.com")
    )
    log = row.scalars().first()
    assert log is not None
    assert log.extra is not None
    assert log.extra.get("unified_social_credit_code") == usc
    assert log.extra.get("is_owner") is True
    assert log.extra.get("org_created") is True
