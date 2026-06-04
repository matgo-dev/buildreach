"""规则求值函数集中地(信用评估 §3.3 + PRD v0.3 §4.3 + v0.2 重构)。

设计:
- 函数签名统一 `def fn(data: dict) -> bool`
- data 含 4 类数据 + today + country_code(详见 ScoringEngine.compute)
- 拆为两组(v0.2 工单):
  · SUBITEM_EVALUATORS:子项级自然评分,key 严格对应 score_rule.evaluator_key
  · DIMENSION_OVERRIDE_EVALUATORS:维度级强制规则,key 严格对应 score_dimension_override.evaluator_key

档位语义:
- 同 subitem 的 rule 按 priority 升序求值,首条命中即停;全部未命中走 subitem.default_score
- 维度级 override 在 ScoringEngine 子项评分完成后单独跑(post-process),命中后该维度
  最终分被 override.override_score 覆盖,但 score_detail 仍保留自然命中规则,可解释

SUBITEM_EVALUATORS 分布(共约 41 个):
- 维度1 基础工商: 9 个(reg_info × 3 + status × 3 + shareholders × 3)
- 维度2 资质认证: 10 个(mandatory × 3 + system × 3 + industry × 4)
- 维度3 财务健康: 12 个(revenue/debt/cashflow × 4)
- 维度4 司法舆情: 11 个(litigation × 4 + defaulter × 3 + news × 4)

DIMENSION_OVERRIDE_EVALUATORS(共 3 个):
- dim2_cert_forged_or_expired:目标国强制认证伪造/过期 → 维度强制清零
- dim3_unknown:财务数据整维度缺失 → 维度给满分 40%(12 分)
- dim4_unresolved_defaulter:失信被执行未结案 → 维度直接判 0(一票否决)
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any, Callable


# =============================================================================
# 工具
# =============================================================================

def _basic(data: dict) -> dict:
    return data.get("basic") or {}


def _finance(data: dict) -> dict:
    return data.get("finance") or {}


def _legal(data: dict) -> dict:
    return data.get("legal") or {}


def _certs(data: dict) -> list[dict]:
    return data.get("certifications") or []


def _today(data: dict) -> date:
    v = data.get("today")
    if v is None:
        return date.today()
    if isinstance(v, str):
        try:
            return date.fromisoformat(v)
        except ValueError:
            return date.today()
    return v


def _country(data: dict) -> str:
    return data.get("country_code") or ""


def _is_cert_effective(cert: dict, today: date) -> bool:
    """证书有效 = status==valid AND (没设过期 OR 过期日期 > today)。

    过期未更新(status==valid 但 expires_at < today)算无效。
    """
    if cert.get("status") != "valid":
        return False
    expires = cert.get("expires_at")
    if expires is None:
        return True  # 没设过期视为有效(如 ISO 通用证书有时不标过期)
    if isinstance(expires, str):
        # ISO date string,可能从 model_dump 来
        try:
            expires = date.fromisoformat(expires)
        except ValueError:
            return False
    return expires >= today


# =============================================================================
# 维度1: 基础工商(15 分 = 3 子项 × 5 分)
# =============================================================================

# ---- 子项 1.1: 注册信息完整性(注册时间 / 资本金 / 经营范围 齐全度)----

def basic_reg_info_full(data: dict) -> bool:
    """3 项齐全 → 5 分。"""
    b = _basic(data)
    have = [b.get("established_date"), b.get("registered_capital"), b.get("business_scope")]
    return sum(1 for f in have if f) == 3


def basic_reg_info_miss_one(data: dict) -> bool:
    """缺 1 项 → 3 分。"""
    b = _basic(data)
    have = [b.get("established_date"), b.get("registered_capital"), b.get("business_scope")]
    return sum(1 for f in have if f) == 2


def basic_reg_info_miss_two_or_more(data: dict) -> bool:
    """缺 ≥2 项 → 0 分(兜底命中)。"""
    b = _basic(data)
    have = [b.get("established_date"), b.get("registered_capital"), b.get("business_scope")]
    return sum(1 for f in have if f) <= 1


# ---- 子项 1.2: 存续状态 ----

def basic_status_normal(data: dict) -> bool:
    return _basic(data).get("status_text") == "normal"


def basic_status_abnormal(data: dict) -> bool:
    return _basic(data).get("status_text") == "abnormal"


def basic_status_cancelled(data: dict) -> bool:
    """已注销/吊销/None → 0 分(兜底)。"""
    s = _basic(data).get("status_text")
    return s in (None, "", "cancelled")


# ---- 子项 1.3: 股东与股权 ----
# 用 shareholders 文本特征区分:
#   - 含 "%" 且 含 "公司" / "持股" → 清晰
#   - 非空但无百分比 → 部分可查
#   - None/空 → 无法查证

def basic_shareholders_clear(data: dict) -> bool:
    """股权结构清晰:文本含百分比标记(说明披露了股权比例)。"""
    s = _basic(data).get("shareholders") or ""
    return "%" in s


def basic_shareholders_partial(data: dict) -> bool:
    s = _basic(data).get("shareholders") or ""
    if not s:
        return False
    return "%" not in s  # 有文本但没百分比 → 部分


def basic_shareholders_missing(data: dict) -> bool:
    """空 → 0 分(兜底)。"""
    s = _basic(data).get("shareholders") or ""
    return s == ""


# =============================================================================
# 维度2: 资质认证(25 分) — 维度级 override 见底部 DIMENSION_OVERRIDE_EVALUATORS
# =============================================================================

# ---- 子项 2.1: 目标国强制认证(10 分)----

def cert_mandatory_valid(data: dict) -> bool:
    """具备目标国强制认证且在有效期内 → 10 分。"""
    today = _today(data)
    country = _country(data)
    for c in _certs(data):
        if c.get("cert_type") != "mandatory_country":
            continue
        if c.get("target_country_code") and c["target_country_code"] != country:
            continue
        if _is_cert_effective(c, today):
            return True
    return False


def cert_mandatory_expired(data: dict) -> bool:
    """有目标国强制认证但已过期(且无有效的同类)→ 3 分。"""
    if cert_mandatory_valid(data):
        return False
    country = _country(data)
    for c in _certs(data):
        if c.get("cert_type") != "mandatory_country":
            continue
        if c.get("target_country_code") and c["target_country_code"] != country:
            continue
        # status=expired 或 valid 但已过期
        if c.get("status") in ("expired", "valid"):
            return True
    return False


def cert_mandatory_missing(data: dict) -> bool:
    """无目标国强制认证 → 0 分(兜底)。"""
    country = _country(data)
    for c in _certs(data):
        if c.get("cert_type") != "mandatory_country":
            continue
        if c.get("target_country_code") and c["target_country_code"] != country:
            continue
        return False  # 有这类证书(无论状态)→ 不算 missing
    return True


# ---- 子项 2.2: 通用体系认证(8 分,每项 +4 最高 8)----

def _system_valid_count(data: dict) -> int:
    today = _today(data)
    return sum(
        1
        for c in _certs(data)
        if c.get("cert_type") == "system_general" and _is_cert_effective(c, today)
    )


def cert_system_count_2_or_more(data: dict) -> bool:
    return _system_valid_count(data) >= 2


def cert_system_count_1(data: dict) -> bool:
    return _system_valid_count(data) == 1


def cert_system_count_0(data: dict) -> bool:
    return _system_valid_count(data) == 0


# ---- 子项 2.3: 行业专项认证(7 分,每项 +3,3 项及以上 cap 7)----

def _industry_valid_count(data: dict) -> int:
    today = _today(data)
    return sum(
        1
        for c in _certs(data)
        if c.get("cert_type") == "industry_specific" and _is_cert_effective(c, today)
    )


def cert_industry_count_3_or_more(data: dict) -> bool:
    return _industry_valid_count(data) >= 3


def cert_industry_count_2(data: dict) -> bool:
    return _industry_valid_count(data) == 2


def cert_industry_count_1(data: dict) -> bool:
    return _industry_valid_count(data) == 1


def cert_industry_count_0(data: dict) -> bool:
    return _industry_valid_count(data) == 0


# =============================================================================
# 维度3: 财务健康(30 分) — 维度级 override 见底部 DIMENSION_OVERRIDE_EVALUATORS
# =============================================================================

# ---- 子项 3.1: 营收与盈利(10 分)----

def finance_revenue_growing(data: dict) -> bool:
    return _finance(data).get("revenue_trend") == "growing"


def finance_revenue_fluctuating(data: dict) -> bool:
    return _finance(data).get("revenue_trend") == "fluctuating"


def finance_revenue_loss(data: dict) -> bool:
    return _finance(data).get("revenue_trend") == "loss"


def finance_revenue_unknown(data: dict) -> bool:
    """单子项 unknown → 5 分(50%);兜底命中包括 None。"""
    v = _finance(data).get("revenue_trend")
    return v in (None, "", "unknown")


# ---- 子项 3.2: 资产负债(10 分)----

def _debt_ratio(data: dict) -> Decimal | None:
    v = _finance(data).get("debt_ratio")
    if v is None:
        return None
    if isinstance(v, Decimal):
        return v
    try:
        return Decimal(str(v))
    except Exception:  # noqa: BLE001
        return None


def finance_debt_low(data: dict) -> bool:
    v = _debt_ratio(data)
    return v is not None and v < Decimal("70")


def finance_debt_medium(data: dict) -> bool:
    v = _debt_ratio(data)
    return v is not None and Decimal("70") <= v <= Decimal("85")


def finance_debt_high(data: dict) -> bool:
    v = _debt_ratio(data)
    return v is not None and v > Decimal("85")


def finance_debt_unknown(data: dict) -> bool:
    return _debt_ratio(data) is None


# ---- 子项 3.3: 现金流(10 分)----

def finance_cashflow_positive(data: dict) -> bool:
    return _finance(data).get("cash_flow_status") == "positive"


def finance_cashflow_negative_with_funding(data: dict) -> bool:
    return _finance(data).get("cash_flow_status") == "negative_with_funding"


def finance_cashflow_persistent_negative(data: dict) -> bool:
    return _finance(data).get("cash_flow_status") == "persistent_negative"


def finance_cashflow_unknown(data: dict) -> bool:
    v = _finance(data).get("cash_flow_status")
    return v in (None, "", "unknown")


# =============================================================================
# 维度4: 司法舆情(30 分) — 维度级 override 见底部 DIMENSION_OVERRIDE_EVALUATORS
# =============================================================================

# ---- 子项 4.1: 法律诉讼(10 分)----

def legal_litigation_zero(data: dict) -> bool:
    return (_legal(data).get("litigation_count") or 0) == 0


def legal_litigation_low(data: dict) -> bool:
    n = _legal(data).get("litigation_count") or 0
    return 1 <= n < 5


def legal_litigation_medium(data: dict) -> bool:
    n = _legal(data).get("litigation_count") or 0
    return 5 <= n <= 20


def legal_litigation_high(data: dict) -> bool:
    return (_legal(data).get("litigation_count") or 0) > 20


# ---- 子项 4.2: 失信被执行(10 分)----

def legal_defaulter_none(data: dict) -> bool:
    leg = _legal(data)
    return (leg.get("defaulter_unresolved_count") or 0) == 0 and (
        leg.get("defaulter_resolved_count") or 0
    ) == 0


def legal_defaulter_resolved_only(data: dict) -> bool:
    leg = _legal(data)
    return (leg.get("defaulter_unresolved_count") or 0) == 0 and (
        leg.get("defaulter_resolved_count") or 0
    ) > 0


def legal_defaulter_unresolved(data: dict) -> bool:
    """有未结案 → 0(兜底命中,理论上 veto 会先拦截整维度)。"""
    return (_legal(data).get("defaulter_unresolved_count") or 0) > 0


# ---- 子项 4.3: 负面舆情(10 分)----

def legal_news_none(data: dict) -> bool:
    return _legal(data).get("negative_news_level") in ("none", None, "")


def legal_news_occasional(data: dict) -> bool:
    return _legal(data).get("negative_news_level") == "occasional"


def legal_news_persistent(data: dict) -> bool:
    return _legal(data).get("negative_news_level") == "persistent"


def legal_news_major_scandal(data: dict) -> bool:
    return _legal(data).get("negative_news_level") == "major_scandal"


# =============================================================================
# 维度级 override(post-process,跑在子项自然评分之后)
# =============================================================================

def dim2_cert_forged_or_expired(data: dict) -> bool:
    """维度2 强制清零:**目标国强制认证**(cert_type='mandatory_country')伪造或过期。

    PRD §4.3 维度2"关键证书伪造或过期未更新 → 该维度强制清零"。
    "关键证书"在 v0.2 工单里精确为 mandatory_country 一类(不含 system/industry)。

    触发条件:
    - status == 'suspicious_forged'
    - status == 'expired'
    - status == 'valid' 但 expires_at < today(数据滞后,实际已过期)
    """
    today = _today(data)
    for c in _certs(data):
        if c.get("cert_type") != "mandatory_country":
            continue
        status = c.get("status")
        if status in ("suspicious_forged", "expired"):
            return True
        if status == "valid":
            expires = c.get("expires_at")
            if expires is not None:
                if isinstance(expires, str):
                    try:
                        expires = date.fromisoformat(expires)
                    except ValueError:
                        continue
                if expires < today:
                    return True
    return False


def dim3_unknown(data: dict) -> bool:
    """维度3 整维度数据缺失 → override_score=12(40% × 30)。

    判定:finance 数据 data_source == 'missing'(MockDataSource 在表无数据时返回的 stub)。
    """
    fin = _finance(data)
    return (fin.get("data_source") or "") == "missing"


def dim4_unresolved_defaulter(data: dict) -> bool:
    """维度4 一票否决:有未结案失信记录 → override_score=0。"""
    return (_legal(data).get("defaulter_unresolved_count") or 0) > 0


# =============================================================================
# 导出字典(严格对应:score_rule.evaluator_key + score_dimension_override.evaluator_key)
# =============================================================================

SUBITEM_EVALUATORS: dict[str, Callable[[dict[str, Any]], bool]] = {
    # 维度1
    "basic_reg_info_full": basic_reg_info_full,
    "basic_reg_info_miss_one": basic_reg_info_miss_one,
    "basic_reg_info_miss_two_or_more": basic_reg_info_miss_two_or_more,
    "basic_status_normal": basic_status_normal,
    "basic_status_abnormal": basic_status_abnormal,
    "basic_status_cancelled": basic_status_cancelled,
    "basic_shareholders_clear": basic_shareholders_clear,
    "basic_shareholders_partial": basic_shareholders_partial,
    "basic_shareholders_missing": basic_shareholders_missing,
    # 维度2
    "cert_mandatory_valid": cert_mandatory_valid,
    "cert_mandatory_expired": cert_mandatory_expired,
    "cert_mandatory_missing": cert_mandatory_missing,
    "cert_system_count_2_or_more": cert_system_count_2_or_more,
    "cert_system_count_1": cert_system_count_1,
    "cert_system_count_0": cert_system_count_0,
    "cert_industry_count_3_or_more": cert_industry_count_3_or_more,
    "cert_industry_count_2": cert_industry_count_2,
    "cert_industry_count_1": cert_industry_count_1,
    "cert_industry_count_0": cert_industry_count_0,
    # 维度3
    "finance_revenue_growing": finance_revenue_growing,
    "finance_revenue_fluctuating": finance_revenue_fluctuating,
    "finance_revenue_loss": finance_revenue_loss,
    "finance_revenue_unknown": finance_revenue_unknown,
    "finance_debt_low": finance_debt_low,
    "finance_debt_medium": finance_debt_medium,
    "finance_debt_high": finance_debt_high,
    "finance_debt_unknown": finance_debt_unknown,
    "finance_cashflow_positive": finance_cashflow_positive,
    "finance_cashflow_negative_with_funding": finance_cashflow_negative_with_funding,
    "finance_cashflow_persistent_negative": finance_cashflow_persistent_negative,
    "finance_cashflow_unknown": finance_cashflow_unknown,
    # 维度4
    "legal_litigation_zero": legal_litigation_zero,
    "legal_litigation_low": legal_litigation_low,
    "legal_litigation_medium": legal_litigation_medium,
    "legal_litigation_high": legal_litigation_high,
    "legal_defaulter_none": legal_defaulter_none,
    "legal_defaulter_resolved_only": legal_defaulter_resolved_only,
    "legal_defaulter_unresolved": legal_defaulter_unresolved,
    "legal_news_none": legal_news_none,
    "legal_news_occasional": legal_news_occasional,
    "legal_news_persistent": legal_news_persistent,
    "legal_news_major_scandal": legal_news_major_scandal,
}


DIMENSION_OVERRIDE_EVALUATORS: dict[str, Callable[[dict[str, Any]], bool]] = {
    "dim2_cert_forged_or_expired": dim2_cert_forged_or_expired,
    "dim3_unknown": dim3_unknown,
    "dim4_unresolved_defaulter": dim4_unresolved_defaulter,
}


# Backward-compat alias(其他模块迁移期间用,后续可删)。
EVALUATORS = SUBITEM_EVALUATORS
