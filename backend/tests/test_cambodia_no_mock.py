"""Δ8:柬埔寨注册不写 mock 占位评分。

验收点 #1:KH 供应商注册后 credit_company 已建、4 张数据表无 mock 行、无 snapshot。
对照:非 KH(CN)仍走 mock 占位,有 snapshot。
"""
from __future__ import annotations

import pytest
from sqlalchemy import func, select

from app.db.models import (
    CreditCompanyBasicData,
    CreditCompanyCertification,
    CreditCompanyFinanceData,
    CreditCompanyLegalData,
    ScoreSnapshot,
)
from app.db.models.supplier_organization import SupplierOrganization, SupplierOrgStatus
from app.services.credit.registration_hook import create_credit_for_supplier

_DATA_MODELS = (
    CreditCompanyBasicData,
    CreditCompanyFinanceData,
    CreditCompanyLegalData,
    CreditCompanyCertification,
)


@pytest.mark.asyncio
async def test_kh_register_writes_no_mock(client, db_session):
    org = SupplierOrganization(
        name="KH No Mock Co.", country_code="KH", registration_no="KH-NM-1",
        status=SupplierOrgStatus.APPROVED,
    )
    db_session.add(org)
    await db_session.flush()

    company = await create_credit_for_supplier(db_session, org, source="test", run_ai=False)
    await db_session.commit()

    # credit_company 已建并 link；KH 不带 expected_grade
    assert company is not None
    assert company.country_code == "KH"
    assert company.linked_supplier_org_id == org.id
    assert company.data_status is None

    # 4 张数据表无任何行（KH 根本不写 mock）
    for model in _DATA_MODELS:
        cnt = (await db_session.execute(
            select(func.count()).select_from(model).where(model.company_id == company.id)
        )).scalar_one()
        assert cnt == 0, f"{model.__name__} 不应有行,实际 {cnt}"

    # 无 snapshot（留待 harvest）
    snap = (await db_session.execute(
        select(ScoreSnapshot).where(ScoreSnapshot.company_id == company.id)
    )).scalar_one_or_none()
    assert snap is None


@pytest.mark.asyncio
async def test_non_kh_register_still_mocks(client, db_session):
    """对照:CN 供应商仍走 mock 占位,有 snapshot(确认只对 KH 关闭)。"""
    org = SupplierOrganization(
        name="CN Still Mock Co.", country_code="CN", registration_no="CN-SM-1",
        status=SupplierOrgStatus.APPROVED,
    )
    db_session.add(org)
    await db_session.flush()

    company = await create_credit_for_supplier(
        db_session, org, target_tier="B", source="test", run_ai=False
    )
    await db_session.commit()

    assert company is not None
    assert company.data_status == {"expected_grade": "B"}

    snap = (await db_session.execute(
        select(ScoreSnapshot).where(
            ScoreSnapshot.company_id == company.id,
            ScoreSnapshot.is_current.is_(True),
        )
    )).scalar_one_or_none()
    assert snap is not None
