"""通用公开网络数据抓取(Δ7 v0.3)。

Tavily 搜索(country boost + 域名白名单两阶段)+ LLM 结构化抽取 + 源字段追溯反幻觉。
落库 / 触发评分由 harvest_task 负责,本类只产出结构化 HarvestResult。

v0.3 相对 v0.2:
- evidence 从 {field: "quote 字符串"} 升级为 {field: FieldEvidence(quote, source_index, source_url)}
- search_context 带 [N] 索引,LLM 输出 source_index 与之对齐;后处理按 index 反查 URL
- 反幻觉新增:source_index 越界 / quote 与来源 content fuzzy 匹配过低 → 字段 null 化
- 搜索:白名单硬过滤优先,结果不足阈值时全网兜底
"""
from __future__ import annotations

import json
import logging
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, ValidationError

from app.services.credit.harvester.country_mapping import get_tavily_country
from app.services.credit.harvester.domain_whitelist import load_whitelist
from app.services.credit.harvester.schemas import (
    BasicExtractedSchema,
    CertificationExtractedSchema,
    FinanceExtractedSchema,
    LegalExtractedSchema,
)
from app.services.credit.harvester.tavily_client import (
    TavilyClient,
    TavilyError,
    TavilySearchResult,
)
from app.services.llm.base import LLMService, LLMUnavailableError

logger = logging.getLogger(__name__)

# 反幻觉:source_quote 最小有效长度(< 此长度视为无效引用)
MIN_QUOTE_LEN = 10

# 国别 ISO-2 → 英文名(拼搜索 query 用)
COUNTRY_NAMES: dict[str, str] = {"KH": "Cambodia"}

# 各维度搜索 query 模板
_QUERY_TEMPLATES: dict[str, str] = {
    "basic": '"{name}" {regno} {country} company registration',
    "finance": '"{name}" {country} annual report revenue financial',
    "legal": '"{name}" {country} lawsuit court litigation',
    "qualification": '"{name}" {country} ISO certification standard',
}

# 各维度参与"反幻觉 null 化"的数据字段(不含 evidence/confidence/notes 元字段)
_DATA_FIELDS: dict[str, list[str]] = {
    "basic": [
        "established_date", "registered_capital", "business_scope",
        "legal_representative", "shareholders", "status_text", "address", "website",
    ],
    "finance": ["revenue_trend", "debt_ratio", "cash_flow_status"],
    "legal": [
        "litigation_count", "defaulter_unresolved_count",
        "defaulter_resolved_count", "negative_news_level",
    ],
    "qualification": [
        "has_iso_9001", "has_iso_14001", "has_iso_45001",
        "has_isc_certification", "other_certifications",
    ],
}

# 维度主数据来源标记(status != missing 时用)
_DIMENSION_SOURCE: dict[str, str] = {
    "basic": "public",
    "finance": "public",
    "legal": "media",
    "qualification": "public",
}

_SCHEMA_BY_DIM: dict[str, type[BaseModel]] = {
    "basic": BasicExtractedSchema,
    "finance": FinanceExtractedSchema,
    "legal": LegalExtractedSchema,
    "qualification": CertificationExtractedSchema,
}


class FieldEvidence(BaseModel):
    """单字段证据(后处理后的完整形态,含反查的 source_url)。"""
    quote: str | None = None
    source_index: int | None = None
    source_url: str | None = None


class HarvestResult(BaseModel):
    """单维度抓取结果。"""
    status: str  # ok / partial / missing / failed
    data_source: str  # public / media / missing
    extracted: dict[str, Any]
    raw_llm_response: str
    evidence: dict[str, FieldEvidence] = Field(default_factory=dict)  # v0.3 对象形态
    confidence: str | None
    tavily_calls: int
    llm_calls: int
    tavily_results: list[dict[str, Any]] = []  # Tavily 原始结果,落 raw_data 留存
    queries: list[str] = Field(default_factory=list)  # v0.3 留存搜索 query
    error: str | None = None


