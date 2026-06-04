"""企业证书(信用评估 §二 · 维度2 数据源)。

cert_type 三类:
- mandatory_country  目标国强制认证(如沙特 SASO、印尼 SNI)
- system_general     通用体系认证(ISO9001 / ISO14001 等)
- industry_specific  行业专项认证(如 CE / UL)

status:valid / expired / suspicious_forged(伪造或可疑触发维度2 清零)
"""
from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import Date, ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampUpdateMixin


class CertType:
    MANDATORY_COUNTRY = "mandatory_country"
    SYSTEM_GENERAL = "system_general"
    INDUSTRY_SPECIFIC = "industry_specific"


class CertStatus:
    VALID = "valid"
    EXPIRED = "expired"
    SUSPICIOUS_FORGED = "suspicious_forged"


class CreditCompanyCertification(Base, TimestampUpdateMixin):
    __tablename__ = "credit_company_certification"
    __table_args__ = (
        Index(
            "ix_credit_cert_company_type", "company_id", "cert_type"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("credit_company.id", name="fk_credit_cert_company"),
        nullable=False,
    )
    cert_type: Mapped[str] = mapped_column(String(50), nullable=False)
    cert_name: Mapped[str] = mapped_column(String(200), nullable=False)
    # 仅 mandatory_country 类型填:对应目标出口国 ISO 二字码
    target_country_code: Mapped[str | None] = mapped_column(String(2), nullable=True)
    issuer: Mapped[str | None] = mapped_column(String(200), nullable=True)
    issued_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    expires_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    data_source: Mapped[str] = mapped_column(String(20), nullable=False)
    # Δ7:抓取留存的原始 LLM 应答;harvest_run_id 追溯抓取批次
    raw_data: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    harvest_run_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("credit_data_harvest_run.id", name="fk_credit_cert_harvest_run"),
        nullable=True,
    )
