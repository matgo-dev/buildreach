"""LLM 抽取输出 schema(Δ7 Step 6)。

LLM 返回的 JSON 用这些模型校验。pydantic 不允许下划线开头的字段名,
故 _evidence / _confidence / _notes 用 alias 映射 + populate_by_name。
"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class FieldEvidenceSchema(BaseModel):
    """LLM 输出的字段级证据(v0.3 对象形态)。

    source_url 不由 LLM 输出、由后处理按 source_index 反查填充,
    故此 Schema 只约束 LLM 输入侧(quote + source_index)。
    """
    quote: str | None = None
    source_index: int | None = None


class _ExtractedBase(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    # v0.3:evidence 从 {field: "quote 字符串"} 升级为 {field: {quote, source_index}}
    evidence: dict[str, FieldEvidenceSchema | None] = Field(
        default_factory=dict, alias="_evidence"
    )
    confidence: str | None = Field(default=None, alias="_confidence")
    notes: str | None = Field(default=None, alias="_notes")


class BasicExtractedSchema(_ExtractedBase):
    established_date: str | None = None  # "YYYY-MM-DD" 字符串,后续 parse
    registered_capital: str | None = None
    business_scope: str | None = None
    legal_representative: str | None = None
    shareholders: str | None = None
    status_text: str | None = None  # 正常/异常/注销/吊销
    address: str | None = None
    website: str | None = None


class FinanceExtractedSchema(_ExtractedBase):
    revenue_trend: str | None = None  # growing/fluctuating/loss/unknown
    debt_ratio: float | None = None
    cash_flow_status: str | None = None  # positive/negative_with_funding/persistent_negative/unknown


class LegalExtractedSchema(_ExtractedBase):
    litigation_count: int | None = None  # 柬埔寨场景多为 null
    defaulter_unresolved_count: int | None = None
    defaulter_resolved_count: int | None = None
    negative_news_level: str | None = None  # none/occasional/persistent/major_scandal/unknown


class CertificationExtractedSchema(_ExtractedBase):
    has_iso_9001: bool | None = None
    has_iso_14001: bool | None = None
    has_iso_45001: bool | None = None
    has_isc_certification: bool | None = None  # 柬埔寨 ISC
    other_certifications: list[str] = Field(default_factory=list)
