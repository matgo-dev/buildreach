"""评分明细(信用评估 §二)。

每快照固定写 12 条(对齐 12 个 subitem)。
冗余字段(dimension_code / subitem_code / hit_rule_description 等)用于
脱离 rule 表也能展示历史明细(规则可能被改 / 停用)。
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import Boolean, ForeignKey, Integer, SmallInteger, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class ScoreDetail(Base, TimestampMixin):
    __tablename__ = "score_detail"
    __table_args__ = (
        UniqueConstraint(
            "snapshot_id", "subitem_code", name="uq_score_detail_snapshot_subitem"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    snapshot_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("score_snapshot.id", name="fk_score_detail_snapshot"),
        nullable=False,
    )
    # 冗余 company_id,加速按 company 查所有快照明细
    company_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("credit_company.id", name="fk_score_detail_company"),
        nullable=False,
    )
    dimension_code: Mapped[str] = mapped_column(String(64), nullable=False)
    dimension_name: Mapped[str] = mapped_column(String(100), nullable=False)
    subitem_code: Mapped[str] = mapped_column(String(64), nullable=False)
    subitem_name: Mapped[str] = mapped_column(String(200), nullable=False)
    hit_rule_code: Mapped[str | None] = mapped_column(String(128), nullable=True)
    hit_rule_description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    score: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    max_score: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    is_default_score: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    evaluation_context: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
