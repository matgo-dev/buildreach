"""信用评估接口 schema(对齐 docs/architecture/信用评估模块技术方案设计-v0_1.md §四 + §六)。"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


# =============================================================================
# 候选企业(列表 / 详情共用)
# =============================================================================

class CompanyListItem(BaseModel):
    """搜索结果列表 item。"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    legal_name_en: str | None = None
    country_code: str
    registration_no: str | None = None
    total_score: int | None = None
    grade: str | None = None


class BasicDataOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    established_date: date | None = None
    registered_capital: str | None = None
    business_scope: str | None = None
    legal_representative: str | None = None
    shareholders: str | None = None
    status_text: str | None = None
    address: str | None = None
    website: str | None = None
    data_source: str
    fetched_at: datetime | None = None


class FinanceDataOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    revenue_trend: str | None = None
    debt_ratio: Decimal | None = None
    cash_flow_status: str | None = None
    data_source: str
    fetched_at: datetime | None = None


class LegalDataOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    litigation_count: int
    defaulter_unresolved_count: int
    defaulter_resolved_count: int
    negative_news_level: str | None = None
    data_source: str
    fetched_at: datetime | None = None


class CertificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    cert_type: str
    cert_name: str
    target_country_code: str | None = None
    issuer: str | None = None
    issued_at: date | None = None
    expires_at: date | None = None
    status: str
    data_source: str


class ScoreDetailOut(BaseModel):
    """单子项明细。"""
    model_config = ConfigDict(from_attributes=True)
    dimension_code: str
    dimension_name: str
    subitem_code: str
    subitem_name: str
    score: int
    max_score: int
    hit_rule_code: str | None = None
    hit_rule_description: str | None = None
    is_default_score: bool


class DimensionOut(BaseModel):
    """维度元信息 + 当前分(用于前端雷达图)。"""
    code: str
    name: str
    max_score: int
    score: int


class DimensionOverrideHitOut(BaseModel):
    """命中的维度级 override 明细(v0.2)。"""
    dimension_code: str
    override_rule_code: str
    override_description: str
    natural_score: int
    final_score: int


class SnapshotOut(BaseModel):
    """评分快照。"""
    model_config = ConfigDict(from_attributes=True)
    id: int
    total_score: int
    grade: str
    # v0.2:同时返回自然分(未 override)和最终分(各维度 dimension_N_score)
    # 历史 v0.1 快照这 5 字段为 NULL,前端等价 '无 override'
    dimension_1_natural_score: int | None = None
    dimension_2_natural_score: int | None = None
    dimension_3_natural_score: int | None = None
    dimension_4_natural_score: int | None = None
    dimension_overrides: list[DimensionOverrideHitOut] | None = None
    rule_version: int
    trigger_type: str
    ai_summary: str | None = None
    ai_summary_generated_at: datetime | None = None
    is_current: bool
    calculated_at: datetime


class CompanyDetailOut(BaseModel):
    """详情页响应。"""
    id: int
    name: str
    legal_name_en: str | None = None
    country_code: str
    registration_no: str | None = None
    snapshot: SnapshotOut | None = None
    dimensions: list[DimensionOut] = Field(default_factory=list)
    details: list[ScoreDetailOut] = Field(default_factory=list)
    basic: BasicDataOut | None = None
    finance: FinanceDataOut | None = None
    legal: LegalDataOut | None = None
    certifications: list[CertificationOut] = Field(default_factory=list)
    # Δ7/Δ8:抓取/评分状态(前端骨架屏依赖);非 KH 公司恒为 ready
    # 值域:pending / ready / empty / failed
    #   empty = 抓取成功完成但公开源 0 命中,无评分快照(Δ8 新增)
    evaluation_status: str = "ready"
    latest_harvest_run: dict[str, Any] | None = None


# =============================================================================
# 搜索历史
# =============================================================================

class SearchHistoryItem(BaseModel):
    id: int
    company_id: int
    company_name: str
    country_code: str
    grade: str | None = None
    searched_at: datetime


# =============================================================================
# AI 会话
# =============================================================================

class AiConversationCreateIn(BaseModel):
    company_id: int


class AiMessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    role: str
    content: str
    sequence: int
    created_at: datetime


class AiConversationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    user_id: int
    company_id: int
    started_at: datetime
    messages: list[AiMessageOut] = Field(default_factory=list)


class AiMessageSendIn(BaseModel):
    content: str = Field(..., min_length=1, max_length=2000)


# =============================================================================
# 触发详情(写入 score_snapshot.trigger_detail)
# =============================================================================

class TriggerDetail(BaseModel):
    """评分触发上下文(放进 trigger_detail JSONB)。"""
    actor_user_id: int | None = None
    actor_email: str | None = None
    source: str | None = None  # api / seed / batch / event
    extra: dict[str, Any] | None = None
