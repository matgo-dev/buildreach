"""购物车主表。

复合唯一 (buyer_org_id, buyer_user_id)——同一组织内一用户一活动车。
硬删除——购物车无审计追溯需求。
"""
from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampUpdateMixin


class Cart(Base, TimestampUpdateMixin):
    __tablename__ = "carts"
    __table_args__ = (
        UniqueConstraint(
            "buyer_org_id", "buyer_user_id",
            name="uq_carts_buyer_org_user",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    buyer_org_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("buyer_organizations.id", name="fk_carts_buyer_org_id"),
        nullable=False,
    )
    buyer_user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", name="fk_carts_buyer_user_id"),
        nullable=False,
    )

    # relationships
    items: Mapped[list["CartItem"]] = relationship(
        "CartItem", back_populates="cart", cascade="all, delete-orphan",
    )
