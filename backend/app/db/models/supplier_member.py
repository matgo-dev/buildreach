from __future__ import annotations

from sqlalchemy import Boolean, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class SupplierMember(Base, TimestampMixin):
    __tablename__ = "supplier_members"
    __table_args__ = (
        UniqueConstraint("user_id", "supplier_org_id", name="uq_supplier_member"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    supplier_org_id: Mapped[int] = mapped_column(
        ForeignKey("supplier_organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    is_owner: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
