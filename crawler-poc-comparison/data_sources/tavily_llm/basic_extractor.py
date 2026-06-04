"""工商基础 · Tavily + LLM 抽取器(裸调版)。"""
from __future__ import annotations

import json
import time
from pathlib import Path

from cache import get_cache
from config import settings
from data_sources.tavily_llm.llm_client import llm_extract_json
from data_sources.tavily_llm.tavily_client import tavily_search
from schemas import BasicFields, BasicResult

_PROMPTS = Path(__file__).parent / "prompts"


def _load_prompt(name: str) -> str:
    return (_PROMPTS / name).read_text(encoding="utf-8")


def _ms(start: float) -> int:
    return int((time.time() - start) * 1000)


async def extract_basic_via_tavily_llm(company_name: str) -> BasicResult:
    cache = get_cache()
    cached = cache.get("basic_tavily", company_name)
    if cached:
        r = BasicResult(**cached)
        r.cache_hit = True
        return r

    start = time.time()
    # 1. Tavily 搜索 + 2. LLM 抽取(任一步上游失败 → status=error)
    try:
        query = f'"{company_name}" Cambodia company registration MOC'
        results = await tavily_search(settings.TAVILY_API_KEY, query, max_results=5)
        context = "\n\n".join(
            f"[{i}] URL: {r.url}\n标题: {r.title}\n内容: {r.content}"
            for i, r in enumerate(results)
        )
        # prompt 含 JSON 示例花括号,必须用 replace 而非 format
        prompt = (
            _load_prompt("basic.txt")
            .replace("{company_name}", company_name)
            .replace("{search_context}", context)
        )
        raw = await llm_extract_json(
            settings.QWEN_API_KEY, settings.QWEN_API_URL, settings.QWEN_MODEL, prompt
        )
    except Exception as exc:  # noqa: BLE001 — PoC 诚实记录上游失败
        return BasicResult(
            source="tavily_llm", status="error", fields=BasicFields(),
            fields_filled=0, duration_ms=_ms(start), error_detail=str(exc)[:300],
        )

    # 3. 解析 JSON → BasicFields
    try:
        extracted = json.loads(raw)
        fields = BasicFields(**{k: extracted.get(k) for k in BasicFields.model_fields})
    except Exception as exc:  # noqa: BLE001
        return BasicResult(
            source="tavily_llm", status="parse_error", fields=BasicFields(),
            fields_filled=0, duration_ms=_ms(start),
            error_detail=str(exc)[:200], raw_snippet=raw[:500],
        )

    filled = sum(1 for v in fields.model_dump().values() if v is not None)
    result = BasicResult(
        source="tavily_llm",
        status="ok" if filled > 0 else "no_match",
        fields=fields,
        fields_filled=filled,
        source_url=results[0].url if results else None,
        duration_ms=_ms(start),
        cache_hit=False,
    )
    cache.set("basic_tavily", company_name, result.model_dump())
    return result
