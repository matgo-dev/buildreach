"""报价行项（独立行项，松关联询价行）。

line_type 区分回应/替代/加项/服务/跳过。
软删除——被订单行项引用。
"""
from __future__ import annotations

from decimal import Decimal

from sqlalchemy import (
    Boolean, ForeignKey, Index, Integer, JSON, Numeric, String, Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampUpdateMixin
from app.db.soft_delete_mixin import SoftDeleteMixin
from app.constants.quote_line_type import QuoteLineType


class RfqQuoteItem(Base, TimestampUpdateMixin, SoftDeleteMixin):
    __tablename__ = "rfq_quote_items"
    __table_args__ = (
        Index("ix_rfq_quote_items_quote_id", "quote_id"),
        Index("ix_rfq_quote_items_source_rfq_item_id", "source_rfq_item_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    quote_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("rfq_quotes.id", name="fk_rfq_quote_items_quote_id"),
        nullable=False,
    )

    # 松关联询价行（可空 = 额外费用/服务等不关联询价行的报价行）
    source_rfq_item_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("rfq_items.id", name="fk_rfq_quote_items_rfq_item_id"),
        nullable=True,
    )

    # 行类型
    line_type: Mapped[str] = mapped_column(
        String(20), nullable=False, default=QuoteLineType.PRODUCT,
        server_default="PRODUCT",
    )

    # 商品快照（报价行自带，不依赖询价行读取）
    product_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("products.id", name="fk_rfq_quote_items_product_id"),
        nullable=True,
    )
    product_name_snapshot: Mapped[str | None] = mapped_column(String(200), nullable=True)
    quoted_variants: Mapped[list | None] = mapped_column(JSON, nullable=True)
    variant_display: Mapped[str | None] = mapped_column(String(500), nullable=True)
    quantity: Mapped[Decimal | None] = mapped_column(Numeric(18, 3), nullable=True)
    uom: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # 报价信息
    skipped: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)
    skip_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    unit_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    moq: Mapped[Decimal | None] = mapped_column(Numeric(18, 3), nullable=True)
    cbm_per_unit: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    gross_weight_per_unit: Mapped[Decimal | None] = mapped_column(Numeric(12, 3), nullable=True)
    lead_time_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    line_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)

    # relationships
    quote: Mapped["RfqQuote"] = relationship("RfqQuote", back_populates="items")
    source_rfq_item: Mapped["RfqItem | None"] = relationship(
        "RfqItem", back_populates="quote_items",
    )
    product: Mapped["Product | None"] = relationship("Product", lazy="select")
    tiers: Mapped[list["RfqQuoteItemTier"]] = relationship(
        "RfqQuoteItemTier", back_populates="quote_item",
        cascade="all, delete-orphan",
    )
    cost: Mapped["RfqQuoteItemCost | None"] = relationship(
        "RfqQuoteItemCost", back_populates="quote_item",
        uselist=False, cascade="all, delete-orphan",
    )
