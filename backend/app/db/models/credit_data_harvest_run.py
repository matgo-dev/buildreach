"""数据抓取审计表(Δ7 §4.7)。

抓取过程审计:一条记录 = 一次抓取任务。
与 audit_logs(操作审计:谁做了什么)、score_audit_log(评分变动审计:分数为什么变)
分工互补,本表回答"数据从哪来"。
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampUpdateMixin


class HarvestRunStatus:
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    PARTIAL_SUCCEEDED = "partial_succeeded"
    FAILED = "failed"
    CACHED_HIT = "cached_hit"


class HarvestTriggeredBy:
    """本工单仅两种触发源;后续 T+1/规则更新工单扩枚举不改表。"""
    SUPPLIER_REGISTER = "supplier_register"
    MANUAL = "manual"


class CreditDataHarvestRun(Base, TimestampUpdateMixin):
    __tablename__ = "credit_data_harvest_run"
    __table_args__ = (
        Index("ix_harvest_run_company_started", "company_id", text("started_at DESC")),
        Index("ix_harvest_run_status_started", "status", text("started_at DESC")),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("credit_company.id", name="fk_harvest_run_company"),
        nullable=False,
    )
    # pending / running / succeeded / partial_succeeded / failed / cached_hit
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    # supplier_register / manual
    triggered_by: Mapped[str] = mapped_column(String(50), nullable=False)
    operator_user_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("users.id", name="fk_harvest_run_operator"),
        nullable=True,
    )
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # {basic: succeeded, finance: missing, legal: succeeded, qualification: missing}
    dimensions_status: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    # cached_hit 状态时引用的源 run
    cache_source_run_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("credit_data_harvest_run.id", name="fk_harvest_run_cache_source"),
        nullable=True,
    )
    error_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    tavily_calls: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    llm_calls: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
