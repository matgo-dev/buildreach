"""工商基础爬虫 · 柬埔寨 MOC 官网(businessregistration.moc.gov.kh)。

实施探索(工单 §Step9):MOC 官网很可能需登录 / JS 渲染 / 反爬。
本实现尝试直接访问搜索入口,按真实失败情况标 status(blocked/not_found/parse_failed),
不切 Playwright,失败即记录 —— 这本身是 PoC 的有效产出。
"""
from __future__ import annotations

import time
from urllib.parse import quote

from bs4 import BeautifulSoup

from data_sources.crawlers.base import CrawlerError, fetch_html, parse_date_loose
from schemas import BasicFields, BasicResult


class MocCambodiaCrawler:
    SOURCE_NAME = "moc.gov.kh"
    BASE_URL = "https://www.businessregistration.moc.gov.kh"

    async def fetch(self, company_name: str) -> BasicResult:
        start = time.time()
        # 尝试公开搜索入口(实际 pattern 未知,先试常见路径)
        url = f"{self.BASE_URL}/?companyName={quote(company_name)}"
        try:
            html = await fetch_html(url, timeout=20)
        except CrawlerError as exc:
            msg = str(exc)
            code = exc.status_code
            status = "access_restricted" if code in (401, 403) else (
                "timeout" if "timeout" in msg.lower() else "error"
            )
            return BasicResult(
                source="crawler_moc", status=status, fields=BasicFields(),
                fields_filled=0, source_url=self.BASE_URL, http_status_code=code,
                duration_ms=int((time.time() - start) * 1000),
                error_detail=msg[:300],
            )

        # 拿到 HTML:探测是否登录页 / JS 占位 / 真实数据
        soup = BeautifulSoup(html, "lxml")
        lowered = html.lower()
        if any(k in lowered for k in ("login", "sign in", "log in")) and "password" in lowered:
            return BasicResult(
                source="crawler_moc", status="access_restricted", fields=BasicFields(),
                fields_filled=0, source_url=url,
                duration_ms=int((time.time() - start) * 1000),
                error_detail="疑似重定向到登录页(页面含登录表单)",
                raw_snippet=html[:500],
            )
        # SPA / JS 渲染探测:body 几乎无文本但有 app 挂载点
        body_text = soup.get_text(strip=True)
        if len(body_text) < 200 and soup.select_one("#root, #app, [ng-app]"):
            return BasicResult(
                source="crawler_moc", status="access_restricted", fields=BasicFields(),
                fields_filled=0, source_url=url,
                duration_ms=int((time.time() - start) * 1000),
                error_detail="疑似 JS 渲染 SPA(需 Playwright,PoC 不切)",
                raw_snippet=html[:500],
            )

        # 尝试解析公司信息(MOC DOM 未知 → 解析不到则 not_found,留 raw_snippet 供人工核对)
        fields = BasicFields(country_region="Cambodia")
        filled = sum(1 for v in fields.model_dump().values() if v is not None)
        return BasicResult(
            source="crawler_moc",
            status="no_match",  # 未能从公开页面解析出结构化字段
            fields=fields,
            fields_filled=filled,
            source_url=url,
            duration_ms=int((time.time() - start) * 1000),
            error_detail="页面可访问但未解析到工商字段(MOC 公开页无结构化数据 / DOM 未适配)",
            raw_snippet=html[:500],
        )
