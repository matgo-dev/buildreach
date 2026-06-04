"""维度级 override 规则(信用评估技术方案 v0.2 重构)。

把 PRD §4.3 三条"维度级强制规则"独立建模,跟子项级 score_rule 解耦:
- 维度2:关键证书伪造/过期 → 维度强制清零
- 维度3:整维度数据缺失 → 维度满分 40%(12 分)
- 维度4:失信被执行未结案 → 维度直接判 0(一票否决)

ScoringEngine.compute 在子项自然评分完后,对每维度跑该表里的 override evaluator,
首条命中即停;命中后维度最终分被覆盖,但 score_detail 保留自然命中规则,可解释。

evaluator_key 映射到 evaluators.py 的 DIMENSION_OVERRIDE_EVALUATORS 字典。
"""
from __future__ import annotations

from sqlalchemy import Boolean, ForeignKey, Index, Integer, SmallInteger, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampUpdateMixin


class ScoreDimensionOverride(Base, TimestampUpdateMixin):
    __tablename__ = "score_dimension_override"
    __table_args__ = (
        Index(
            "ix_score_dim_override_dim_active_priority",
            "dimension_id",
            "is_active",
            "priority",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dimension_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("score_dimension.id", name="fk_score_dim_override_dimension"),
        nullable=False,
    )
    code: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    override_score: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    evaluator_key: Mapped[str] = mapped_column(String(100), nullable=False)
    priority: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
