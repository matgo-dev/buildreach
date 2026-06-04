"""司法舆情数据快照(信用评估 §二 · 维度4 数据源)。

注意"失信被执行未结案"是一票否决:维度4 直接判 0 分(由 evaluator 实现)。
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Index, Integer, SmallInteger, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class NegativeNewsLevel:
    NONE = "none"
    OCCASIONAL = "occasional"
    PERSISTENT = "persistent"
    MAJOR_SCANDAL = "major_scandal"
    UNKNOWN = "unknown"


class CreditCompanyLegalData(Base, TimestampMixin):
    __tablename__ = "credit_company_legal_data"
    __table_args__ = (
        Index(
            "ix_credit_legal_company_fetched", "company_id", "fetched_at"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("credit_company.id", name="fk_credit_legal_company"),
        nullable=False,
    )
    litigation_count: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    defaulter_unresolved_count: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, default=0
    )
    defaulter_resolved_count: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, default=0
    )
    negative_news_level: Mapped[str | None] = mapped_column(String(20), nullable=True)
    raw_data: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    data_source: Mapped[str] = mapped_column(String(20), nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    # Δ7:追溯抓取批次
    harvest_run_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("credit_data_harvest_run.id", name="fk_credit_legal_harvest_run"),
        nullable=True,
    )
