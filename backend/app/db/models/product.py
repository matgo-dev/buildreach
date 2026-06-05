"""商品主表。

平台管控模型：运营上架商品，非供应商自主上架。
商品与供应商是 N:M 关系，通过 product_suppliers 中间表关联。

多语言约定：name/description/brand/origin 存运营填的原始值，
对应的 _i18n 字段存 JSON {"zh": "...", "en": "...", "sw": "..."}，
后端用 get_localized() 按请求 locale 自动选取。
"""
from __future__ import annotations

from sqlalchemy import (
    Boolean, DECIMAL, ForeignKey, Index, Integer, JSON, String, Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampUpdateMixin


class ProductStatus:
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    ALL = (DRAFT, ACTIVE, INACTIVE)


class Product(Base, TimestampUpdateMixin):
    __tablename__ = "products"
    __table_args__ = (
        Index("ix_products_category_code", "category_code"),
        Index("ix_products_status", "status"),
        Index("ix_products_is_featured", "is_featured"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    category_code: Mapped[str] = mapped_column(
        String(16),
        ForeignKey("categories.code", name="fk_products_category_code"),
        nullable=False,
    )
    sku_code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)

    # 多语言文本字段：原始值 + i18n JSON
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    name_i18n: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    description_i18n: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    brand: Mapped[str | None] = mapped_column(String(100), nullable=True)
    brand_i18n: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    origin: Mapped[str] = mapped_column(String(100), nullable=False, default="China")
    origin_i18n: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    price_min: Mapped[float] = mapped_column(DECIMAL(10, 2), nullable=False)
    price_max: Mapped[float] = mapped_column(DECIMAL(10, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    unit: Mapped[str] = mapped_column(String(20), nullable=False)
    moq: Mapped[int] = mapped_column(Integer, nullable=False)
    lead_time_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    hs_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    certifications: Mapped[dict | None] = mapped_column(JSON, default=list)
    is_featured: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=ProductStatus.DRAFT)
    created_by: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("users.id", name="fk_products_created_by"),
        nullable=True,
    )

    images: Mapped[list["ProductImage"]] = relationship(
        "ProductImage", back_populates="product", cascade="all, delete-orphan",
        order_by="ProductImage.sort_order",
    )
    attrs: Mapped[list["ProductAttr"]] = relationship(
        "ProductAttr", back_populates="product", cascade="all, delete-orphan",
    )
    supplier_relations: Mapped[list["ProductSupplier"]] = relationship(
        "ProductSupplier", back_populates="product", cascade="all, delete-orphan",
    )
