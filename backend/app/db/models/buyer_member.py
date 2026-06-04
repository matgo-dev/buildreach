from __future__ import annotations

from sqlalchemy import Boolean, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class BuyerMember(Base, TimestampMixin):
    __tablename__ = "buyer_members"
    __table_args__ = (
        UniqueConstraint("user_id", "buyer_org_id", name="uq_buyer_member"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    buyer_org_id: Mapped[int] = mapped_column(
        ForeignKey("buyer_organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    is_owner: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
