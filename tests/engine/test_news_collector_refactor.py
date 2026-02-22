#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
News collector 분해/성능 회귀 테스트
"""

from __future__ import annotations

import asyncio
from datetime import datetime

from engine.collectors.news import EnhancedNewsCollector
from engine.models import NewsItem


def _build_news(title: str, source: str, weight: float) -> NewsItem:
    return NewsItem(
        title=title,
        summary=title,
        source=source,
        url=f"https://example.com/{title}",
        published_at=datetime(2026, 2, 1),
        weight=weight,
    )


def test_get_stock_news_merges_and_sorts_by_weight(monkeypatch):
    collector = EnhancedNewsCollector()

    monkeypatch.setattr(
        collector,
        "_fetch_naver_finance_news",
        lambda *_a, **_k: [
            _build_news("a", "네이버금융", 0.60),
            _build_news("b", "네이버금융", 0.55),
        ],
    )
    monkeypatch.setattr(
        collector,
        "_fetch_naver_search_news",
        lambda *_a, **_k: [
            _build_news("c", "한국경제", 0.81),
        ],
    )
    monkeypatch.setattr(
        collector,
        "_fetch_daum_search_news",
        lambda *_a, **_k: [
            _build_news("d", "다음", 0.50),
        ],
    )

    result = asyncio.run(collector.get_stock_news("005930", limit=3, name="삼성전자"))
    assert [item.title for item in result] == ["c", "a", "b"]


def test_get_stock_news_continues_when_one_source_fails(monkeypatch):
    collector = EnhancedNewsCollector()

    def _raise(*_a, **_k):
        raise RuntimeError("failed")

    monkeypatch.setattr(collector, "_fetch_naver_finance_news", _raise)
    monkeypatch.setattr(
        collector,
        "_fetch_naver_search_news",
        lambda *_a, **_k: [_build_news("x", "검색", 0.40)],
    )
    monkeypatch.setattr(
        collector,
        "_fetch_daum_search_news",
        lambda *_a, **_k: [_build_news("y", "검색", 0.30)],
    )

    result = asyncio.run(collector.get_stock_news("005930", limit=5, name="삼성전자"))
    assert [item.title for item in result] == ["x", "y"]


def test_get_weight_uses_cache_for_repeated_source_platform():
    collector = EnhancedNewsCollector()

    first = collector._get_weight("한국경제", "finance")
    second = collector._get_weight("한국경제", "finance")

    assert first == second
    assert len(collector._weight_cache) == 1
    assert collector._weight_cache[("한국경제", "finance")] == first

