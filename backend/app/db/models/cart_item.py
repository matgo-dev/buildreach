"""购物车行项。

硬删除——配置明细，无独立业务身份。
复合唯一 (cart_id, sku_id)：同 SKU 不重复加车，前端走数量累加。
"""
from __future__ import annotations

from decimal import Decimal

from sqlalchemy import ForeignKey, Integer, Numeric, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampUpdateMixin


class CartItem(Base, TimestampUpdateMixin):
    __tablename__ = "cart_items"
    __table_args__ = (
        UniqueConstraint("cart_id", "sku_id", name="uq_cart_items_cart_sku"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    cart_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("carts.id", name="fk_cart_items_cart_id", ondelete="CASCADE"),
        nullable=False,
    )
    sku_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("product_skus.id", name="fk_cart_items_sku_id"),
        nullable=False,
    )
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 3), nullable=False)
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)

    # relationships
    cart: Mapped["Cart"] = relationship("Cart", back_populates="items")
    sku: Mapped["ProductSku"] = relationship("ProductSku", lazy="select")
