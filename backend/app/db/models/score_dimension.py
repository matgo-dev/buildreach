"""评分维度(信用评估 §二)。

4 个维度 = 基础工商(15) / 资质认证(25) / 财务健康(30) / 司法舆情(30)。
版本号 `version` 用于"规则集冻结":同一评分快照内 dimension/subitem/rule 必须 version 一致。
"""
from __future__ import annotations

from sqlalchemy import Boolean, Integer, SmallInteger, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampUpdateMixin


class DimensionCode:
    BASIC_INFO = "BASIC_INFO"        # 基础工商
    CERTIFICATION = "CERTIFICATION"  # 资质认证
    FINANCE = "FINANCE"              # 财务健康
    LEGAL = "LEGAL"                  # 司法舆情


class ScoreDimension(Base, TimestampUpdateMixin):
    __tablename__ = "score_dimension"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    max_score: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    display_order: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
