"""报价行阶梯价。

硬删除——配置明细，编辑时全量替换。
复合唯一 (quote_item_id, min_qty)。
"""
from __future__ import annotations

from decimal import Decimal

from sqlalchemy import ForeignKey, Integer, Numeric, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class RfqQuoteItemTier(Base, TimestampMixin):
    __tablename__ = "rfq_quote_item_tiers"
    __table_args__ = (
        UniqueConstraint(
            "quote_item_id", "min_qty",
            name="uq_rfq_quote_item_tiers_item_qty",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    quote_item_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey(
            "rfq_quote_items.id",
            name="fk_rfq_quote_item_tiers_quote_item_id",
        ),
        nullable=False,
    )
    min_qty: Mapped[Decimal] = mapped_column(Numeric(18, 3), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)

    # relationships
    quote_item: Mapped["RfqQuoteItem"] = relationship(
        "RfqQuoteItem", back_populates="tiers",
    )
