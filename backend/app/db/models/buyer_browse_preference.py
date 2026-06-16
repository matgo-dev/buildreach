"""买方浏览偏好 — user 维度 1:1 单行。

注册时用经营品类初始化,买方可自助调整,持久化。
与经营品类(org 级)解耦,互不回写。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, _utcnow


class BuyerBrowsePreference(Base):
    __tablename__ = "buyer_browse_preferences"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    # 浏览品类:一级品类 code 数组,全量替换
    category_codes: Mapped[list] = mapped_column(
        JSONB, nullable=False, server_default="[]"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=_utcnow, onupdate=_utcnow
    )
