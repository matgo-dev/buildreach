"""信用评估搜索历史(信用评估 §二)。

每个用户最多查最近 5 条(同 company 去重),用于 /credit 页"近期搜索"。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class CreditSearchHistory(Base, TimestampMixin):
    __tablename__ = "credit_search_history"
    __table_args__ = (
        Index(
            "ix_credit_search_user_searched_at",
            "user_id",
            text("searched_at DESC"),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    company_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("credit_company.id", name="fk_credit_search_company"),
        nullable=False,
    )
    searched_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
