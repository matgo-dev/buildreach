"""软删除 Mixin — 为业务表提供 deleted_at + deleted_by 字段。

用法:
    class Product(Base, TimestampUpdateMixin, I18nMixin, SoftDeleteMixin):
        __tablename__ = "products"
        ...

删除时:
    obj.deleted_at = _utcnow()
    obj.deleted_by = current_user.id

查询时:
    query.where(Model.deleted_at.is_(None))
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column


class SoftDeleteMixin:
    """deleted_at 有值 = 已删除，NULL = 正常记录。"""

    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True, default=None, index=True,
    )
    deleted_by: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("users.id", name="fk_%(table_name)s_deleted_by"),
        nullable=True,
        default=None,
    )
