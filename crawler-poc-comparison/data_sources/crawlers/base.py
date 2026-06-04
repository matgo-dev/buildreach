"""爬虫基类 + 共享工具(HTTP 抓取、日期解析、负面关键词)。"""
from __future__ import annotations

import re
from datetime import date, datetime
from difflib import SequenceMatcher

import httpx

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml",
}

_DATE_FORMATS = ("%Y-%m-%d", "%d %B %Y", "%B %d, %Y", "%d/%m/%Y", "%Y/%m/%d")

NEGATIVE_KEYWORDS_EN = [
    "lawsuit", "sued", "fraud", "scandal", "investigation", "bankruptcy",
    "fined", "violation", "illegal", "court", "convicted", "default",
    "breach", "dispute", "litigation", "arrest", "embezzle", "corrupt",
]


class CrawlerError(Exception):
    """爬虫失败(HTTP 错误 / 超时 / DOM 结构变化)。status_code 便于降级链记录每级 HTTP 码。"""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


async def fetch_html(url: str, timeout: int = 20, extra_headers: dict | None = None) -> str:
    """抓取页面 HTML。4xx/5xx/网络错误 → CrawlerError(带状态码)。"""
    headers = dict(_HEADERS)
    if extra_headers:
        headers.update(extra_headers)
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
            return resp.text
    except httpx.HTTPStatusError as exc:
        raise CrawlerError(f"HTTP {exc.response.status_code}", exc.response.status_code) from exc
    except httpx.HTTPError as exc:
        raise CrawlerError(f"请求失败: {exc}") from exc


async def fetch_html_warmup(homepage: str, url: str, timeout: int = 20) -> str:
    """媒体站基础反爬规避:同一 client 先 GET 首页拿 Cookie,带 Referer 再抓目标页。

    仍 403 即抛 CrawlerError(不引入 Playwright / 代理,接受现状)。
    """
    headers = dict(_HEADERS)
    headers["Accept"] = (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/avif,image/webp,*/*;q=0.8"
    )
    headers["Referer"] = homepage
    try:
        async with httpx.AsyncClient(
            timeout=timeout, follow_redirects=True, headers=headers
        ) as client:
            try:
                await client.get(homepage)  # 预热:拿 Cookie,失败忽略
            except httpx.HTTPError:
                pass
            resp = await client.get(url)
            resp.raise_for_status()
            return resp.text
    except httpx.HTTPStatusError as exc:
        raise CrawlerError(f"HTTP {exc.response.status_code}", exc.response.status_code) from exc
    except httpx.HTTPError as exc:
        raise CrawlerError(f"请求失败: {exc}") from exc


def is_negative(title: str, snippet: str) -> bool:
    text = (title + " " + snippet).lower()
    return any(kw in text for kw in NEGATIVE_KEYWORDS_EN)


def parse_date_loose(text: str | None) -> date | None:
    if not text:
        return None
    text = text.strip()
    m = re.search(r"\d{4}-\d{2}-\d{2}", text)
    if m:
        try:
            return date.fromisoformat(m.group())
        except ValueError:
            pass
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def abs_url(base_url: str, href: str) -> str:
    if not href:
        return ""
    if href.startswith("http"):
        return href
    return base_url.rstrip("/") + ("" if href.startswith("/") else "/") + href


_NAME_SUFFIXES = (
    "coltd", "company", "limited", "ltd", "plc", "inc",
    "corporation", "cambodia", "co",
)


def _normalize_name(s: str) -> str:
    """归一化公司名:转小写、去标点空格、剥离常见后缀,便于跨源比对。"""
    s = re.sub(r"[^a-z0-9]", "", (s or "").lower())
    for suf in _NAME_SUFFIXES:
        s = s.replace(suf, "")
    return s


def name_match(query: str, candidate: str, threshold: float = 0.6) -> bool:
    """命中校验:候选名是否与查询名近似。

    模糊搜索源(GLEIF filter、Wikipedia 标题)会返回"沾边但不是同一家"的结果,
    直接采信会张冠李戴。归一化后要求互为子串、或相似度 ≥ threshold 才算命中。
    """
    q, c = _normalize_name(query), _normalize_name(candidate)
    if not q or not c:
        return False
    return q in c or c in q or SequenceMatcher(None, q, c).ratio() >= threshold
