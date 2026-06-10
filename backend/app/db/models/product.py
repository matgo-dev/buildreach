"""商品 SPU 主表。

SPU(Standard Product Unit) = 一款产品，共享描述/品牌/品类/卖点。
SKU 变体(颜色/材质/型号)在 product_skus 表。
供货关系挂在 SKU 上（product_suppliers.sku_id）。

多语言:v2 分列模式(name_zh / name_en),继承 I18nMixin 获得 source_lang + trans_meta。
写入经 i18n_write,读出经 get_localized。
"""
from __future__ import annotations

from sqlalchemy import (
    JSON, Boolean, ForeignKey, Index, Integer, String, Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampUpdateMixin
from app.db.i18n_mixin import I18nMixin
from app.db.soft_delete_mixin import SoftDeleteMixin


class ProductStatus:
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    ALL = (DRAFT, ACTIVE, INACTIVE)

    # 状态机：合法转换路径
    TRANSITIONS: dict[str, tuple[str, ...]] = {
        DRAFT: (ACTIVE,),           # 草稿 → 上架
        ACTIVE: (INACTIVE,),        # 已上架 → 下架
        INACTIVE: (ACTIVE,),        # 已下架 → 重新上架
    }

    # 可编辑的状态（ACTIVE 不可编辑，需先下架）
    EDITABLE = (DRAFT, INACTIVE)

    # 可删除的状态
    DELETABLE = (DRAFT, INACTIVE)

    @classmethod
    def can_transition(cls, current: str, target: str) -> bool:
        return target in cls.TRANSITIONS.get(current, ())


class Product(Base, TimestampUpdateMixin, I18nMixin, SoftDeleteMixin):
    __tablename__ = "products"
    __table_args__ = (
        Index("ix_products_category_code", "category_code"),
        Index("ix_products_status", "status"),
        Index("ix_products_is_featured", "is_featured"),
        Index(
            "uq_products_spu_code_active",
            "spu_code",
            unique=True,
            postgresql_where="deleted_at IS NULL",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    category_code: Mapped[str] = mapped_column(
        String(16),
        ForeignKey("categories.code", name="fk_products_category_code"),
        nullable=False,
    )
    spu_code: Mapped[str] = mapped_column(String(50), nullable=False)

    # 多语言分列
    name_zh: Mapped[str] = mapped_column(String(200), nullable=False)
    name_en: Mapped[str | None] = mapped_column(String(200), nullable=True)
    description_zh: Mapped[str | None] = mapped_column(Text, nullable=True)
    description_en: Mapped[str | None] = mapped_column(Text, nullable=True)
    brand_zh: Mapped[str | None] = mapped_column(String(100), nullable=True)
    brand_en: Mapped[str | None] = mapped_column(String(100), nullable=True)
    origin_zh: Mapped[str] = mapped_column(String(100), nullable=False, default="中国")
    origin_en: Mapped[str | None] = mapped_column(String(100), nullable=True, default="China")
    selling_points_zh: Mapped[str | None] = mapped_column(Text, nullable=True)
    selling_points_en: Mapped[str | None] = mapped_column(Text, nullable=True)

    hs_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    certifications: Mapped[list | None] = mapped_column(JSON, default=list)

    # 计量单位 & 币种（SPU 级，所有 SKU 共享）
    unit: Mapped[str] = mapped_column(String(20), nullable=False, default="PCS")
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="TZS")

    is_featured: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=ProductStatus.DRAFT)
    created_by: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("users.id", name="fk_products_created_by"),
        nullable=True,
    )

    # relationships
    skus: Mapped[list["ProductSku"]] = relationship(
        "ProductSku", back_populates="product", cascade="all, delete-orphan",
    )
    images: Mapped[list["ProductImage"]] = relationship(
        "ProductImage", back_populates="product", cascade="all, delete-orphan",
        order_by="ProductImage.sort_order",
    )
    attrs: Mapped[list["ProductAttr"]] = relationship(
        "ProductAttr", back_populates="product", cascade="all, delete-orphan",
    )
