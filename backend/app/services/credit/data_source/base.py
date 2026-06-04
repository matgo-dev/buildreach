"""DataSource 抽象基类(信用评估 §3.1)。"""
from __future__ import annotations

from abc import ABC, abstractmethod

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.credit.types import (
    BasicData,
    Certification,
    FinanceData,
    LegalData,
)


class DataSource(ABC):
    """封装"如何获取某公司某类数据"。

    本期 MockDataSource 是唯一实现;未来按国别路由到不同数据源(企查查 / OpenCorporates 等)。
    """

    @abstractmethod
    async def fetch_basic_data(
        self, session: AsyncSession, company_id: int
    ) -> BasicData: ...

    @abstractmethod
    async def fetch_finance_data(
        self, session: AsyncSession, company_id: int
    ) -> FinanceData: ...

    @abstractmethod
    async def fetch_legal_data(
        self, session: AsyncSession, company_id: int
    ) -> LegalData: ...

    @abstractmethod
    async def fetch_certifications(
        self, session: AsyncSession, company_id: int
    ) -> list[Certification]: ...
