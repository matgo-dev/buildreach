from __future__ import annotations

from sqlalchemy import Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
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
    # 统一社会信用代码:中国场景遗留,坦桑场景不使用;保留列兼容存量
    unified_social_credit_code: Mapped[str | None] = mapped_column(
        String(18), unique=True, nullable=True, index=True
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=BuyerOrgStatus.ACTIVE)
    # 坦桑场景新增字段
    address: Mapped[str | None] = mapped_column(String(255), nullable=True)
    tin: Mapped[str | None] = mapped_column(String(50), nullable=True)
    brela_no: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # 经营品类:一级品类 code 数组,注册时沉淀,相对稳定
    business_category_codes: Mapped[list] = mapped_column(
        JSONB, nullable=False, server_default="[]"
    )
