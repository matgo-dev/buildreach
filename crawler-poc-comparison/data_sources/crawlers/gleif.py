"""工商基础爬虫 · GLEIF LEI API(降级链第 4 级,v1.2)。REST JSON,无需 DOM。"""
from __future__ import annotations

import time

import httpx

from data_sources.crawlers.base import name_match
from schemas import BasicFields, BasicResult


class GleifApiCrawler:
    SOURCE_NAME = "api.gleif.org"
    BASE_URL = "https://api.gleif.org/api/v1"

    async def fetch(self, company_name: str) -> BasicResult:
        start = time.time()
        def ms() -> int:
            return int((time.time() - start) * 1000)

        url = f"{self.BASE_URL}/lei-records"
        params = {
            "filter[entity.legalName]": company_name,
            "filter[entity.legalAddress.country]": "KH",
        }
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                resp = await client.get(
                    url, params=params, headers={"Accept": "application/vnd.api+json"}
                )
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPStatusError as exc:
            return BasicResult(
                source=self.SOURCE_NAME, status="error", fields=BasicFields(),
                fields_filled=0, source_url=url, http_status_code=exc.response.status_code,
                duration_ms=ms(), error_detail=f"HTTP {exc.response.status_code}",
            )
        except httpx.HTTPError as exc:
            return BasicResult(
                source=self.SOURCE_NAME, status="error", fields=BasicFields(),
                fields_filled=0, source_url=url, duration_ms=ms(), error_detail=str(exc)[:300],
            )

        records = data.get("data", [])
        if not records:
            return BasicResult(
                source=self.SOURCE_NAME, status="no_match",
                fields=BasicFields(country_region="Cambodia"), fields_filled=1,
                source_url=url, duration_ms=ms(),
            )
        entity = (records[0].get("attributes") or {}).get("entity") or {}
        name = (entity.get("legalName") or {}).get("name")
        # 命中校验:GLEIF filter 是模糊匹配,可能返回不相关公司(查 T.S SPORT 命中 F.U.G.I GOLD)。
        # 返回名必须与查询名近似,否则视为未命中,防张冠李戴。
        if not name or not name_match(company_name, name):
            return BasicResult(
                source=self.SOURCE_NAME, status="no_match",
                fields=BasicFields(country_region="Cambodia"), fields_filled=1,
                source_url=url, duration_ms=ms(),
                error_detail=(f"GLEIF 返回 '{name}' 与查询不匹配,判未命中" if name else None),
            )
        fields = BasicFields(company_full_name=name, country_region="Cambodia")
        filled = sum(1 for v in fields.model_dump().values() if v is not None)
        return BasicResult(
            source=self.SOURCE_NAME, status="ok" if filled > 1 else "no_match",
            fields=fields, fields_filled=filled, source_url=url, duration_ms=ms(),
        )
