"""评分规则(信用评估 §二)。

~35 条规则。`evaluator_key` 映射到 `app/services/credit/evaluators.py` 的求值函数。
同 subitem 内按 priority 升序求值,首条命中即停;全部未命中走 subitem.default_score。

condition_expr:T-3 规则配置化时启用 DSL,本期留空。
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import Boolean, ForeignKey, Index, Integer, SmallInteger, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampUpdateMixin


class ScoreRule(Base, TimestampUpdateMixin):
    __tablename__ = "score_rule"
    __table_args__ = (
        Index(
            "ix_score_rule_subitem_active_priority",
            "subitem_id",
            "is_active",
            "priority",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    subitem_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("score_subitem.id", name="fk_score_rule_subitem"),
        nullable=False,
    )
    code: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    score: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    evaluator_key: Mapped[str] = mapped_column(String(100), nullable=False)
    # TODO(T-3): 规则配置化时启用,本期留空
    condition_expr: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    priority: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
