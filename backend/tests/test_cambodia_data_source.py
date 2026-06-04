"""CambodiaDataSource 单测(Δ7 Step 8)。读最新一条快照,与 MockDataSource 行为对齐。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import CreditCompany, CreditCompanyBasicData
from app.services.credit.data_source.cambodia_data_source import CambodiaDataSource
from app.services.credit.data_source.registry import resolve_data_source


async def test_reads_latest_snapshot(test_engine):
    SessionLocal = async_sessionmaker(test_engine, expire_on_commit=False, autoflush=False)
    async with SessionLocal() as db:
        company = CreditCompany(name="C", country_code="KH", registration_no="X")
        db.add(company)
        await db.flush()
        db.add(CreditCompanyBasicData(
            company_id=company.id, data_source="public",
            fetched_at=datetime(2020, 1, 1), registered_capital="OLD",
        ))
        db.add(CreditCompanyBasicData(
            company_id=company.id, data_source="public",
            fetched_at=datetime(2024, 1, 1), registered_capital="NEW",
        ))
        await db.flush()

        ds = CambodiaDataSource()
        basic = await ds.fetch_basic_data(db, company.id)
        assert basic.registered_capital == "NEW"  # 读最新一条
        # 无数据 → missing stub
        finance = await ds.fetch_finance_data(db, company.id)
        assert finance.is_missing


def test_registry_routes_kh_to_cambodia():
    assert isinstance(resolve_data_source("KH"), CambodiaDataSource)
    assert isinstance(resolve_data_source("kh"), CambodiaDataSource)
    # 其他国别不是 CambodiaDataSource
    assert not isinstance(resolve_data_source("CN"), CambodiaDataSource)
