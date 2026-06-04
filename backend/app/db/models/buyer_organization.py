from __future__ import annotations

from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampUpdateMixin


class BuyerOrgStatus:
    ACTIVE = "ACTIVE"
    DISABLED = "DISABLED"


class BuyerOrganization(Base, TimestampUpdateMixin):
    __tablename__ = "buyer_organizations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    code: Mapped[str | None] = mapped_column(String(50), unique=True, nullable=True)
    # 统一社会信用代码:18 位大写字母 + 数字,采购方注册时按此识别企业
    unified_social_credit_code: Mapped[str | None] = mapped_column(
        String(18), unique=True, nullable=True, index=True
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=BuyerOrgStatus.ACTIVE)
