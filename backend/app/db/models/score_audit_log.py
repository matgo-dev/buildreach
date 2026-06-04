"""评分变动审计(信用评估 §二)。

仅在评分变化时写。与平台 audit_logs 并存:
- audit_logs:谁做了什么(操作维度)
- score_audit_log:分数为什么变(数据维度)
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import Boolean, ForeignKey, Index, Integer, SmallInteger, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class ScoreAuditLog(Base, TimestampMixin):
    __tablename__ = "score_audit_log"
    __table_args__ = (
        Index(
            "ix_score_audit_company_created",
            "company_id",
            text("created_at DESC"),
        ),
        Index(
            "ix_score_audit_grade_changed", "grade_changed", "created_at"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("credit_company.id", name="fk_score_audit_company"),
        nullable=False,
    )
    previous_snapshot_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("score_snapshot.id", name="fk_score_audit_prev_snapshot"),
        nullable=True,
    )
    current_snapshot_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("score_snapshot.id", name="fk_score_audit_curr_snapshot"),
        nullable=False,
    )
    previous_total_score: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    current_total_score: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    score_delta: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    previous_grade: Mapped[str | None] = mapped_column(String(1), nullable=True)
    current_grade: Mapped[str] = mapped_column(String(1), nullable=False)
    grade_changed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    # 变化子项数组:[{"subitem_code":"...", "previous_score":..., "current_score":...}, ...]
    changed_subitems: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    trigger_type: Mapped[str] = mapped_column(String(32), nullable=False)
