"""商品-供应商供货关系（N:M）。

一个 SKU 可由多家供应商供货，运营在上架时绑定。
所有供应商相关字段对买方不可见（断层隔离）。
"""
from __future__ import annotations

from sqlalchemy import (
    Boolean, DECIMAL, ForeignKey, Index, Integer, Text, UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampUpdateMixin


class ProductSupplier(Base, TimestampUpdateMixin):
    __tablename__ = "product_suppliers"
    __table_args__ = (
        Index("ix_product_suppliers_product_id", "product_id"),
        Index("ix_product_suppliers_supplier_org_id", "supplier_org_id"),
        UniqueConstraint(
            "product_id", "supplier_org_id",
            name="uq_product_suppliers_product_supplier",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("products.id", name="fk_product_suppliers_product_id", ondelete="CASCADE"),
        nullable=False,
    )
    supplier_org_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("supplier_organizations.id", name="fk_product_suppliers_supplier_org_id"),
        nullable=False,
    )
    supplier_price: Mapped[float] = mapped_column(DECIMAL(10, 2), nullable=False)
    supplier_moq: Mapped[int | None] = mapped_column(Integer, nullable=True)
    supplier_lead_time_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    has_pvoc: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    has_coc: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_preferred: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    product: Mapped["Product"] = relationship("Product", back_populates="supplier_relations")
