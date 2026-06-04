"""司法舆情爬虫 · Phnom Penh Post。"""
from __future__ import annotations

from urllib.parse import quote

from bs4 import BeautifulSoup

from data_sources.crawlers.base import abs_url, fetch_html_warmup, is_negative, parse_date_loose
from schemas import LegalArticle


class PhnomPenhPostCrawler:
    SOURCE_NAME = "phnompenhpost"
    BASE_URL = "https://www.phnompenhpost.com"

    async def fetch(self, company_name: str) -> list[LegalArticle]:
        """失败抛 CrawlerError(由 service 捕获)。"""
        url = f"{self.BASE_URL}/search?keys={quote(company_name)}"
        html = await fetch_html_warmup(self.BASE_URL, url)
        soup = BeautifulSoup(html, "lxml")
        nodes = (
            soup.select(".views-row")
            or soup.select("article")
            or soup.select("div.search-result, li.search-result")
        )
        articles: list[LegalArticle] = []
        for node in nodes[:20]:
            link = node.select_one("h2 a, h3 a, .field-content a, a")
            if not link or not link.get_text(strip=True):
                continue
            title = link.get_text(strip=True)
            time_node = node.select_one("time, .date, .submitted")
            published = parse_date_loose(
                time_node.get("datetime") if time_node and time_node.get("datetime")
                else (time_node.get_text(strip=True) if time_node else None)
            )
            snippet_node = node.select_one("p, .field-content, .teaser")
            snippet = snippet_node.get_text(strip=True)[:200] if snippet_node else ""
            articles.append(LegalArticle(
                source_site=self.SOURCE_NAME, title=title,
                url=abs_url(self.BASE_URL, link.get("href", "")),
                published_date=published, snippet=snippet,
                is_negative=is_negative(title, snippet),
            ))
        return articles
