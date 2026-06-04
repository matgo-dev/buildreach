"""MockDataSource — 直接从 credit_company_*_data 表读最新一条快照(信用评估 §3.1)。

未抓到数据时返回 data_source='missing' 的 stub,evaluator 会走"数据不可查"档位。
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    CreditCompanyBasicData,
    CreditCompanyCertification,
    CreditCompanyFinanceData,
    CreditCompanyLegalData,
)
from app.services.credit.data_source.base import DataSource
from app.services.credit.types import (
    BasicData,
    Certification,
    FinanceData,
    LegalData,
)


class MockDataSource(DataSource):
    """读 seed 数据;未来 T-2 真实数据源接入时这里换实现。"""

    async def fetch_basic_data(
        self, session: AsyncSession, company_id: int
    ) -> BasicData:
        stmt = (
            select(CreditCompanyBasicData)
            .where(CreditCompanyBasicData.company_id == company_id)
            .order_by(CreditCompanyBasicData.fetched_at.desc())
            .limit(1)
        )
        row = (await session.execute(stmt)).scalar_one_or_none()
        if row is None:
            return BasicData(company_id=company_id, data_source="missing")
        return BasicData.model_validate(row)

    async def fetch_finance_data(
        self, session: AsyncSession, company_id: int
    ) -> FinanceData:
        stmt = (
            select(CreditCompanyFinanceData)
            .where(CreditCompanyFinanceData.company_id == company_id)
            .order_by(CreditCompanyFinanceData.fetched_at.desc())
            .limit(1)
        )
        row = (await session.execute(stmt)).scalar_one_or_none()
        if row is None:
            return FinanceData(company_id=company_id, data_source="missing")
        return FinanceData.model_validate(row)

    async def fetch_legal_data(
        self, session: AsyncSession, company_id: int
    ) -> LegalData:
        stmt = (
            select(CreditCompanyLegalData)
            .where(CreditCompanyLegalData.company_id == company_id)
            .order_by(CreditCompanyLegalData.fetched_at.desc())
            .limit(1)
        )
        row = (await session.execute(stmt)).scalar_one_or_none()
        if row is None:
            return LegalData(company_id=company_id, data_source="missing")
        return LegalData.model_validate(row)

    async def fetch_certifications(
        self, session: AsyncSession, company_id: int
    ) -> list[Certification]:
        stmt = (
            select(CreditCompanyCertification)
            .where(CreditCompanyCertification.company_id == company_id)
            .order_by(CreditCompanyCertification.cert_type)
        )
        rows = (await session.execute(stmt)).scalars().all()
        return [Certification.model_validate(r) for r in rows]