def _has_value(v: Any) -> bool:
    """None / 空字符串 / 空列表 视为"无值"。"""
    if v is None:
        return False
    if isinstance(v, (list, str)) and len(v) == 0:
        return False
    return True


def _build_search_context(results: list[TavilySearchResult]) -> str:
    """拼接 Tavily 结果为带 [N] 索引的文本块,索引与 LLM 输出的 source_index 对齐。"""
    blocks = []
    for idx, r in enumerate(results):
        blocks.append(
            f"[{idx}] 来源: {r.url}\n    标题: {r.title}\n    内容: {r.content}"
        )
    return "\n\n".join(blocks)


def _fuzzy_match_ratio(quote: str | None, content: str | None) -> float:
    """quote 在 content 中的最长公共子串长度占 quote 长度的比例(工单选项 C)。

    用于核对 LLM 给的 quote 确实出自它声称的来源 content,挡住张冠李戴 / 改写。
    """
    q = (quote or "").strip()
    c = content or ""
    if not q or not c:
        return 0.0
    block = SequenceMatcher(None, q, c).find_longest_match(0, len(q), 0, len(c))
    return block.size / len(q)


def _null_out(cleaned: dict[str, Any], field: str) -> None:
    """list 字段置空数组,其余置 None。"""
    cleaned[field] = [] if isinstance(cleaned.get(field), list) else None


def _validate_and_resolve_evidence(
    extracted: dict[str, Any],
    evidence_raw: dict[str, Any],
    tavily_results: list[TavilySearchResult],
    data_fields: list[str],
    fuzzy_threshold: float,
) -> tuple[dict[str, Any], dict[str, FieldEvidence]]:
    """反幻觉后处理 + 源 URL 反查。

    对每个有值字段三重校验:quote 长度 ≥10、source_index 在范围、quote 与对应
    content fuzzy 匹配 ≥ 阈值。任一不过 → 字段 null 化;全过 → 反查填 source_url。
    """
    cleaned = dict(extracted)
    resolved: dict[str, FieldEvidence] = {}

    for field in data_fields:
        if not _has_value(cleaned.get(field)):
            continue
        ev = evidence_raw.get(field)
        if ev is None:
            _null_out(cleaned, field)
            continue
        # ev 是 FieldEvidenceSchema(model_validate 后);兼容 dict
        quote = getattr(ev, "quote", None) if not isinstance(ev, dict) else ev.get("quote")
        source_index = (
            getattr(ev, "source_index", None) if not isinstance(ev, dict) else ev.get("source_index")
        )

        # 校验 1:quote 长度
        if not quote or len(quote.strip()) < MIN_QUOTE_LEN:
            _null_out(cleaned, field)
            logger.warning("字段 %s 因 quote 过短被 null 化", field)
            continue
        # 校验 2:source_index 范围
        if not isinstance(source_index, int) or not (0 <= source_index < len(tavily_results)):
            _null_out(cleaned, field)
            logger.warning("字段 %s 的 source_index=%s 越界,被 null 化", field, source_index)
            continue
        # 校验 3:quote 与 source_index 指向的 content fuzzy 匹配
        content = tavily_results[source_index].content
        if _fuzzy_match_ratio(quote, content) < fuzzy_threshold:
            _null_out(cleaned, field)
            logger.warning("字段 %s 的 quote 与来源 content 匹配度过低,被 null 化", field)
            continue
        # 校验通过,反查 source_url
        resolved[field] = FieldEvidence(
            quote=quote,
            source_index=source_index,
            source_url=tavily_results[source_index].url,
        )

    return cleaned, resolved


def _judge_status(cleaned: dict[str, Any], data_fields: list[str]) -> str:
    non_null = [f for f in data_fields if _has_value(cleaned.get(f))]
    if not non_null:
        return "missing"
    if len(non_null) < len(data_fields):
        return "partial"
    return "ok"


