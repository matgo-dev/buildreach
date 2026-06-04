"""财务数据快照(信用评估 §二 · 维度3 数据源)。"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Index, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class RevenueTrend:
    GROWING = "growing"
    FLUCTUATING = "fluctuating"
    LOSS = "loss"
    UNKNOWN = "unknown"


class CashFlowStatus:
    POSITIVE = "positive"
    NEGATIVE_WITH_FUNDING = "negative_with_funding"
    PERSISTENT_NEGATIVE = "persistent_negative"
    UNKNOWN = "unknown"


class CreditCompanyFinanceData(Base, TimestampMixin):
    __tablename__ = "credit_company_finance_data"
    __table_args__ = (
        Index(
            "ix_credit_finance_company_fetched", "company_id", "fetched_at"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("credit_company.id", name="fk_credit_finance_company"),
        nullable=False,
    )
    revenue_trend: Mapped[str | None] = mapped_column(String(32), nullable=True)
    # 资产负债率(%),精度 5,小数 2
    debt_ratio: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    cash_flow_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    raw_data: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    data_source: Mapped[str] = mapped_column(String(20), nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    # Δ7:追溯抓取批次
    harvest_run_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("credit_data_harvest_run.id", name="fk_credit_finance_harvest_run"),
        nullable=True,
    )
