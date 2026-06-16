"""商品图片。

image_type: MAIN(主图) / GALLERY(轮播图) / DETAIL(详情描述图)
image_key: 存储相对路径，完整 URL 由后端按 IMAGE_BASE_URL 拼接。
sku_id: NULL=SPU 级图片，非空=SKU 级图片。
"""
from __future__ import annotations

from sqlalchemy import ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin
from app.db.soft_delete_mixin import SoftDeleteMixin


class ImageType:
    MAIN = "MAIN"
    GALLERY = "GALLERY"
    DETAIL = "DETAIL"
    ALL = (MAIN, GALLERY, DETAIL)


class ProductImage(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "product_images"
    __table_args__ = (
        Index("ix_product_images_product_id", "product_id"),
        Index("ix_product_images_type", "product_id", "image_type"),
        Index("ix_product_images_sku_id", "sku_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("products.id", name="fk_product_images_product_id", ondelete="CASCADE"),
        nullable=False,
    )
    sku_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("product_skus.id", name="fk_product_images_sku_id", ondelete="SET NULL"),
        nullable=True,
    )
    image_key: Mapped[str] = mapped_column(String(300), nullable=False)
    image_type: Mapped[str] = mapped_column(String(20), nullable=False, default=ImageType.GALLERY)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    file_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # 色板等规格图绑定到具体规格值,如 "颜色:Red"
    spec_value: Mapped[str | None] = mapped_column(String(200), nullable=True)

    product: Mapped["Product"] = relationship("Product", back_populates="images")
    sku: Mapped["ProductSku | None"] = relationship("ProductSku", back_populates="images")
