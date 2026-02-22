#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
News Collector 오케스트레이션 헬퍼.
"""

from __future__ import annotations

import heapq
from typing import Any, Callable

from engine.models import NewsItem


def collect_stock_news(
    *,
    code: str,
    limit: int,
    stock_name: str,
    fetch_naver_finance_news_fn: Callable[[str, int, set[str]], list[NewsItem]],
    fetch_naver_search_news_fn: Callable[[str, int, set[str]], list[NewsItem]],
    fetch_daum_search_news_fn: Callable[[str, int, set[str]], list[NewsItem]],
    logger: Any,
) -> list[NewsItem]:
    """다중 소스 뉴스를 수집해 가중치 상위 limit개를 반환한다."""
    if limit <= 0:
        return []

    all_news: list[NewsItem] = []
    seen_titles: set[str] = set()
    source_limit = max(limit * 2, limit)

    try:
        all_news.extend(fetch_naver_finance_news_fn(code, source_limit, seen_titles))
    except Exception as e:
        logger.debug(f"네이버 금융 뉴스 수집 실패: {e}")

    if stock_name:
        try:
            all_news.extend(fetch_naver_search_news_fn(stock_name, source_limit, seen_titles))
        except Exception as e:
            logger.debug(f"네이버 뉴스 검색 실패: {e}")

    if stock_name:
        try:
            all_news.extend(fetch_daum_search_news_fn(stock_name, source_limit, seen_titles))
        except Exception as e:
            logger.debug(f"다음 뉴스 검색 실패: {e}")

    if not all_news:
        return []

    # 성능: 전체 정렬 대신 상위 limit개만 선택한다.
    top_news = heapq.nlargest(limit, all_news, key=lambda item: item.weight)
    sources_summary = [f"{item.source}({item.weight})" for item in top_news]
    logger.info(
        f"뉴스 수집 완료: {stock_name} -> {len(top_news)}개 [{', '.join(sources_summary[:3])}...]"
    )
    return top_news


__all__ = ["collect_stock_news"]
