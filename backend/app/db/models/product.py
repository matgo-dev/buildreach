"""商品 SPU 主表。

SPU(Standard Product Unit) = 一款产品，共享描述/品牌/品类/卖点。
SKU 变体(颜色/材质/型号)在 product_skus 表。
供货关系挂在 SKU 上（product_suppliers.sku_id）。

多语言:v2 分列模式(name_zh / name_en),继承 I18nMixin 获得 source_lang + trans_meta。
写入经 i18n_write,读出经 get_localized。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    DDL, JSON, Boolean, Computed, DECIMAL, DateTime, ForeignKey, Index, Integer, String, Text,
    event, text,
)
from sqlalchemy.dialects.postgresql import ARRAY, TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column, relationship

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from app.db.models.ingest_run import IngestRun

from app.db.base import Base, TimestampUpdateMixin
from app.db.i18n_mixin import I18nMixin
from app.db.soft_delete_mixin import SoftDeleteMixin


class SupplyMode:
    """履约模式：平台集采 vs 供应商直发。"""
    PLATFORM_STOCK = "PLATFORM_STOCK"    # 平台集采（自营备货）
    SUPPLIER_DIRECT = "SUPPLIER_DIRECT"  # 供应商直发
    ALL = (PLATFORM_STOCK, SUPPLIER_DIRECT)


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


class ProductVisibility:
    PUBLIC = "PUBLIC"
    ZONE_ONLY = "ZONE_ONLY"
    ALL = (PUBLIC, ZONE_ONLY)


# 关键词检索派生列(services/product_search.py)。改表达式须同步写迁移重建列。
# zh_ngrams:中文单字 + 双字 n-gram,让 1~2 字中文词也能走 GIN 索引(pg_trgm 需 ≥3 字符)。
ZH_NGRAMS_FUNCTION_SQL = """
CREATE OR REPLACE FUNCTION zh_ngrams(t text) RETURNS text[]
LANGUAGE sql IMMUTABLE PARALLEL SAFE AS $$
  SELECT coalesce(array_agg(DISTINCT g), '{}') FROM (
    SELECT substr(t, i, 1) AS g FROM generate_series(1, length(t)) AS i
    UNION ALL
    SELECT substr(t, i, 2) FROM generate_series(1, length(t) - 1) AS i
  ) s
  -- 按码点判断 CJK 统一汉字 U+4E00..U+9FFF(与 product_search._CJK_RE 一致),不依赖库 locale
  WHERE ascii(substr(g, 1, 1)) BETWEEN 19968 AND 40959
    AND (length(g) = 1 OR ascii(substr(g, 2, 1)) BETWEEN 19968 AND 40959)
