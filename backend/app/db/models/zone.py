"""央企专区(Zone)四表:zones / zone_categories / zone_products / zone_grants。

设计要点:
- zones:专区主表(code / 多语名 / status / sort_order)。
- zone_categories:专区自有类目树(区别于全局 categories),`(zone_id, id)` 唯一约束供
  zone_products 的复合外键引用,保证类目必须属于同一 zone。
- zone_products:专区选品,`zone_category_id` 不直接建单列 FK,而是与 zone_id 一起组成
  复合外键指向 zone_categories.(zone_id, id),杜绝跨专区串联类目。
- zone_grants:专区对 buyer_organization 的授权关系。
"""
from __future__ import annotations

from sqlalchemy import (
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    JSON,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampUpdateMixin
from app.db.i18n_mixin import I18nMixin


class Zone(Base, TimestampUpdateMixin):
    __tablename__ = "zones"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)  # CENTRAL_SOE
    name_zh: Mapped[str] = mapped_column(String(128), nullable=False)
    name_en: Mapped[str | None] = mapped_column(String(128))
    name_sw: Mapped[str | None] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="ACTIVE")  # ACTIVE/INACTIVE
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class ZoneCategory(Base, TimestampUpdateMixin, I18nMixin):
    __tablename__ = "zone_categories"
    __table_args__ = (
        UniqueConstraint("zone_id", "code", name="uq_zone_categories_zone_code"),
        # 供 zone_product 复合外键引用(保证类目属于同一 zone)
        UniqueConstraint("zone_id", "id", name="uq_zone_categories_zone_id_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    zone_id: Mapped[int] = mapped_column(ForeignKey("zones.id"), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(16), nullable=False)  # 01..17
    name_zh: Mapped[str] = mapped_column(String(128), nullable=False)
    name_en: Mapped[str | None] = mapped_column(String(128))
    name_sw: Mapped[str | None] = mapped_column(String(128))
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    mapped_platform_codes: Mapped[list] = mapped_column(JSON, nullable=False, default=list)  # OVH category codes, 选品辅助


class ZoneProduct(Base, TimestampUpdateMixin):
    __tablename__ = "zone_products"
    __table_args__ = (
        UniqueConstraint("zone_id", "spu_id", "zone_category_id", name="uq_zone_products_triplet"),
        # 复合外键:zone_category 必须属于同一 zone,杜绝跨专区串联
        ForeignKeyConstraint(
            ["zone_id", "zone_category_id"],
            ["zone_categories.zone_id", "zone_categories.id"],
            name="fk_zone_products_category_same_zone",
        ),
        # v2 查询索引
        Index("ix_zone_product_zone_category_sort", "zone_id", "zone_category_id", "sort_order", "id"),
        Index("ix_zone_product_zone_spu", "zone_id", "spu_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    zone_id: Mapped[int] = mapped_column(ForeignKey("zones.id"), nullable=False, index=True)
    spu_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False, index=True)
    zone_category_id: Mapped[int] = mapped_column(Integer, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    source: Mapped[str] = mapped_column(String(16), nullable=False, default="MANUAL")  # IMPORT | MANUAL
    source_batch_id: Mapped[str | None] = mapped_column(String(64))
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))


class ZoneGrant(Base, TimestampUpdateMixin):
    __tablename__ = "zone_grants"
    __table_args__ = (
        UniqueConstraint("zone_id", "buyer_org_id", name="uq_zone_grants_zone_org"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    zone_id: Mapped[int] = mapped_column(ForeignKey("zones.id"), nullable=False, index=True)
    buyer_org_id: Mapped[int] = mapped_column(ForeignKey("buyer_organizations.id"), nullable=False, index=True)
    granted_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
