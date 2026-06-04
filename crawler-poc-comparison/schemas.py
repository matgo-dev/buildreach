"""Pydantic 模型(字段对齐 PRD §Δ10)。"""
from __future__ import annotations

from datetime import date

from pydantic import BaseModel


# ---------- 工商基础 ----------

class BasicFields(BaseModel):
    """工商基础字段(对齐 PRD §Δ10,7 字段)。"""
    company_full_name: str | None = None
    country_region: str | None = None
    registration_no: str | None = None
    established_date: date | None = None
    legal_representative: str | None = None
    business_scope: str | None = None
    registered_capital: str | None = None


class AttemptRecord(BaseModel):
    """爬虫降级链中单次尝试的记录(v1.2)。"""
    source: str
    status: str  # ok / access_restricted / no_match / parse_error / timeout / error
    duration_ms: int
    http_status_code: int | None = None
    error_detail: str | None = None


class BasicResult(BaseModel):
    """工商基础单源结果。"""
    source: str  # tavily_llm / crawler_chain(v1.2 爬虫侧固定为降级链)
    # ok / access_restricted / no_match / parse_error / timeout / error
    status: str
    fields: BasicFields
    fields_filled: int
    fields_total: int = 7
    source_url: str | None = None
    duration_ms: int
    cache_hit: bool = False
    error_detail: str | None = None
    raw_snippet: str | None = None  # 失败现场(HTML 片段或 LLM 应答前 500 字)
    http_status_code: int | None = None  # v1.2:单源 HTTP 状态码
    hit_source: str | None = None        # v1.2:降级链实际命中的源(Tavily 侧 None)
    attempts: list[AttemptRecord] = []   # v1.2:降级链尝试轨迹(Tavily 侧空)


# ---------- 司法舆情 ----------

class LegalArticle(BaseModel):
    source_site: str  # phnompenhpost / khmertimes / tavily_llm
    title: str
    url: str
    published_date: date | None = None
    snippet: str
    is_negative: bool


class LegalResult(BaseModel):
    """司法舆情单源结果。"""
    source: str  # tavily_llm / crawler_media
    # ok / access_restricted / no_match / parse_error / timeout / error
    status: str
    article_count: int
    negative_count: int
    latest_published: date | None
    articles: list[LegalArticle]
    duration_ms: int
    cache_hit: bool = False
    error_detail: str | None = None


# ---------- 顶层响应 ----------

class OverlapAnalysis(BaseModel):
    """司法舆情两路召回 URL 重合度分析(v1.1)。"""
    tavily_total: int
    crawler_total: int
    overlap_count: int
    overlap_urls: list[str]
    tavily_only_urls: list[str]
    crawler_only_urls: list[str]


class LegalResultWithOverlap(BaseModel):
    legal_tavily: LegalResult
    legal_crawler: LegalResult
    overlap: OverlapAnalysis


class ComparisonResponse(BaseModel):
    """页面查询的顶层响应(4 路并发结果)。"""
    company_name: str
    basic_tavily: BasicResult
    basic_crawler: BasicResult
    legal: LegalResultWithOverlap  # v1.1:两路 + 重合度(替代原 legal_tavily/legal_crawler)