$$
"""
SEARCH_TSV_EXPR = (
    "setweight(to_tsvector('english'::regconfig, coalesce(name_en, '')), 'A') || "
    "setweight(to_tsvector('simple'::regconfig, coalesce(name_sw, '')), 'A') || "
    "setweight(to_tsvector('english'::regconfig, coalesce(brand_en, '')), 'B') || "
    "setweight(to_tsvector('simple'::regconfig, coalesce(manufacturer_model, '')), 'C')"
)
SEARCH_ZH_EXPR = "zh_ngrams(coalesce(name_zh, '')) || zh_ngrams(coalesce(brand_zh, ''))"


class Product(Base, TimestampUpdateMixin, I18nMixin, SoftDeleteMixin):
    __tablename__ = "products"
    __table_args__ = (
        Index("ix_products_category_code", "category_code"),
        Index("ix_products_status", "status"),
        Index("ix_products_is_featured", "is_featured"),
        Index("ix_products_supply_mode", "supply_mode"),
        Index(
            "uq_products_spu_code_active",
            "spu_code",
            unique=True,
            postgresql_where="deleted_at IS NULL",
        ),
        Index(
            "ix_products_search_tsv", "search_tsv",
            postgresql_using="gin", postgresql_where=text("deleted_at IS NULL"),
        ),
        Index(
            "ix_products_search_zh", "search_zh",
            postgresql_using="gin", postgresql_where=text("deleted_at IS NULL"),
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
    name_sw: Mapped[str | None] = mapped_column(String(200), nullable=True)
    description_sw: Mapped[str | None] = mapped_column(Text, nullable=True)
    brand_sw: Mapped[str | None] = mapped_column(String(100), nullable=True)
    origin_sw: Mapped[str | None] = mapped_column(String(100), nullable=True)
    selling_points_sw: Mapped[str | None] = mapped_column(Text, nullable=True)

    # 详情区长文产品介绍(与短描述 description 区分)
    detail_description_zh: Mapped[str | None] = mapped_column(Text, nullable=True)
    detail_description_en: Mapped[str | None] = mapped_column(Text, nullable=True)
    detail_description_sw: Mapped[str | None] = mapped_column(Text, nullable=True)

    # 厂家型号（SPU 级，如 GBM 13 RE）
    manufacturer_model: Mapped[str | None] = mapped_column(String(100), nullable=True)

    hs_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    certifications: Mapped[list | None] = mapped_column(JSON, default=list)

    # 计量单位 & 币种（SPU 级，所有 SKU 共享）
    unit: Mapped[str] = mapped_column(String(20), nullable=False, default="PCS")
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="TZS")

    # 最低起订量(SPU 级,抓数导入或运营手填)
    moq: Mapped[int | None] = mapped_column(Integer, nullable=True)
    moq_unit: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # 交期（天）
    lead_time_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    lead_time_max: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # 物流参数（单件维度，拼柜时 × 数量）
    packing_quantity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    gross_weight_kg: Mapped[float | None] = mapped_column(DECIMAL(8, 2), nullable=True)
    volume_cbm: Mapped[float | None] = mapped_column(DECIMAL(8, 4), nullable=True)
    can_consolidate: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true",
    )
    cargo_type: Mapped[str | None] = mapped_column(String(20), nullable=True)

    is_featured: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    supply_mode: Mapped[str] = mapped_column(
        String(30), nullable=False, default=SupplyMode.SUPPLIER_DIRECT,
        server_default=SupplyMode.SUPPLIER_DIRECT,
    )
    visibility: Mapped[str] = mapped_column(String(16), nullable=False, default=ProductVisibility.PUBLIC, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=ProductStatus.DRAFT)
    # 上架时间：ACTIVE 时写入，下架时清空，重新上架时更新
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    created_by: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("users.id", name="fk_products_created_by"),
        nullable=True,
    )

    # 阿里阶梯参考价（SPU 级，运营参考用，不展示给买方）
    ref_price_tiers: Mapped[list | None] = mapped_column(JSON, nullable=True)

    # 商品视频（抓数导入或运营手填）
    video_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # 商品来源:MANUAL(运营手动) / alibaba / 1688 等爬虫源
    source: Mapped[str] = mapped_column(
        String(50), nullable=False, default="MANUAL", server_default="MANUAL",
    )
    # 来源溯源元数据（offer_url / crawled_at 等，按数据源不同结构可变）
    source_meta: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    last_ingest_run_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("ingest_runs.id", name="fk_products_last_ingest_run_id"),
        nullable=True,
    )

    # 关键词检索派生列:DB 计算、只读;deferred 避免普通查询把它们读回来
    search_tsv: Mapped[str | None] = mapped_column(
        TSVECTOR, Computed(SEARCH_TSV_EXPR, persisted=True), deferred=True,
    )
    search_zh: Mapped[list[str] | None] = mapped_column(
        ARRAY(Text), Computed(SEARCH_ZH_EXPR, persisted=True), deferred=True,
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


# 测试用 metadata.create_all 建表(不走迁移),生成列依赖的函数须先于表创建
event.listen(Product.__table__, "before_create", DDL(ZH_NGRAMS_FUNCTION_SQL))
