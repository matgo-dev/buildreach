"""SKU 阶梯价。

按采购量分档定价，阶梯价的应用层规则（首档=moq、连续、逐档递减）
在 API 分支实现，本模型只建表与唯一约束。
"""
from __future__ import annotations

from sqlalchemy import DECIMAL, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin
from app.db.soft_delete_mixin import SoftDeleteMixin


class SkuPriceTier(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "sku_price_tiers"
    __table_args__ = (
        Index("ix_sku_price_tiers_sku_id", "sku_id"),
        Index(
            "uq_sku_price_tiers_sku_qty_active",
            "sku_id", "min_qty",
            unique=True,
            postgresql_where="deleted_at IS NULL",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sku_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("product_skus.id", name="fk_sku_price_tiers_sku_id", ondelete="CASCADE"),
        nullable=False,
    )
    min_qty: Mapped[int] = mapped_column(Integer, nullable=False)
    max_qty: Mapped[int | None] = mapped_column(Integer, nullable=True)
    unit_price: Mapped[float] = mapped_column(DECIMAL(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="TZS")
    label: Mapped[str | None] = mapped_column(String(50), nullable=True)

    sku: Mapped["ProductSku"] = relationship("ProductSku", back_populates="price_tiers")
