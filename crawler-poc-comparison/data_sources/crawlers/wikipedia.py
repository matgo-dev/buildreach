"""工商基础爬虫 · Wikipedia REST summary API(降级链第 3 级,v1.2)。

v1.2 修复:原方案抓 /wiki/ HTML,被 Wikipedia 反爬 403。改用公开 REST API
(/api/rest_v1/page/summary/{title}),返回结构化 JSON、无反爬;并加命中校验
防匹配到无关/同名词条。注意:summary 不含 infobox,只能拿到标题(全称)+ 国别。
"""
from __future__ import annotations

import time
from urllib.parse import quote

import httpx

from data_sources.crawlers.base import name_match
from schemas import BasicFields, BasicResult


class WikipediaCrawler:
    SOURCE_NAME = "en.wikipedia.org"
    API = "https://en.wikipedia.org/api/rest_v1/page/summary"
    _HEADERS = {
        # Wikimedia UA 策略(https://meta.wikimedia.org/wiki/User-Agent_policy):
        # UA 必须标识工具并带联系方式(URL + email),否则 REST API 返回 403。
        "User-Agent": (
            "overseas-supply-poc/1.0 "
            "(https://github.com/tutu6/overseas-platform-v0.1; poc-research@example.com)"
        ),
        "Accept": "application/json",
    }

    async def fetch(self, company_name: str) -> BasicResult:
        start = time.time()
        def ms() -> int:
            return int((time.time() - start) * 1000)

        title = quote(company_name.replace(" ", "_"), safe="")
        url = f"{self.API}/{title}"
        try:
            async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
                resp = await client.get(url, headers=self._HEADERS)
                if resp.status_code == 404:
                    return BasicResult(
                        source=self.SOURCE_NAME, status="no_match", fields=BasicFields(),
                        fields_filled=0, source_url=url, http_status_code=404,
                        duration_ms=ms(), error_detail="无对应词条",
                    )
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPStatusError as exc:
            code = exc.response.status_code
            status = "access_restricted" if code in (401, 403) else "error"
            return BasicResult(
                source=self.SOURCE_NAME, status=status, fields=BasicFields(),
                fields_filled=0, source_url=url, http_status_code=code,
                duration_ms=ms(), error_detail=f"HTTP {code}",
            )
        except httpx.HTTPError as exc:
            return BasicResult(
                source=self.SOURCE_NAME, status="error", fields=BasicFields(),
                fields_filled=0, source_url=url, duration_ms=ms(),
                error_detail=str(exc)[:300],
            )

        # 消歧义页 → 非具体企业,视为未命中
        if data.get("type") == "disambiguation":
            return BasicResult(
                source=self.SOURCE_NAME, status="no_match",
                fields=BasicFields(country_region="Cambodia"), fields_filled=1,
                source_url=url, duration_ms=ms(), error_detail="消歧义页,非具体企业",
            )

        page_title = data.get("title")
        # 命中校验:词条标题须与查询名近似,防匹配到无关词条(如缩写撞名)
        if not page_title or not name_match(company_name, page_title):
            return BasicResult(
                source=self.SOURCE_NAME, status="no_match",
                fields=BasicFields(country_region="Cambodia"), fields_filled=1,
                source_url=url, duration_ms=ms(),
                error_detail=(f"词条 '{page_title}' 与查询不匹配" if page_title else None),
            )

        page_url = ((data.get("content_urls") or {}).get("desktop") or {}).get("page") or url
        fields = BasicFields(company_full_name=page_title, country_region="Cambodia")
        filled = sum(1 for v in fields.model_dump().values() if v is not None)
        return BasicResult(
            source=self.SOURCE_NAME, status="ok" if filled > 1 else "no_match",
            fields=fields, fields_filled=filled, source_url=page_url, duration_ms=ms(),
        )
