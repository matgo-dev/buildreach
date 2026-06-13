"""SKU 变体表。

每个 SPU 下可有多个 SKU，以颜色/材质/型号区分。
is_default=TRUE 的 SKU 用于列表页展示价格和主图。
price_min/max 为 TZS 展示价，可空（运营后补录）。

多语言:v2 分列模式(name_zh / name_en),继承 I18nMixin 获得 source_lang + trans_meta。
"""
from __future__ import annotations

from sqlalchemy import (
    Boolean, DECIMAL, ForeignKey, Index, Integer, String,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampUpdateMixin
from app.db.i18n_mixin import I18nMixin
from app.db.soft_delete_mixin import SoftDeleteMixin


class SkuStatus:
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    ALL = (ACTIVE, INACTIVE)


class ProductSku(Base, TimestampUpdateMixin, I18nMixin, SoftDeleteMixin):
    __tablename__ = "product_skus"
    __table_args__ = (
        Index("ix_product_skus_product_id", "product_id"),
        Index("ix_product_skus_status", "status"),
        # 部分唯一索引：每个 SPU 下最多 1 个未删除默认 SKU
        Index(
            "ix_product_skus_default",
            "product_id",
            unique=True,
            postgresql_where="is_default AND deleted_at IS NULL",
        ),
        Index(
            "uq_product_skus_sku_code_active",
            "sku_code",
            unique=True,
            postgresql_where="deleted_at IS NULL",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("products.id", name="fk_product_skus_product_id", ondelete="CASCADE"),
        nullable=False,
    )
    sku_code: Mapped[str] = mapped_column(String(50), nullable=False)
    manufacturer_model: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # 多语言分列
    name_zh: Mapped[str | None] = mapped_column(String(200), nullable=True)
    name_en: Mapped[str | None] = mapped_column(String(200), nullable=True)
    color_zh: Mapped[str | None] = mapped_column(String(50), nullable=True)
    color_en: Mapped[str | None] = mapped_column(String(50), nullable=True)
    material_zh: Mapped[str | None] = mapped_column(String(100), nullable=True)
    material_en: Mapped[str | None] = mapped_column(String(100), nullable=True)
    name_sw: Mapped[str | None] = mapped_column(String(200), nullable=True)
    color_sw: Mapped[str | None] = mapped_column(String(50), nullable=True)
    material_sw: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # 定价（展示价，可空——运营后补录；币种和单位在 SPU 级）
    price_min: Mapped[float | None] = mapped_column(DECIMAL(12, 2), nullable=True)
    price_max: Mapped[float | None] = mapped_column(DECIMAL(12, 2), nullable=True)
    moq: Mapped[int] = mapped_column(Integer, nullable=False)

    # 交期
    lead_time_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    lead_time_max: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # 物流参数
    packing_quantity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    gross_weight_kg: Mapped[float | None] = mapped_column(DECIMAL(8, 2), nullable=True)
    volume_cbm: Mapped[float | None] = mapped_column(DECIMAL(8, 4), nullable=True)
    can_consolidate: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    cargo_type: Mapped[str | None] = mapped_column(String(20), nullable=True)

    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=SkuStatus.ACTIVE)

    # relationships
    product: Mapped["Product"] = relationship("Product", back_populates="skus")
    price_tiers: Mapped[list["SkuPriceTier"]] = relationship(
        "SkuPriceTier", back_populates="sku", cascade="all, delete-orphan",
        order_by="SkuPriceTier.min_qty",
    )
    images: Mapped[list["ProductImage"]] = relationship(
        "ProductImage", back_populates="sku",
    )
    supplier_relations: Mapped[list["ProductSupplier"]] = relationship(
        "ProductSupplier", back_populates="sku", cascade="all, delete-orphan",
    )
