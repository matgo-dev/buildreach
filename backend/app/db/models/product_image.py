"""商品图片。

image_type: MAIN(主图,每商品仅1张) / GALLERY(轮播图) / DETAIL(详情描述图)
image_key: 存储相对路径，完整 URL 由后端按 IMAGE_BASE_URL 拼接。
上传时自动压缩到 800x800 正方形 JPEG。
"""
from __future__ import annotations

from sqlalchemy import ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class ImageType:
    MAIN = "MAIN"
    GALLERY = "GALLERY"
    DETAIL = "DETAIL"
    ALL = (MAIN, GALLERY, DETAIL)


class ProductImage(Base, TimestampMixin):
    __tablename__ = "product_images"
    __table_args__ = (
        Index("ix_product_images_product_id", "product_id"),
        Index("ix_product_images_type", "product_id", "image_type"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("products.id", name="fk_product_images_product_id", ondelete="CASCADE"),
        nullable=False,
    )
    image_key: Mapped[str] = mapped_column(String(300), nullable=False)
    image_type: Mapped[str] = mapped_column(String(20), nullable=False, default=ImageType.GALLERY)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    file_size: Mapped[int | None] = mapped_column(Integer, nullable=True)

    product: Mapped["Product"] = relationship("Product", back_populates="images")
