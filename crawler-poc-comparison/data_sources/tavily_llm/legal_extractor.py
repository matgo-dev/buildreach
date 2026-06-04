"""司法舆情 · Tavily + LLM 抽取器(裸调版)。"""
from __future__ import annotations

import json
import time
from datetime import date
from pathlib import Path

from cache import get_cache
from config import settings
from data_sources.tavily_llm.llm_client import llm_extract_json
from data_sources.tavily_llm.tavily_client import tavily_search
from schemas import LegalArticle, LegalResult

_PROMPTS = Path(__file__).parent / "prompts"


def _load_prompt(name: str) -> str:
    return (_PROMPTS / name).read_text(encoding="utf-8")


def _ms(start: float) -> int:
    return int((time.time() - start) * 1000)


def _parse_date(s) -> date | None:
    if not s or not isinstance(s, str):
        return None
    try:
        return date.fromisoformat(s.strip()[:10])
    except ValueError:
        return None


async def extract_legal_via_tavily_llm(company_name: str) -> LegalResult:
    cache = get_cache()
    cached = cache.get("legal_tavily", company_name)
    if cached:
        r = LegalResult(**cached)
        r.cache_hit = True
        return r

    start = time.time()
    try:
        query = f'"{company_name}" Cambodia lawsuit OR court OR scandal'
        results = await tavily_search(settings.TAVILY_API_KEY, query, max_results=5)
        context = "\n\n".join(
            f"[{i}] URL: {r.url}\n标题: {r.title}\n内容: {r.content}"
            for i, r in enumerate(results)
        )
        prompt = (
            _load_prompt("legal.txt")
            .replace("{company_name}", company_name)
            .replace("{search_context}", context)
        )
        raw = await llm_extract_json(
            settings.QWEN_API_KEY, settings.QWEN_API_URL, settings.QWEN_MODEL, prompt
        )
    except Exception as exc:  # noqa: BLE001
        return LegalResult(
            source="tavily_llm", status="error", article_count=0, negative_count=0,
            latest_published=None, articles=[], duration_ms=_ms(start),
            error_detail=str(exc)[:300],
        )

    try:
        data = json.loads(raw)
        articles = [
            LegalArticle(
                source_site="tavily_llm",
                title=a.get("title", ""),
                url=a.get("url", ""),
                published_date=_parse_date(a.get("published_date")),
                snippet=(a.get("snippet") or "")[:200],
                is_negative=bool(a.get("is_negative", False)),
            )
            for a in data.get("articles", [])
        ]
    except Exception as exc:  # noqa: BLE001
        return LegalResult(
            source="tavily_llm", status="parse_error", article_count=0,
            negative_count=0, latest_published=None, articles=[],
            duration_ms=_ms(start), error_detail=str(exc)[:200],
        )

    articles.sort(key=lambda a: a.published_date or date.min, reverse=True)
    neg = sum(1 for a in articles if a.is_negative)
    latest = next((a.published_date for a in articles if a.published_date), None)
    result = LegalResult(
        source="tavily_llm",
        status="ok" if articles else "no_match",
        article_count=len(articles),
        negative_count=neg,
        latest_published=latest,
        articles=articles,
        duration_ms=_ms(start),
        cache_hit=False,
    )
    cache.set("legal_tavily", company_name, result.model_dump())
    return result
