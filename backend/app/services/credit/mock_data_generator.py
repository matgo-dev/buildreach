"""Supplier 注册即评分 · mock 信用数据生成器(工单 Δ5 Step 1)。

按 target_tier(A/B/C/D)产出一套"合理的 mock 信用数据",覆盖四类:
basic / finance / legal / certifications。等级仅是预期,实际分由 ScoringEngine 跑出。

只返回数据结构(不写库、不带 company_id);由调用方落库时补 company_id /
data_source / fetched_at。

# TODO(T-2): 本生成器在真实数据源接入后弃用
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal

from app.db.models import (
    CashFlowStatus,
    CertStatus,
    CertType,
    NegativeNewsLevel,
    RevenueTrend,
)
from app.db.models.supplier_organization import SupplierOrganization

# 四档循环:id % 4 → tier(seed 可显式指定,注册钩子用取模兜底)
TIER_BY_MOD: dict[int, str] = {0: "A", 1: "B", 2: "C", 3: "D"}


@dataclass
class MockCreditDataBundle:
    """一家 Supplier 的 mock 信用数据(不含 company_id / data_source / fetched_at)。"""
    basic_data: dict
    legal_data: dict
    certifications: list[dict]
    finance_data: dict | None = None  # D 档财务整体缺失 → None
    expected_grade: str = "A"
    overrides: dict = field(default_factory=dict)


def tier_for_supplier_org_id(supplier_org_id: int) -> str:
    """注册钩子无显式档位时,按 id 取模循环出 A/B/C/D。"""
    return TIER_BY_MOD[supplier_org_id % 4]


def generate_mock_credit_data_for_supplier(
    supplier_org: SupplierOrganization,
    target_tier: str | None = None,
) -> MockCreditDataBundle:
    """按 target_tier 生成 mock 数据;target_tier 为空则按 supplier_org.id 取模。

    数据形态对齐 seed 既有 4 档样例,但 name/country/regno 取自 supplier_org,
    使每家"看起来是该 Supplier 自己的档案"。
    """
    tier = (target_tier or tier_for_supplier_org_id(supplier_org.id)).upper()
    country = supplier_org.country_code
    regno = supplier_org.registration_no
    today = date.today()

    if tier == "A":
        return _tier_a(country, regno, today)
    if tier == "B":
        return _tier_b(country, regno, today)
    if tier == "C":
        return _tier_c(country, regno, today)
    if tier == "D":
        return _tier_d(country, regno, today)
    # 兜底:未知档位按 A 处理(不抛异常,避免阻断注册)
    return _tier_a(country, regno, today)


# =============================================================================
# 四档样例(工商完整度 / 证书 / 财务 / 司法 逐档恶化)
# =============================================================================

def _tier_a(country: str, regno: str | None, today: date) -> MockCreditDataBundle:
    return MockCreditDataBundle(
        expected_grade="A",
        basic_data={
            "established_date": date(2008, 4, 15),
            "registered_capital": "50,000,000",
            "business_scope": "海外工程总承包、建材进出口、机电安装",
            "legal_representative": "Mohammed Al-Rashid",
            "shareholders": "控股集团 60%, 投资方 40%(完整披露)",
            "status_text": "normal",
            "address": f"Industrial Zone, {country}",
            "website": "https://example.com",
        },
        finance_data={
            "revenue_trend": RevenueTrend.GROWING,
            "debt_ratio": Decimal("58.50"),
            "cash_flow_status": CashFlowStatus.POSITIVE,
        },
        legal_data={
            "litigation_count": 0,
            "defaulter_unresolved_count": 0,
            "defaulter_resolved_count": 0,
            "negative_news_level": NegativeNewsLevel.NONE,
        },
        certifications=[
            {"cert_type": CertType.MANDATORY_COUNTRY, "cert_name": "Country Mandatory Cert",
             "target_country_code": country, "issuer": "National Standards Body",
             "issued_at": today - timedelta(days=200), "expires_at": today + timedelta(days=900),
             "status": CertStatus.VALID},
            {"cert_type": CertType.SYSTEM_GENERAL, "cert_name": "ISO 9001:2015",
             "issuer": "TÜV NORD", "issued_at": today - timedelta(days=180),
             "expires_at": today + timedelta(days=900), "status": CertStatus.VALID},
            {"cert_type": CertType.SYSTEM_GENERAL, "cert_name": "ISO 14001:2015",
             "issuer": "TÜV NORD", "issued_at": today - timedelta(days=180),
             "expires_at": today + timedelta(days=900), "status": CertStatus.VALID},
            {"cert_type": CertType.INDUSTRY_SPECIFIC, "cert_name": "CE Marking",
             "issuer": "Notified Body 0123", "issued_at": today - timedelta(days=150),
             "expires_at": today + timedelta(days=1500), "status": CertStatus.VALID},
            {"cert_type": CertType.INDUSTRY_SPECIFIC, "cert_name": "UL Listed",
             "issuer": "UL LLC", "issued_at": today - timedelta(days=300),
             "expires_at": today + timedelta(days=1500), "status": CertStatus.VALID},
        ],
    )


def _tier_b(country: str, regno: str | None, today: date) -> MockCreditDataBundle:
    return MockCreditDataBundle(
        expected_grade="B",
        basic_data={
            "established_date": date(2012, 8, 20),
            "registered_capital": "15,000,000",
            "business_scope": "建材贸易、工程咨询",
            "legal_representative": "Budi Santoso",
            "shareholders": "控股方(部分披露,具体股权比例未公开)",
            "status_text": "normal",
            "address": f"Capital City, {country}",
            "website": "https://example.com",
        },
        finance_data={
            "revenue_trend": RevenueTrend.FLUCTUATING,
            "debt_ratio": Decimal("75.20"),
            "cash_flow_status": CashFlowStatus.POSITIVE,
        },
        legal_data={
            "litigation_count": 2,
            "defaulter_unresolved_count": 0,
            "defaulter_resolved_count": 0,
            "negative_news_level": NegativeNewsLevel.OCCASIONAL,
        },
        certifications=[
            {"cert_type": CertType.MANDATORY_COUNTRY, "cert_name": "Country Mandatory Cert",
             "target_country_code": country, "issuer": "National Standards Body",
             "issued_at": today - timedelta(days=200), "expires_at": today + timedelta(days=500),
             "status": CertStatus.VALID},
            {"cert_type": CertType.SYSTEM_GENERAL, "cert_name": "ISO 9001:2015",
             "issuer": "Sucofindo ICS", "issued_at": today - timedelta(days=160),
             "expires_at": today + timedelta(days=800), "status": CertStatus.VALID},
            {"cert_type": CertType.INDUSTRY_SPECIFIC, "cert_name": "CE Marking",
             "issuer": "Notified Body 0035", "issued_at": today - timedelta(days=210),
             "expires_at": today + timedelta(days=1400), "status": CertStatus.VALID},
        ],
    )


def _tier_c(country: str, regno: str | None, today: date) -> MockCreditDataBundle:
    return MockCreditDataBundle(
        expected_grade="C",
        basic_data={
            "established_date": date(2015, 3, 10),
            "registered_capital": None,  # 缺资本金
            "business_scope": "钢材加工与出口",
            "legal_representative": "Ahmad Khan",
            "shareholders": "家族信托(部分披露)",
            "status_text": "normal",
            "address": f"Port City, {country}",
            "website": None,
        },
        finance_data={
            "revenue_trend": RevenueTrend.FLUCTUATING,
            "debt_ratio": Decimal("78.00"),
            "cash_flow_status": CashFlowStatus.NEGATIVE_WITH_FUNDING,
        },
        legal_data={
            "litigation_count": 3,
            "defaulter_unresolved_count": 0,
            "defaulter_resolved_count": 1,
            "negative_news_level": NegativeNewsLevel.OCCASIONAL,
        },
        certifications=[
            # 目标国强制认证已过期 → 触发证书关键问题
            {"cert_type": CertType.MANDATORY_COUNTRY, "cert_name": "Country Mandatory Cert",
             "target_country_code": country, "issuer": "National Standards Body",
             "issued_at": today - timedelta(days=1500), "expires_at": today - timedelta(days=400),
             "status": CertStatus.EXPIRED},
            {"cert_type": CertType.SYSTEM_GENERAL, "cert_name": "ISO 9001:2015",
             "issuer": "TÜV", "issued_at": today - timedelta(days=250),
             "expires_at": today + timedelta(days=600), "status": CertStatus.VALID},
        ],
    )


def _tier_d(country: str, regno: str | None, today: date) -> MockCreditDataBundle:
    return MockCreditDataBundle(
        expected_grade="D",
        basic_data={
            "established_date": date(2018, 11, 22),
            "registered_capital": "5,000,000",
            "business_scope": "建筑工程总承包",
            "legal_representative": "Hassan El Idrissi",
            "shareholders": "",  # 无法查证
            "status_text": "abnormal",
            "address": f"City, {country}",
            "website": None,
        },
        finance_data=None,  # 财务整体缺失 → 维度走 missing override
        legal_data={
            "litigation_count": 15,
            "defaulter_unresolved_count": 2,  # 触发司法一票否决
            "defaulter_resolved_count": 3,
            "negative_news_level": NegativeNewsLevel.PERSISTENT,
        },
        certifications=[],
    )
