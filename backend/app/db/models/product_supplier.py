"""SKU-供应商供货关系（N:M）。

供货关系精确到 SKU（同款产品不同颜色可能由不同供应商供货）。
所有供应商相关字段对买方不可见（断层隔离）。
"""
from __future__ import annotations

from sqlalchemy import (
    Boolean, DECIMAL, ForeignKey, Index, Integer, String, Text, UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampUpdateMixin


class ProductSupplier(Base, TimestampUpdateMixin):
    __tablename__ = "product_suppliers"
    __table_args__ = (
        Index("ix_product_suppliers_sku_id", "sku_id"),
        Index("ix_product_suppliers_supplier_org_id", "supplier_org_id"),
        UniqueConstraint(
            "sku_id", "supplier_org_id",
            name="uq_product_suppliers_sku_supplier",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sku_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("product_skus.id", name="fk_product_suppliers_sku_id", ondelete="CASCADE"),
        nullable=False,
    )
    supplier_org_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("supplier_organizations.id", name="fk_product_suppliers_supplier_org_id"),
        nullable=False,
    )
    supplier_price: Mapped[float] = mapped_column(DECIMAL(12, 2), nullable=False)
    supplier_currency: Mapped[str] = mapped_column(String(3), nullable=False, default="CNY")
    cif_price_usd: Mapped[float | None] = mapped_column(DECIMAL(12, 2), nullable=True)
    supplier_moq: Mapped[int | None] = mapped_column(Integer, nullable=True)
    supplier_lead_time_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pvoc_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    has_coc: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_preferred: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    sku: Mapped["ProductSku"] = relationship("ProductSku", back_populates="supplier_relations")
