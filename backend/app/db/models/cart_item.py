"""购物车行项。

硬删除——配置明细，无独立业务身份。
复合唯一 (cart_id, product_id)：同 SPU 数据库层防重复，
同 SPU 不同变体的多行由应用层按 selected_variants 指纹去重。
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any

from sqlalchemy import JSON, ForeignKey, Integer, Numeric, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampUpdateMixin


class CartItem(Base, TimestampUpdateMixin):
    __tablename__ = "cart_items"
    __table_args__ = (
        UniqueConstraint("cart_id", "product_id", name="uq_cart_items_cart_product"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    cart_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("carts.id", name="fk_cart_items_cart_id", ondelete="CASCADE"),
        nullable=False,
    )
    product_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("products.id", name="fk_cart_items_product_id"),
        nullable=False,
    )
    sku_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("product_skus.id", name="fk_cart_items_sku_id"),
        nullable=True,
    )
    selected_variants: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON, nullable=False, default=list, server_default="[]",
    )
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 3), nullable=False)
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)

    # relationships
    cart: Mapped["Cart"] = relationship("Cart", back_populates="items")
    product: Mapped["Product"] = relationship("Product", lazy="select")
    sku: Mapped["ProductSku | None"] = relationship("ProductSku", lazy="select")
