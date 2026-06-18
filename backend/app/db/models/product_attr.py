"""商品品类属性（EAV 简化版）。

sku_id 为空 = 商品级公共属性（SPU 共用）。
sku_id 非空 = 该 SKU 的规格属性。
唯一性按维度判定:商品级(sku_id 空)内 attr_key_en 唯一;SKU 级(同一 sku_id)内 attr_key_en 唯一。

i18n:attr_key/attr_value 按 {field}_{locale} 命名,走 I18nMixin + i18n_registry 标准流程。
"""
from __future__ import annotations

from sqlalchemy import Boolean, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.i18n_mixin import I18nMixin


class ProductAttr(Base, I18nMixin):
    __tablename__ = "product_attrs"
    __table_args__ = (
        Index("ix_product_attrs_product_id", "product_id"),
        Index("ix_product_attrs_sku_id", "sku_id"),
        # 商品级:同 attr_key_en + attr_value_en 不可重复(允许同 key 多值)
        Index(
            "uq_product_attrs_product_key_val",
            "product_id", "attr_key_en", "attr_value_en",
            unique=True,
            postgresql_where="sku_id IS NULL",
        ),
        # SKU 级:同理
        Index(
            "uq_product_attrs_sku_key_val",
            "sku_id", "attr_key_en", "attr_value_en",
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

    # i18n 规范化：统一 {field}_{locale} 命名
    attr_key_en: Mapped[str] = mapped_column(String(50), nullable=False)
    attr_key_zh: Mapped[str | None] = mapped_column(String(50), nullable=True)
    attr_key_sw: Mapped[str | None] = mapped_column(String(50), nullable=True)

    attr_value_en: Mapped[str] = mapped_column(String(200), nullable=False)
    attr_value_zh: Mapped[str | None] = mapped_column(String(500), nullable=True)
    attr_value_sw: Mapped[str | None] = mapped_column(String(500), nullable=True)

    attr_unit: Mapped[str | None] = mapped_column(String(20), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Phase 1 新增:导入用
    value_type: Mapped[str] = mapped_column(
        String(20), nullable=False, default="text", server_default="text",
    )
    attr_group: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # 该属性是否作为可选轴(如颜色、厚度),由爬数 offer.json 提供
    selectable: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false",
    )
    # 色板图片路径(如 products/SPU001/swatch_01.jpg),直接挂属性值行
    swatch_image: Mapped[str | None] = mapped_column(String(500), nullable=True)

    product: Mapped["Product"] = relationship("Product", back_populates="attrs")
