"""工商基础数据快照(信用评估 §二 · 维度1 数据源)。

只增不改:每次抓取写一条新快照。评分时读最新一条。
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import Date, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class DataSourceTag:
    """data_source 取值。"""
    MOCK = "mock"
    OFFICIAL = "official"
    API = "api"
    PUBLIC = "public"
    MEDIA = "media"
    MISSING = "missing"


class CreditCompanyBasicData(Base, TimestampMixin):
    __tablename__ = "credit_company_basic_data"
    __table_args__ = (
        Index(
            "ix_credit_basic_company_fetched", "company_id", "fetched_at"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("credit_company.id", name="fk_credit_basic_company"),
        nullable=False,
    )
    established_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    registered_capital: Mapped[str | None] = mapped_column(String(100), nullable=True)
    business_scope: Mapped[str | None] = mapped_column(Text, nullable=True)
    legal_representative: Mapped[str | None] = mapped_column(String(100), nullable=True)
    shareholders: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 存续状态:normal / abnormal / cancelled
    status_text: Mapped[str | None] = mapped_column(String(50), nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    website: Mapped[str | None] = mapped_column(String(300), nullable=True)
    data_source: Mapped[str] = mapped_column(String(20), nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    # Δ7:抓取留存的原始 LLM 应答 + 证据 + Tavily 结果;harvest_run_id 追溯抓取批次
    raw_data: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    harvest_run_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("credit_data_harvest_run.id", name="fk_credit_basic_harvest_run"),
        nullable=True,
    )
