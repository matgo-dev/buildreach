"""Δ7 harvester 测试共享 fake(下划线前缀,pytest 不收集为测试)。v0.3。"""
from __future__ import annotations

import json
from pathlib import Path

from app.services.credit.harvester import public_web_harvester as _pwh
from app.services.credit.harvester.public_web_harvester import FieldEvidence, HarvestResult
from app.services.credit.harvester.tavily_client import TavilyError, TavilySearchResult
from app.services.llm.base import LLMUnavailableError

PROMPTS_ROOT = Path(_pwh.__file__).parent / "prompts"


def tavily_result(url: str = "https://x", title: str = "t", content: str = "some context text"):
    return TavilySearchResult(title=title, url=url, content=content)


class FakeTavily:
    """记录每次调用参数(query/include_domains/country);返回 default 或按调用序列。"""

    def __init__(self, results=None, raise_error=False, results_by_call=None):
        self._default = results if results is not None else [tavily_result()]
        self._raise = raise_error
        self._results_by_call = results_by_call  # list[list[TavilySearchResult]] 按调用次序
        self.calls: list[dict] = []

    async def search(self, query, max_results=5, search_depth="basic",
                     include_domains=None, country=None):
        self.calls.append({"query": query, "include_domains": include_domains, "country": country})
        if self._raise:
            raise TavilyError("boom")
        if self._results_by_call is not None:
            i = len(self.calls) - 1
            return self._results_by_call[i] if i < len(self._results_by_call) else []
        return self._default


class FakeLLM:
    def __init__(self, response="{}", raise_error=False):
        self._response = response
        self._raise = raise_error
        self.calls = 0

    async def generate_json(self, prompt, *, timeout_seconds=None):
        self.calls += 1
        if self._raise:
            raise LLMUnavailableError("down")
        return self._response


def ev(quote: str, source_index: int = 0) -> dict:
    """构造 v0.3 字段证据对象(LLM 输出形态)。"""
    return {"quote": quote, "source_index": source_index}


def basic_json(*, confidence: str = "low", **fields) -> str:
    """构造 basic 维度 LLM 应答 JSON(v0.3:_evidence 为对象 {quote,source_index})。

    用法:basic_json(established_date="2008-04-15", _evidence={"established_date": ev("...", 0)})
    """
    payload = {
        "established_date": None, "registered_capital": None, "business_scope": None,
        "legal_representative": None, "shareholders": None, "status_text": None,
        "address": None, "website": None, "_evidence": {}, "_confidence": confidence,
    }
    payload.update(fields)
    return json.dumps(payload)


def make_result(status="ok", data_source="public", extracted=None, *, evidence=None,
                error=None, queries=None, tavily_results=None) -> HarvestResult:
    """构造 HarvestResult(harvest_task 集成测试用)。"""
    return HarvestResult(
        status=status, data_source=data_source, extracted=extracted or {},
        raw_llm_response="{}",
        evidence=evidence or {},
        confidence="high",
        tavily_calls=0 if status == "failed" else 1,
        llm_calls=0 if status == "failed" else 1,
        tavily_results=(
            tavily_results if tavily_results is not None
            else [{"url": "https://x", "title": "t", "content": "c"}]
        ),
        queries=queries or ["q"],
        error=error,
    )


class FakeHarvester:
    """直接返回预设 HarvestResult,绕过 Tavily/LLM。"""

    def __init__(self, basic, finance, legal, qual):
        self._b, self._f, self._l, self._q = basic, finance, legal, qual

    async def harvest_basic(self, *a, **k):
        return self._b

    async def harvest_finance(self, *a, **k):
        return self._f

    async def harvest_legal(self, *a, **k):
        return self._l

    async def harvest_qualifications(self, *a, **k):
        return [self._q]


class RaisingHarvester:
    """任何方法被调用即失败 — 验证缓存命中路径不触发抓取。"""

    async def harvest_basic(self, *a, **k):
        raise AssertionError("harvester 不应在缓存命中时被调用")

    harvest_finance = harvest_basic
    harvest_legal = harvest_basic
    harvest_qualifications = harvest_basic
