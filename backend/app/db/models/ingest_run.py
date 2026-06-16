"""商品导入批次运行记录。

每次执行导入脚本产生一条 IngestRun,记录批次元信息和运行结果。
状态机:RUNNING → SUCCESS / PARTIAL / FAILED
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampUpdateMixin


class IngestRunStatus:
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    PARTIAL = "PARTIAL"     # 部分 offer 失败
    FAILED = "FAILED"
    ALL = (RUNNING, SUCCESS, PARTIAL, FAILED)


class IngestRun(Base, TimestampUpdateMixin):
    __tablename__ = "ingest_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # 批次唯一标识,格式如 "alibaba_2026-06-10_batch01"
    run_key: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    operator: Mapped[str | None] = mapped_column(String(100), nullable=True)
    crawled_at: Mapped["datetime | None"] = mapped_column(DateTime, nullable=True)
    imported_at: Mapped["datetime | None"] = mapped_column(DateTime, nullable=True)
    product_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=IngestRunStatus.RUNNING,
    )
    raw_path: Mapped[str] = mapped_column(String(500), nullable=False)
    # 失败 offer 摘要:[{offer_id, error}]
    error_summary: Mapped[list | None] = mapped_column(JSON, nullable=True)
