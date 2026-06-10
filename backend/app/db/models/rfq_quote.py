"""报价表头（独立实体）。

一个 RFQ 可有多版报价，但同时仅一个 ACTIVE。
部分唯一索引 (rfq_id) WHERE quote_status='ACTIVE' 保证单 ACTIVE。
软删除——被订单引用，需审计追溯。
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    DateTime, ForeignKey, Index, Integer, Numeric, String, Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampUpdateMixin
from app.db.soft_delete_mixin import SoftDeleteMixin


class RfqQuote(Base, TimestampUpdateMixin, SoftDeleteMixin):
    __tablename__ = "rfq_quotes"
    __table_args__ = (
        Index(
            "uq_rfq_quotes_rfq_active",
            "rfq_id",
            unique=True,
            postgresql_where="quote_status = 'ACTIVE'",
        ),
        Index(
            "uq_rfq_quotes_quote_no_active",
            "quote_no",
            unique=True,
            postgresql_where="deleted_at IS NULL",
        ),
        Index(
            "uq_rfq_quotes_rfq_version_active",
            "rfq_id", "version",
            unique=True,
            postgresql_where="deleted_at IS NULL",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    rfq_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("rfqs.id", name="fk_rfq_quotes_rfq_id"),
        nullable=False,
    )
    quote_no: Mapped[str] = mapped_column(String(40), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    quote_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="ACTIVE",
    )

    # 贸易条款
    trade_term: Mapped[str | None] = mapped_column(String(10), nullable=True)
    named_place: Mapped[str | None] = mapped_column(String(120), nullable=True)
    currency: Mapped[str | None] = mapped_column(
        String(3), nullable=True, default="USD",
    )
    valid_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    lead_time_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    eta_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(18, 4), nullable=True,
    )

    # 报价人
    quoted_by_user_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("users.id", name="fk_rfq_quotes_quoted_by_user_id"),
        nullable=True,
    )
    quoted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # relationships
    rfq: Mapped["Rfq"] = relationship(
        "Rfq",
        back_populates="quotes",
        foreign_keys=[rfq_id],
    )
    items: Mapped[list["RfqQuoteItem"]] = relationship(
        "RfqQuoteItem", back_populates="quote", cascade="all, delete-orphan",
    )
