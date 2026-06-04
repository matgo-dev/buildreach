"""工商基础爬虫 · OpenCorporates(降级链第 2 级,v1.2)。

v1.2 修复:URL 模式更正为 /companies/kh?q=...(kh 是 path 而非 query 参数);
带 cookie_consent header;搜索结果取第一条 /companies/kh/ 链接,注册号从 href 尾部取;
详情页 "Please log in" 占位视为 null;命中校验防搜到不相关公司。
"""
from __future__ import annotations

import time
from urllib.parse import quote

from bs4 import BeautifulSoup

from data_sources.crawlers.base import CrawlerError, fetch_html, name_match
from schemas import BasicFields, BasicResult

_CONSENT = {"Cookie": "cookie_consent=accepted"}


class OpenCorporatesCrawler:
    SOURCE_NAME = "opencorporates.com"
    BASE_URL = "https://opencorporates.com"

    async def fetch(self, company_name: str) -> BasicResult:
        start = time.time()
        def ms() -> int:
            return int((time.time() - start) * 1000)

        # kh 作为 path 一部分,不是 jurisdiction_code query 参数
        url = f"{self.BASE_URL}/companies/kh?q={quote(company_name)}"
        try:
            html = await fetch_html(url, extra_headers=_CONSENT)
        except CrawlerError as exc:
            return _err(self.SOURCE_NAME, exc, url, ms())

        # OpenCorporates 用 HAProxy/JS 挑战页拦非浏览器客户端(返回 200 但实为 captcha 页)。
        # 诚实标 access_restricted,不要误报成"搜了没结果"(no_match)。
        lowered = html.lower()
        if len(html) < 3000 and ("challenge" in lowered or "captcha" in lowered):
            return BasicResult(
                source=self.SOURCE_NAME, status="access_restricted",
                fields=BasicFields(country_region="Cambodia"), fields_filled=1,
                source_url=url, duration_ms=ms(),
                error_detail="HAProxy/JS 挑战页(需浏览器执行 JS,PoC 不引入 Playwright)",
                raw_snippet=html[:300],
            )

        soup = BeautifulSoup(html, "lxml")
        link = soup.select_one("a[href^='/companies/kh/']")
        if not link:
            return BasicResult(
                source=self.SOURCE_NAME, status="no_match",
                fields=BasicFields(country_region="Cambodia"), fields_filled=1,
                source_url=url, duration_ms=ms(), raw_snippet=html[:300],
            )

        matched_name = link.get_text(strip=True)
        # 命中校验:搜索首条须与查询名近似,防搜到不相关公司(张冠李戴)
        if not name_match(company_name, matched_name):
            return BasicResult(
                source=self.SOURCE_NAME, status="no_match",
                fields=BasicFields(country_region="Cambodia"), fields_filled=1,
                source_url=url, duration_ms=ms(),
                error_detail=f"搜索首条 '{matched_name}' 与查询不匹配",
            )

        detail_path = link.get("href", "")
        registration_no = detail_path.rsplit("/", 1)[-1] or None  # 如 /companies/kh/00003077
        detail_url = self.BASE_URL + detail_path

        # 详情页补充字段(成立日期/董事多需登录,本期能拿啥拿啥;失败不影响已有全称+注册号)
        business_scope = None
        try:
            dhtml = await fetch_html(detail_url, extra_headers=_CONSENT)
            ds = BeautifulSoup(dhtml, "lxml")
            h1 = ds.select_one("h1")
            if h1 and h1.get_text(strip=True):
                matched_name = h1.get_text(strip=True)
            business_scope = _extract_field(ds, "Company Type")
        except CrawlerError:
            pass

        fields = BasicFields(
            company_full_name=matched_name,
            country_region="Cambodia",
            registration_no=registration_no,
            business_scope=business_scope,
        )
        filled = sum(1 for v in fields.model_dump().values() if v is not None)
        return BasicResult(
            source=self.SOURCE_NAME, status="ok" if filled > 1 else "no_match",
            fields=fields, fields_filled=filled, source_url=detail_url, duration_ms=ms(),
        )


def _extract_field(soup: BeautifulSoup, label: str) -> str | None:
    """按 label 文本找相邻值;'Please log in' 占位视为 null。"""
    for dt in soup.select("dt, th, .attribute_label"):
        if label.lower() in dt.get_text(strip=True).lower():
            val = dt.find_next_sibling(["dd", "td"]) or dt.find_next(["dd", "td"])
            if val:
                text = val.get_text(" ", strip=True)
                if "please log in" in text.lower():
                    return None
                return text or None
    return None


def _err(source: str, exc: CrawlerError, url: str, ms: int) -> BasicResult:
    status = "access_restricted" if exc.status_code in (401, 403) else (
        "timeout" if "timeout" in str(exc).lower() else "error"
    )
    return BasicResult(
        source=source, status=status, fields=BasicFields(), fields_filled=0,
        source_url=url, http_status_code=exc.status_code, duration_ms=ms,
        error_detail=str(exc)[:300],
    )
