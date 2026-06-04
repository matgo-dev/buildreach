"""Tavily Search API 裸调(不复用主项目 Δ7 代码)。"""
from __future__ import annotations

import httpx
from pydantic import BaseModel


class TavilyResult(BaseModel):
    title: str = ""
    url: str = ""
    content: str = ""
    score: float | None = None


async def tavily_search(
    api_key: str,
    query: str,
    max_results: int = 5,
    country: str | None = "cambodia",
    timeout: float = 20.0,
) -> list[TavilyResult]:
    """裸调 Tavily Search API。失败抛 httpx 异常(由调用方捕获)。"""
    body: dict = {
        "api_key": api_key,
        "query": query,
        "max_results": max_results,
        "search_depth": "advanced",  # advanced 返回更长 content,LLM 抽字段命中率更高(2 credits/次)
        "include_answer": False,
    }
    if country:
        body["country"] = country
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post("https://api.tavily.com/search", json=body)
        resp.raise_for_status()
        data = resp.json()
    return [TavilyResult(**r) for r in data.get("results", [])]
