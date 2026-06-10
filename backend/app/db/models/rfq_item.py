"""询价行项（需求行）。

快照字段为冻结副本（提交时拍照），不挂 I18nMixin。
软删除——被订单行项引用。
复合唯一 (rfq_id, sku_id)。
"""
from __future__ import annotations

from decimal import Decimal

from sqlalchemy import (
    ForeignKey, Index, Integer, Numeric, String, Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampUpdateMixin
from app.db.soft_delete_mixin import SoftDeleteMixin


class RfqItem(Base, TimestampUpdateMixin, SoftDeleteMixin):
    __tablename__ = "rfq_items"
    __table_args__ = (
        Index(
            "uq_rfq_items_rfq_sku_active",
            "rfq_id", "sku_id",
            unique=True,
            postgresql_where="deleted_at IS NULL",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    rfq_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("rfqs.id", name="fk_rfq_items_rfq_id"),
        nullable=False,
    )
    sku_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("product_skus.id", name="fk_rfq_items_sku_id"),
        nullable=False,
    )

    # 提交时快照（冻结副本，不走 I18nMixin / trans_meta）
    product_name_snapshot_zh: Mapped[str | None] = mapped_column(
        String(200), nullable=True,
    )
    product_name_snapshot_en: Mapped[str | None] = mapped_column(
        String(200), nullable=True,
    )
    sku_spec_snapshot_zh: Mapped[str | None] = mapped_column(
        String(200), nullable=True,
    )
    sku_spec_snapshot_en: Mapped[str | None] = mapped_column(
        String(200), nullable=True,
    )
    uom_snapshot: Mapped[str | None] = mapped_column(
        String(20), nullable=True,
    )

    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 3), nullable=False)
    target_unit_price: Mapped[Decimal | None] = mapped_column(
        Numeric(18, 4), nullable=True,
    )
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)

    # relationships
    rfq: Mapped["Rfq"] = relationship("Rfq", back_populates="items")
    quote_items: Mapped[list["RfqQuoteItem"]] = relationship(
        "RfqQuoteItem", back_populates="rfq_item",
    )
