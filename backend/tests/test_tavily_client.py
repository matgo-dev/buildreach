"""TavilyClient 单测(Δ7 Step 4)。httpx.MockTransport 拦截,不真连网络。"""
from __future__ import annotations

import json

import httpx
import pytest

from app.services.credit.harvester.tavily_client import TavilyClient, TavilyError


async def test_search_builds_payload_and_parses_results():
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"results": [
            {"title": "ACME", "url": "https://x", "content": "info", "score": 0.9},
            {"title": "B", "url": "https://y", "content": "c2"},
        ]})

    client = TavilyClient(
        "k", "https://api.tavily.com", transport=httpx.MockTransport(handler)
    )
    out = await client.search("q1", max_results=3)

    assert captured["path"] == "/search"
    assert captured["body"]["api_key"] == "k"
    assert captured["body"]["query"] == "q1"
    assert captured["body"]["max_results"] == 3
    assert captured["body"]["include_answer"] is False
    assert len(out) == 2
    assert out[0].title == "ACME" and out[0].score == 0.9
    assert out[1].score is None


async def test_search_no_key_raises():
    client = TavilyClient("", "https://api.tavily.com")
    with pytest.raises(TavilyError):
        await client.search("q")


async def test_search_http_error_raises_tavily_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"error": "rate limit"})

    client = TavilyClient(
        "k", "https://api.tavily.com", transport=httpx.MockTransport(handler)
    )
    with pytest.raises(TavilyError):
        await client.search("q")


async def test_search_empty_results():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"results": []})

    client = TavilyClient(
        "k", "https://api.tavily.com", transport=httpx.MockTransport(handler)
    )
    assert await client.search("q") == []
