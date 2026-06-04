"""评分子项(信用评估 §二)。

12 个子项 = 4 维度 × 3 子项。`default_score` 在无规则命中时回落。
"""
from __future__ import annotations

from sqlalchemy import Boolean, ForeignKey, Index, Integer, SmallInteger, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampUpdateMixin


class ScoreSubitem(Base, TimestampUpdateMixin):
    __tablename__ = "score_subitem"
    __table_args__ = (
        Index(
            "ix_score_subitem_dimension_active",
            "dimension_id",
            "is_active",
            "display_order",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dimension_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("score_dimension.id", name="fk_score_subitem_dimension"),
        nullable=False,
    )
    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    max_score: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    default_score: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    display_order: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    data_source_hint: Mapped[str | None] = mapped_column(String(200), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
