from __future__ import annotations

from sqlalchemy import Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampUpdateMixin


class SupplierOrgStatus:
    """供应商组织状态(MVP 简化:注册后即 DRAFT,审核流程在后续 prompt)。"""

    DRAFT = "DRAFT"
    UNDER_REVIEW = "UNDER_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    DISABLED = "DISABLED"


class SupplierOrganization(Base, TimestampUpdateMixin):
    __tablename__ = "supplier_organizations"
    # 复合唯一:不同国家允许 registration_no 字符串撞号
    __table_args__ = (
        UniqueConstraint(
            "country_code", "registration_no", name="uq_supplier_org_country_regno"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    # 9 国之一(ISO 2 位 code),应用层枚举校验
    country_code: Mapped[str] = mapped_column(String(2), nullable=False)
    # 各国凭证号统一存这里(规则按 country_code 分发,见 app/constants/country_registration.py)
    registration_no: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=SupplierOrgStatus.DRAFT)
