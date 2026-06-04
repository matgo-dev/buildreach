"""信用评估目标企业主表(信用评估 §二)。

候选搜索按 (country_code, name) 模糊查;`linked_supplier_org_id` 可选,
若该企业同时在平台供应商入驻流程中,可关联;但本期不强制。
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampUpdateMixin


class CreditCompany(Base, TimestampUpdateMixin):
    __tablename__ = "credit_company"
    __table_args__ = (
        UniqueConstraint("country_code", "name", name="uq_credit_company_country_name"),
        Index("ix_credit_company_country", "country_code"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    legal_name_en: Mapped[str | None] = mapped_column(String(300), nullable=True)
    country_code: Mapped[str] = mapped_column(String(2), nullable=False)
    registration_no: Mapped[str | None] = mapped_column(String(100), nullable=True)
    linked_supplier_org_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey(
            "supplier_organizations.id", name="fk_credit_company_supplier_org"
        ),
        nullable=True,
    )
    # 各维度数据完整/缺失/抓取状态汇总(便于雷达图渲染虚线区域)
    data_status: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    created_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    updated_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
