"""商品品类属性（EAV 简化版）。"""
from __future__ import annotations

from sqlalchemy import ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ProductAttr(Base):
    __tablename__ = "product_attrs"
    __table_args__ = (
        Index("ix_product_attrs_product_id", "product_id"),
        UniqueConstraint("product_id", "attr_key", name="uq_product_attrs_product_key"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("products.id", name="fk_product_attrs_product_id", ondelete="CASCADE"),
        nullable=False,
    )
    attr_key: Mapped[str] = mapped_column(String(50), nullable=False)
    attr_value: Mapped[str] = mapped_column(String(200), nullable=False)
    attr_unit: Mapped[str | None] = mapped_column(String(20), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    product: Mapped["Product"] = relationship("Product", back_populates="attrs")
