"""询价行项（需求行）。

快照字段为冻结副本（提交时拍照），不挂 I18nMixin。
variant_snapshot 统一存英文（attr_key_en + attr_value_en），展示时按 locale 动态翻译。
软删除——被订单行项引用。
"""
from __future__ import annotations

from decimal import Decimal

from sqlalchemy import (
    ForeignKey, Index, Integer, JSON, Numeric, String, Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampUpdateMixin
from app.db.soft_delete_mixin import SoftDeleteMixin


class RfqItem(Base, TimestampUpdateMixin, SoftDeleteMixin):
    __tablename__ = "rfq_items"
    __table_args__ = (
        Index("ix_rfq_items_rfq_product", "rfq_id", "product_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    rfq_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("rfqs.id", name="fk_rfq_items_rfq_id"),
        nullable=False,
    )
    product_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("products.id", name="fk_rfq_items_product_id"),
        nullable=False,
    )
    sku_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("product_skus.id", name="fk_rfq_items_sku_id"),
        nullable=True,
    )

    # 结构化变体快照（统一存英文 attr_key_en + attr_value_en）
    # 示例: [{"attr_name": "material_type", "value": "normal_white_with_film"}]
    # 展示时按 product_id + attr_name 反查 product_attrs 取当前 locale 翻译
    # 查不到用原始英文值 fallback
    variant_snapshot: Mapped[list] = mapped_column(
        JSON, nullable=False, default=list, server_default="[]",
    )

    # 提交时快照（冻结副本）
    product_name_snapshot_zh: Mapped[str | None] = mapped_column(
        String(200), nullable=True,
    )
    product_name_snapshot_en: Mapped[str | None] = mapped_column(
        String(200), nullable=True,
    )
    # 旧列（从 sku_spec_snapshot_zh/en 改名），仅兼容历史数据，新数据不写入
    variant_snapshot_zh: Mapped[str | None] = mapped_column(
        String(200), nullable=True,
    )
    variant_snapshot_en: Mapped[str | None] = mapped_column(
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
    product: Mapped["Product"] = relationship("Product")
    quote_items: Mapped[list["RfqQuoteItem"]] = relationship(
        "RfqQuoteItem", back_populates="rfq_item",
    )
