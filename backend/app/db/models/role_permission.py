from __future__ import annotations

from sqlalchemy import ForeignKey, Index, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin
from app.db.soft_delete_mixin import SoftDeleteMixin


class RolePermission(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "role_permissions"
    __table_args__ = (
        Index(
            "uq_role_permission_active",
            "role_id", "permission_id",
            unique=True,
            postgresql_where="deleted_at IS NULL",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    role_id: Mapped[int] = mapped_column(
        ForeignKey("roles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    permission_id: Mapped[int] = mapped_column(
        ForeignKey("permissions.id", ondelete="CASCADE"), nullable=False, index=True
    )
