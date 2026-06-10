"""报价行项。

挂报价表头，关联需求行。
复合唯一 (quote_id, rfq_item_id)。
软删除——被订单行项引用。
"""
from __future__ import annotations

from decimal import Decimal

from sqlalchemy import (
    ForeignKey, Integer, Numeric, Text, UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampUpdateMixin
from app.db.soft_delete_mixin import SoftDeleteMixin


class RfqQuoteItem(Base, TimestampUpdateMixin, SoftDeleteMixin):
    __tablename__ = "rfq_quote_items"
    __table_args__ = (
        UniqueConstraint(
            "quote_id", "rfq_item_id",
            name="uq_rfq_quote_items_quote_rfq_item",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    quote_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("rfq_quotes.id", name="fk_rfq_quote_items_quote_id"),
        nullable=False,
    )
    rfq_item_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("rfq_items.id", name="fk_rfq_quote_items_rfq_item_id"),
        nullable=False,
    )

    unit_price: Mapped[Decimal | None] = mapped_column(
        Numeric(18, 4), nullable=True,
    )
    moq: Mapped[Decimal | None] = mapped_column(Numeric(18, 3), nullable=True)
    cbm_per_unit: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 4), nullable=True,
    )
    gross_weight_per_unit: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 3), nullable=True,
    )
    lead_time_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    line_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(18, 4), nullable=True,
    )
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)

    # relationships
    quote: Mapped["RfqQuote"] = relationship("RfqQuote", back_populates="items")
    rfq_item: Mapped["RfqItem"] = relationship("RfqItem", back_populates="quote_items")
    tiers: Mapped[list["RfqQuoteItemTier"]] = relationship(
        "RfqQuoteItemTier", back_populates="quote_item",
        cascade="all, delete-orphan",
    )
    cost: Mapped["RfqQuoteItemCost | None"] = relationship(
        "RfqQuoteItemCost", back_populates="quote_item",
        uselist=False, cascade="all, delete-orphan",
    )
