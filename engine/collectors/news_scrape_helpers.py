#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
News scrape helper functions.
"""

from __future__ import annotations

from datetime import datetime
from typing import Callable

from engine.models import NewsItem


def fetch_naver_finance_news(
    *,
    code: str,
    limit: int,
    seen_titles: set[str],
    headers: dict[str, str],
    get_weight_fn: Callable[[str, str], float],
) -> list[NewsItem]:
    """네이버 금융 종목 뉴스 페이지에서 뉴스를 수집한다."""
    import requests
    from bs4 import BeautifulSoup

    url = f"https://finance.naver.com/item/news_news.naver?code={code}"
    headers_finance = headers.copy()
    headers_finance["Referer"] = f"https://finance.naver.com/item/news.naver?code={code}"
    response = requests.get(url, headers=headers_finance, timeout=5)
    if not response.ok:
        return []

    soup = BeautifulSoup(response.text, "html.parser")
    news_table = soup.select_one("table.type5")
    if not news_table:
        return []

    published_at = datetime.now()
    results: list[NewsItem] = []
    for row in news_table.select("tr"):
        title_el = row.select_one("td.title a")
        if not title_el:
            continue

        title = title_el.text.strip()
        if not title or title in seen_titles:
            continue

        news_url = title_el.get("href", "")
        if news_url and not news_url.startswith("http"):
            news_url = f"https://finance.naver.com{news_url}"

        source_el = row.select_one("td.info")
        source = source_el.text.strip() if source_el else "네이버금융"

        seen_titles.add(title)
        results.append(
            NewsItem(
                title=title,
                summary=title,
                source=source,
                url=news_url,
                published_at=published_at,
                weight=get_weight_fn(source, "finance"),
            )
        )
        if len(results) >= limit:
            break

    return results


def fetch_naver_search_news(
    *,
    stock_name: str,
    limit: int,
    seen_titles: set[str],
    headers: dict[str, str],
    get_weight_fn: Callable[[str, str], float],
) -> list[NewsItem]:
    """네이버 뉴스 검색 결과에서 뉴스를 수집한다."""
    import requests
    from bs4 import BeautifulSoup

    search_url = f"https://search.naver.com/search.naver?where=news&query={stock_name}&sort=1"
    response = requests.get(search_url, headers=headers, timeout=5)
    if not response.ok:
        return []

    soup = BeautifulSoup(response.text, "html.parser")
    items = soup.select("div.news_wrap") or soup.select("li.bx") or soup.select("div.news_area")

    published_at = datetime.now()
    results: list[NewsItem] = []
    for item in items:
        title_el = item.select_one("a.news_tit")
        if not title_el:
            continue

        title = title_el.get("title") or title_el.text.strip()
        if not title or title in seen_titles:
            continue

        source_el = (
            item.select_one("a.info.press")
            or item.select_one("span.info.press")
            or item.select_one("a.press")
        )
        source = source_el.text.strip().replace("언론사 선정", "") if source_el else "네이버검색"

        seen_titles.add(title)
        results.append(
            NewsItem(
                title=title,
                summary=title,
                source=source,
                url=title_el.get("href", ""),
                published_at=published_at,
                weight=get_weight_fn(source, "search_naver"),
            )
        )
        if len(results) >= limit:
            break

    return results


def fetch_daum_search_news(
    *,
    stock_name: str,
    limit: int,
    seen_titles: set[str],
    headers: dict[str, str],
    get_weight_fn: Callable[[str, str], float],
) -> list[NewsItem]:
    """다음 뉴스 검색 결과에서 뉴스를 수집한다."""
    import requests
    from bs4 import BeautifulSoup

    daum_url = f"https://search.daum.net/search?w=news&q={stock_name}&sort=recency"
    response = requests.get(daum_url, headers=headers, timeout=5)
    if not response.ok:
        return []

    soup = BeautifulSoup(response.text, "html.parser")
    items = soup.select("div.c-item-content") or soup.select("ul.list_news > li")

    published_at = datetime.now()
    results: list[NewsItem] = []
    for item in items:
        link = item.select_one("a.item-title") or item.select_one("a.f_link_b") or item.select_one("a.tit_main")
        if not link:
            continue

        title = link.text.strip()
        if not title or title in seen_titles:
            continue

        source_el = item.select_one("span.txt_info") or item.select_one("a.txt_info")
        source = source_el.text.strip() if source_el else "다음검색"

        seen_titles.add(title)
        results.append(
            NewsItem(
                title=title,
                summary=title,
                source=source,
                url=link.get("href", ""),
                published_at=published_at,
                weight=get_weight_fn(source, "search_daum"),
            )
        )
        if len(results) >= limit:
            break

    return results


__all__ = [
    "fetch_naver_finance_news",
    "fetch_naver_search_news",
    "fetch_daum_search_news",
]

