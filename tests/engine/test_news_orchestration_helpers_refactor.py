#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
News orchestration helper 리팩토링 회귀 테스트
"""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

from engine.collectors.news_orchestration_helpers import collect_stock_news
from engine.models import NewsItem


def _news(title: str, source: str, weight: float) -> NewsItem:
    return NewsItem(
        title=title,
        summary=title,
        source=source,
        url=f"https://example.com/{title}",
        published_at=datetime(2026, 2, 1),
        weight=weight,
    )


def test_collect_stock_news_returns_top_limit_by_weight():
    logger = SimpleNamespace(debug=lambda *_a, **_k: None, info=lambda *_a, **_k: None)

    result = collect_stock_news(
        code="005930",
        limit=2,
        stock_name="삼성전자",
        fetch_naver_finance_news_fn=lambda *_a, **_k: [_news("a", "f", 0.3), _news("b", "f", 0.7)],
        fetch_naver_search_news_fn=lambda *_a, **_k: [_news("c", "n", 0.9)],
        fetch_daum_search_news_fn=lambda *_a, **_k: [_news("d", "d", 0.5)],
        logger=logger,
    )

    assert [item.title for item in result] == ["c", "b"]


def test_collect_stock_news_continues_when_source_raises():
    logger = SimpleNamespace(debug=lambda *_a, **_k: None, info=lambda *_a, **_k: None)

    def _raise(*_a, **_k):
        raise RuntimeError("failed")

    result = collect_stock_news(
        code="005930",
        limit=5,
        stock_name="삼성전자",
        fetch_naver_finance_news_fn=_raise,
        fetch_naver_search_news_fn=lambda *_a, **_k: [_news("x", "n", 0.4)],
        fetch_daum_search_news_fn=lambda *_a, **_k: [_news("y", "d", 0.3)],
        logger=logger,
    )

    assert [item.title for item in result] == ["x", "y"]
