"""Tavily 搜索 API 封装(Δ7 Step 4)。httpx 异步调用。"""
from __future__ import annotations

import httpx
from pydantic import BaseModel


class TavilyError(Exception):
    """Tavily 调用失败(超时 / 鉴权 / 限流 / 服务端错误 / 未配置 key)。"""


class TavilySearchResult(BaseModel):
    title: str
    url: str
    content: str  # Tavily 返回的摘要
    score: float | None = None  # Tavily 相关性分数


class TavilyClient:
    """Tavily 搜索 API 封装。

    transport 参数仅用于单测注入 httpx.MockTransport;生产留 None。
    """

    def __init__(
        self,
        api_key: str,
        base_url: str,
        timeout: int = 15,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._transport = transport

    async def search(
        self,
        query: str,
        max_results: int = 5,
        search_depth: str = "basic",  # basic / advanced
        include_domains: list[str] | None = None,
        country: str | None = None,
    ) -> list[TavilySearchResult]:
        """Tavily 搜索。

        Tavily 参数行为(官方文档):
        - country: 软偏好(boost)。提升指定国家结果排序,不排除他国;取值为国家名小写
          (如 "cambodia",不是 ISO 码),仅 topic="general" 时生效。
        - include_domains: 硬过滤。仅返回白名单域名结果,上限 300 个域名。
        - 两者可叠加:在白名单域名内优先返回指定国家结果。
        """
        # fail-fast:没有 key 直接报错,不要静默发空请求
        if not self._api_key:
            raise TavilyError("TAVILY_API_KEY 未配置")

        payload: dict = {
            "api_key": self._api_key,
            "query": query,
            "max_results": max_results,
            "search_depth": search_depth,
            "include_answer": False,
            "include_raw_content": False,
        }
        if include_domains:
            payload["include_domains"] = include_domains
        if country:
            payload["country"] = country

        try:
            async with httpx.AsyncClient(
                timeout=self._timeout, transport=self._transport
            ) as client:
                resp = await client.post(f"{self._base_url}/search", json=payload)
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPStatusError as exc:
            raise TavilyError(f"Tavily HTTP {exc.response.status_code}") from exc
        except httpx.HTTPError as exc:
            raise TavilyError(f"Tavily 请求失败: {exc}") from exc

        results = data.get("results") or []
        return [
            TavilySearchResult(
                title=r.get("title", ""),
                url=r.get("url", ""),
                content=r.get("content", ""),
                score=r.get("score"),
            )
            for r in results
        ]
