"""信用评估服务层类型(用于 DataSource 返回 + 引擎输入输出)。

为什么用 Pydantic 而不是直接传 ORM:
- 解耦数据获取层与评分逻辑层(future:换数据源 = 换实现,引擎不动)
- 评分时把数据"快照"成纯 dict 写入 evaluation_context,可复算 / 排错
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class BasicData(BaseModel):
    """工商基础数据(供维度1 用)。"""
    model_config = ConfigDict(from_attributes=True)

    id: int | None = None  # ORM 行 id;source=missing 时为 None
    company_id: int
    established_date: date | None = None
    registered_capital: str | None = None
    business_scope: str | None = None
    legal_representative: str | None = None
    shareholders: str | None = None
    status_text: str | None = None
    address: str | None = None
    website: str | None = None
    raw_data: dict[str, Any] | None = None  # Δ7:抓取留存
    # 来源标记:mock / official / api / public / media / missing
    data_source: str = "mock"
    fetched_at: datetime | None = None

    @property
    def is_missing(self) -> bool:
        return self.data_source == "missing"


class FinanceData(BaseModel):
    """财务数据(供维度3 用)。"""
    model_config = ConfigDict(from_attributes=True)

    id: int | None = None
    company_id: int
    revenue_trend: str | None = None       # growing / fluctuating / loss / unknown
    debt_ratio: Decimal | None = None
    cash_flow_status: str | None = None    # positive / negative_with_funding / persistent_negative / unknown
    raw_data: dict[str, Any] | None = None
    data_source: str = "mock"
    fetched_at: datetime | None = None

    @property
    def is_missing(self) -> bool:
        return self.data_source == "missing"


class LegalData(BaseModel):
    """司法舆情数据(供维度4 用)。"""
    model_config = ConfigDict(from_attributes=True)

    id: int | None = None
    company_id: int
    litigation_count: int = 0
    defaulter_unresolved_count: int = 0
    defaulter_resolved_count: int = 0
    negative_news_level: str | None = None  # none / occasional / persistent / major_scandal / unknown
    raw_data: dict[str, Any] | None = None
    data_source: str = "mock"
    fetched_at: datetime | None = None

    @property
    def is_missing(self) -> bool:
        return self.data_source == "missing"


class Certification(BaseModel):
    """单条证书(供维度2 用)。"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    cert_type: str  # mandatory_country / system_general / industry_specific
    cert_name: str
    target_country_code: str | None = None
    issuer: str | None = None
    issued_at: date | None = None
    expires_at: date | None = None
    status: str  # valid / expired / suspicious_forged
    data_source: str = "mock"


class EvaluationInput(BaseModel):
    """评分引擎完整输入上下文(传给每个 evaluator)。"""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    company_id: int
    country_code: str
    basic: BasicData
    finance: FinanceData
    legal: LegalData
    certifications: list[Certification] = Field(default_factory=list)
    # 评分上下文里也带"今天"(用于证书过期判断)
    today: date


class SubitemResult(BaseModel):
    """单子项评分结果(写入 score_detail)。"""
    subitem_code: str
    score: int
    hit_rule_code: str | None
    hit_rule_description: str | None
    is_default_score: bool


class DimensionResult(BaseModel):
    """单维度评分结果。"""
    dimension_code: str
    score: int
    max_score: int
    subitems: list[SubitemResult]


class DimensionOverrideHit(BaseModel):
    """命中维度级 override 的明细(写入 score_snapshot.dimension_overrides JSONB)。"""
    dimension_code: str
    override_rule_code: str
    override_description: str
    natural_score: int
    final_score: int


class ScoringResult(BaseModel):
    """ScoringEngine.compute 完整输出(用于写库前的中间产物)。

    v0.2 重构:同时记录自然分(natural_dim_scores)和最终分(dimensions[i].score),
    后者可能被维度级 override 覆盖。dimension_overrides 记录命中明细。
    """
    company_id: int
    total_score: int  # = sum(final_score per dim)
    grade: str
    dimensions: list[DimensionResult]  # score 字段是 final_score(可能被 override 覆盖)
    natural_dim_scores: dict[str, int]  # dimension_code → 自然分(未 override)
    dimension_overrides: list[DimensionOverrideHit]  # 命中的维度级 override 列表,可为空
    rule_version: int
    basic_data_id: int | None = None
    finance_data_id: int | None = None
    legal_data_id: int | None = None
