"""商品品类属性（EAV 简化版）。

sku_id 为空 = 商品级公共属性（SPU 共用）。
sku_id 非空 = 该 SKU 的规格属性。
唯一性按维度判定:商品级(sku_id 空)内 attr_key 唯一;SKU 级(同一 sku_id)内 attr_key 唯一。
"""
from __future__ import annotations

from sqlalchemy import Boolean, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ProductAttr(Base):
    __tablename__ = "product_attrs"
    __table_args__ = (
        Index("ix_product_attrs_product_id", "product_id"),
        Index("ix_product_attrs_sku_id", "sku_id"),
        # 商品级:同 attr_key + attr_value 不可重复(允许同 key 多值)
        Index(
            "uq_product_attrs_product_key_val",
            "product_id", "attr_key", "attr_value",
            unique=True,
            postgresql_where="sku_id IS NULL",
        ),
        # SKU 级:同理
        Index(
            "uq_product_attrs_sku_key_val",
            "sku_id", "attr_key", "attr_value",
            unique=True,
            postgresql_where="sku_id IS NOT NULL",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("products.id", name="fk_product_attrs_product_id", ondelete="CASCADE"),
        nullable=False,
    )
    sku_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("product_skus.id", name="fk_product_attrs_sku_id", ondelete="CASCADE"),
        nullable=True,
    )
    attr_key: Mapped[str] = mapped_column(String(50), nullable=False)
    attr_value: Mapped[str] = mapped_column(String(200), nullable=False)
    attr_unit: Mapped[str | None] = mapped_column(String(20), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Phase 1 新增:导入用
    value_type: Mapped[str] = mapped_column(
        String(20), nullable=False, default="text", server_default="text",
    )
    attr_group: Mapped[str | None] = mapped_column(String(100), nullable=True)
    attr_key_zh: Mapped[str | None] = mapped_column(String(50), nullable=True)
    attr_value_zh: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # 该属性是否作为可选轴(如颜色、厚度),由爬数 offer.json 提供
    selectable: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false",
    )

    product: Mapped["Product"] = relationship("Product", back_populates="attrs")