class PublicWebHarvester:
    """通用工具:Tavily 搜索(白名单两阶段)+ qwen-plus 抽取 + 源追溯反幻觉。"""

    def __init__(
        self,
        tavily: TavilyClient,
        llm: LLMService,
        prompts_root: Path,
        *,
        max_results: int = 5,
        llm_timeout_seconds: int = 30,
        llm_retry: int = 1,
        fuzzy_threshold: float = 0.3,
        whitelist_fallback_threshold: int = 3,
    ) -> None:
        self._tavily = tavily
        self._llm = llm
        self._prompts_root = Path(prompts_root)
        self._max_results = max_results
        self._llm_timeout = llm_timeout_seconds
        self._llm_retry = llm_retry
        self._fuzzy_threshold = fuzzy_threshold
        self._whitelist_fallback_threshold = whitelist_fallback_threshold

    # ---- 公开维度入口 ----
    async def harvest_basic(
        self, company_name: str, country_code: str, registration_no: str | None
    ) -> HarvestResult:
        return await self._harvest("basic", company_name, registration_no, country_code)

    async def harvest_finance(
        self, company_name: str, country_code: str, registration_no: str | None
    ) -> HarvestResult:
        return await self._harvest("finance", company_name, registration_no, country_code)

    async def harvest_legal(
        self, company_name: str, country_code: str, registration_no: str | None
    ) -> HarvestResult:
        return await self._harvest("legal", company_name, registration_no, country_code)

    async def harvest_qualifications(
        self, company_name: str, country_code: str, registration_no: str | None
    ) -> list[HarvestResult]:
        # 证书维度本期单次抽取"是否拥有"类布尔;返回 list 以兼容未来多证书拆分
        result = await self._harvest(
            "qualification", company_name, registration_no, country_code
        )
        return [result]

    # ---- 内部 ----
    def _country(self, code: str) -> str:
        return COUNTRY_NAMES.get(code.upper(), code)

    def _build_query(
        self, dimension: str, name: str, country_code: str, regno: str | None
    ) -> str:
        return _QUERY_TEMPLATES[dimension].format(
            name=name, regno=regno or "", country=self._country(country_code)
        ).replace("  ", " ").strip()

    def _load_prompt(self, country_code: str, dimension: str) -> str:
        path = self._prompts_root / country_code.lower() / f"{dimension}.txt"
        return path.read_text(encoding="utf-8")

    async def _search_two_stage(
        self, query: str, country_code: str, dimension: str
    ) -> tuple[list[TavilySearchResult], int, str | None]:
        """白名单硬过滤优先 + 全网兜底。

        返回 (results, tavily_calls, error)。任一阶段成功(即使空结果)→ error=None;
        所有阶段都抛 TavilyError → 返回 error(调用方据此判 failed)。
        """
        tavily_country = get_tavily_country(country_code)
        whitelist = load_whitelist(country_code, dimension)
        results: list[TavilySearchResult] = []
        calls = 0
        any_success = False
        last_error: str | None = None

        # 阶段 1:白名单硬过滤(有白名单才走)
        if whitelist:
            try:
                r1 = await self._tavily.search(
                    query, max_results=self._max_results,
                    country=tavily_country, include_domains=whitelist,
                )
                calls += 1
                any_success = True
                results.extend(r1)
            except TavilyError as exc:
                last_error = f"tavily(whitelist): {exc}"
                logger.warning("[harvest:%s] 白名单搜索失败: %s", dimension, exc)

        # 阶段 2:结果不足阈值(或无白名单)→ 全网兜底
        if len(results) < self._whitelist_fallback_threshold:
            try:
                r2 = await self._tavily.search(
                    query, max_results=self._max_results, country=tavily_country,
                )
                calls += 1
                any_success = True
                existing = {r.url for r in results}
                for r in r2:
                    if r.url not in existing:
                        results.append(r)
            except TavilyError as exc:
                last_error = f"tavily(fallback): {exc}"
                logger.warning("[harvest:%s] 全网兜底搜索失败: %s", dimension, exc)

        return results, calls, (None if any_success else last_error)

    async def _harvest(
        self,
        dimension: str,
        company_name: str,
        registration_no: str | None,
        country_code: str,
    ) -> HarvestResult:
        query = self._build_query(dimension, company_name, country_code, registration_no)
        schema_cls = _SCHEMA_BY_DIM[dimension]

        # 1. 两阶段搜索
        results, tavily_calls, search_error = await self._search_two_stage(
            query, country_code, dimension
        )
        if not results:
            # 有 error → Tavily 全失败(failed);无 error → 真实查无(missing)
            status = "failed" if search_error else "missing"
            return HarvestResult(
                status=status, data_source="missing", extracted={},
                raw_llm_response="", evidence={}, confidence=None,
                tavily_calls=tavily_calls, llm_calls=0,
                queries=[query], error=search_error,
            )
        search_context = _build_search_context(results)

        # 2. 加载 prompt 模板并替换占位
        try:
            template = self._load_prompt(country_code, dimension)
        except OSError as exc:
            logger.error("[harvest:%s] prompt 模板缺失: %s", dimension, exc)
            return HarvestResult(
                status="failed", data_source="missing", extracted={},
                raw_llm_response="", evidence={}, confidence=None,
                tavily_calls=tavily_calls, llm_calls=0,
                queries=[query], error=f"prompt: {exc}",
            )
        prompt = (
            template.replace("{company_name}", company_name)
            .replace("{registration_no}", registration_no or "")
            .replace("{search_context}", search_context)
        )

        # 3. LLM 结构化抽取(失败重试 llm_retry 次)
        raw: str | None = None
        last_err: Exception | None = None
        llm_calls = 0
        for _ in range(1 + self._llm_retry):
            try:
                raw = await self._llm.generate_json(prompt, timeout_seconds=self._llm_timeout)
                llm_calls += 1
                break
            except LLMUnavailableError as exc:
                last_err = exc
                llm_calls += 1
        if raw is None:
            return HarvestResult(
                status="failed", data_source="missing", extracted={},
                raw_llm_response="", evidence={}, confidence=None,
                tavily_calls=tavily_calls, llm_calls=llm_calls,
                queries=[query], error=f"llm: {last_err}",
            )

        # 4. JSON + schema 校验
        try:
            model = schema_cls.model_validate(json.loads(raw))
        except (json.JSONDecodeError, ValidationError) as exc:
            logger.warning("[harvest:%s] JSON/schema 校验失败: %s", dimension, exc)
            return HarvestResult(
                status="failed", data_source="missing", extracted={},
                raw_llm_response=raw, evidence={}, confidence=None,
                tavily_calls=tavily_calls, llm_calls=llm_calls,
                queries=[query], error=f"schema: {exc}",
            )

        # 5. 源追溯反幻觉后处理(quote 长度 + source_index 范围 + fuzzy 匹配 → 反查 URL)
        data_fields = _DATA_FIELDS[dimension]
        extracted = model.model_dump(exclude={"evidence", "confidence", "notes"})
        evidence_raw = getattr(model, "evidence", {}) or {}
        cleaned, resolved = _validate_and_resolve_evidence(
            extracted, evidence_raw, results, data_fields, self._fuzzy_threshold
        )
        status = _judge_status(cleaned, data_fields)
        data_source = "missing" if status == "missing" else _DIMENSION_SOURCE[dimension]
        return HarvestResult(
            status=status,
            data_source=data_source,
            extracted=cleaned,
            raw_llm_response=raw,
            evidence=resolved,
            confidence=getattr(model, "confidence", None),
            tavily_calls=tavily_calls,
            llm_calls=llm_calls,
            tavily_results=[r.model_dump() for r in results],
            queries=[query],
        )
