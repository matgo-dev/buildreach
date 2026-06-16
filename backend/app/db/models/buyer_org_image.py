"""买方组织图片 — 门店照片(STOREFRONT) + 证照图片(LICENSE)。

走 SoftDeleteMixin,门店照片有审计与地推沉淀价值。
"""
from __future__ import annotations

from sqlalchemy import ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin
from app.db.soft_delete_mixin import SoftDeleteMixin


class BuyerOrgImageType:
    STOREFRONT = "STOREFRONT"
    LICENSE = "LICENSE"
    ALL = (STOREFRONT, LICENSE)


class BuyerOrgImage(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "buyer_org_images"
    __table_args__ = (
        Index("ix_buyer_org_images_org_id", "buyer_org_id"),
        Index("ix_buyer_org_images_type", "buyer_org_id", "image_type"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    buyer_org_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("buyer_organizations.id", name="fk_buyer_org_images_org_id", ondelete="CASCADE"),
        nullable=False,
    )
    image_key: Mapped[str] = mapped_column(String(300), nullable=False)
    image_type: Mapped[str] = mapped_column(String(20), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    file_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
