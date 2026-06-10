"""报价行内部成本（运营内部，断层隔离）。

与买方可见的报价行/阶梯分离。
软删除——有供应商、成本等业务含义。
quote_item_id 唯一（1:1）。
"""
from __future__ import annotations

from decimal import Decimal

from sqlalchemy import ForeignKey, Index, Integer, Numeric, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampUpdateMixin
from app.db.soft_delete_mixin import SoftDeleteMixin


class RfqQuoteItemCost(Base, TimestampUpdateMixin, SoftDeleteMixin):
    __tablename__ = "rfq_quote_item_costs"
    __table_args__ = (
        Index(
            "uq_rfq_quote_item_costs_quote_item_active",
            "quote_item_id",
            unique=True,
            postgresql_where="deleted_at IS NULL",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    quote_item_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey(
            "rfq_quote_items.id",
            name="fk_rfq_quote_item_costs_quote_item_id",
        ),
        nullable=False,
    )
    supplier_org_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey(
            "supplier_organizations.id",
            name="fk_rfq_quote_item_costs_supplier_org_id",
        ),
        nullable=True,
    )

    # 成本明细
    supplier_unit_price: Mapped[Decimal | None] = mapped_column(
        Numeric(18, 4), nullable=True,
    )
    freight_cost_alloc: Mapped[Decimal | None] = mapped_column(
        Numeric(18, 4), nullable=True,
    )
    insurance_cost: Mapped[Decimal | None] = mapped_column(
        Numeric(18, 4), nullable=True,
    )
    export_clearance_cost: Mapped[Decimal | None] = mapped_column(
        Numeric(18, 4), nullable=True,
    )
    consolidation_cost: Mapped[Decimal | None] = mapped_column(
        Numeric(18, 4), nullable=True,
    )
    gross_margin: Mapped[Decimal | None] = mapped_column(
        Numeric(18, 4), nullable=True,
    )
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)

    # relationships
    quote_item: Mapped["RfqQuoteItem"] = relationship(
        "RfqQuoteItem", back_populates="cost",
    )
