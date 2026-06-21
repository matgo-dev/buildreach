"""通用附件表 — 多态归属(RFQ / QUOTE / 未来可扩),policy-free。

通用层只管"文件 + owner 归属",不带平台可见性字段;
谁能看由 owner 域在下载 scope 判定。
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampUpdateMixin
from app.db.soft_delete_mixin import SoftDeleteMixin


class OwnerType:
    RFQ = "RFQ"
    QUOTE = "QUOTE"
    ALL = (RFQ, QUOTE)


class Attachment(Base, TimestampUpdateMixin, SoftDeleteMixin):
    __tablename__ = "attachments"
    __table_args__ = (
        # owner_type / owner_id 同空同非空
        CheckConstraint(
            "(owner_type IS NULL AND owner_id IS NULL) "
            "OR (owner_type IS NOT NULL AND owner_id IS NOT NULL)",
            name="ck_attachments_owner_sync",
        ),
        # owner_type 取值白名单(显式放行 NULL)
        CheckConstraint(
            "owner_type IS NULL OR owner_type IN ('RFQ', 'QUOTE')",
            name="ck_attachments_owner_type_enum",
        ),
        # 按 owner 查附件 + 软删过滤
        Index("ix_attachments_owner", "owner_type", "owner_id", "deleted_at"),
        # 上传者索引
        Index("ix_attachments_uploaded_by", "uploaded_by_user_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # 服务端生成: uuid4 + 白名单扩展名,即私有目录内文件名
    file_key: Mapped[str] = mapped_column(String(300), unique=True, nullable=False)

    # 原始文件名(展示/下载用)
    original_filename: Mapped[str] = mapped_column(String(500), nullable=False)

    # 服务端规范化后的 MIME(嗅探/canonical,非客户端声明原值)
    content_type: Mapped[str] = mapped_column(String(200), nullable=False)

    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)

    # 上传者(仅草稿孤儿期鉴权依据)
    uploaded_by_user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", name="fk_attachments_uploaded_by"),
        nullable=False,
    )

    # 多态归属:NULL = 草稿孤儿
    owner_type: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    owner_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # 首次关联时间:第一次归属时置值,永不清除
    # NULL = 从未归属;非 NULL = 曾归属过
    first_linked_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True, default=None,
    )

    # 缩略图(仅图片类型附件,上传时 Pillow 生成 300px JPEG)
    thumbnail_key: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    thumbnail_content_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    thumbnail_size_bytes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
