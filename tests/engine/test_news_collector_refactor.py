#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
News collector 분해/성능 회귀 테스트
"""

from __future__ import annotations

import asyncio
import sys
import types
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


def test_get_stock_news_reuses_sqlite_snapshot_after_memory_clear(monkeypatch, tmp_path):
    collector = EnhancedNewsCollector()
    with collector._news_cache_lock:
        collector._news_cache.clear()

    monkeypatch.setattr(
        EnhancedNewsCollector,
        "_current_news_cache_slot",
        classmethod(lambda cls, now=None: "202602261500"),
    )
    monkeypatch.setattr(
        EnhancedNewsCollector,
        "_news_sqlite_context",
        classmethod(
            lambda cls, *, code, limit, stock_name, cache_slot: (
                str(tmp_path / ".enhanced_news_cache" / f"{code}__{limit}__{cache_slot}.snapshot"),
                (55, 77),
            )
        ),
    )

    calls = {"count": 0}

    def _fake_collect_stock_news(*_args, **_kwargs):
        calls["count"] += 1
        return [_build_news("cached-news", "한국경제", 0.81)]

    monkeypatch.setattr("engine.collectors.news.collect_stock_news_impl", _fake_collect_stock_news)

    first = asyncio.run(collector.get_stock_news("5930", limit=3, name="삼성전자"))
    assert [item.title for item in first] == ["cached-news"]
    assert calls["count"] == 1

    with collector._news_cache_lock:
        collector._news_cache.clear()

    monkeypatch.setattr(
        "engine.collectors.news.collect_stock_news_impl",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("sqlite snapshot should be reused")),
    )

    second = asyncio.run(collector.get_stock_news("005930", limit=3, name="삼성전자"))
    assert [item.title for item in second] == ["cached-news"]
    assert calls["count"] == 1


def test_get_stock_news_caches_empty_result_and_reuses_sqlite_snapshot(monkeypatch, tmp_path):
    collector = EnhancedNewsCollector()
    with collector._news_cache_lock:
        collector._news_cache.clear()

    monkeypatch.setattr(
        EnhancedNewsCollector,
        "_current_news_cache_slot",
        classmethod(lambda cls, now=None: "202602261500"),
    )
    monkeypatch.setattr(
        EnhancedNewsCollector,
        "_news_sqlite_context",
        classmethod(
            lambda cls, *, code, limit, stock_name, cache_slot: (
                str(tmp_path / ".enhanced_news_cache" / f"{code}__{limit}__{cache_slot}.snapshot"),
                (56, 78),
            )
        ),
    )

    calls = {"count": 0}

    def _fake_collect_stock_news(*_args, **_kwargs):
        calls["count"] += 1
        return []

    monkeypatch.setattr("engine.collectors.news.collect_stock_news_impl", _fake_collect_stock_news)

    first = asyncio.run(collector.get_stock_news("005930", limit=3, name="삼성전자"))
    assert first == []
    assert calls["count"] == 1

    with collector._news_cache_lock:
        collector._news_cache.clear()

    monkeypatch.setattr(
        "engine.collectors.news.collect_stock_news_impl",
        lambda *_a, **_k: (_ for _ in ()).throw(
            AssertionError("empty result should be served from sqlite snapshot")
        ),
    )

    second = asyncio.run(collector.get_stock_news("005930", limit=3, name="삼성전자"))
    assert second == []
    assert calls["count"] == 1


def test_get_weight_uses_cache_for_repeated_source_platform():
    collector = EnhancedNewsCollector()

    first = collector._get_weight("한국경제", "finance")
    second = collector._get_weight("한국경제", "finance")

    assert first == second
    assert len(collector._weight_cache) == 1
    assert collector._weight_cache[("한국경제", "finance")] == first


def test_engine_package_exposes_modular_enhanced_news_collector():
    import engine
    from engine.collectors.news import EnhancedNewsCollector as ModularEnhancedNewsCollector

    assert engine.EnhancedNewsCollector is ModularEnhancedNewsCollector


def test_collectors_module_exposes_modular_enhanced_news_collector():
    import engine.collectors as collectors_module
    from engine.collectors.news import EnhancedNewsCollector as ModularEnhancedNewsCollector

    assert collectors_module.EnhancedNewsCollector is ModularEnhancedNewsCollector


def test_news_collector_get_stock_name_reuses_sqlite_snapshot_after_memory_clear(monkeypatch, tmp_path):
    collector = EnhancedNewsCollector()
    with collector._stock_name_cache_lock:
        collector._stock_name_cache.clear()

    monkeypatch.setattr(
        EnhancedNewsCollector,
        "_stock_name_sqlite_context",
        classmethod(
            lambda cls, ticker: (
                str(tmp_path / ".krx_collector_cache" / "stock_name" / f"{str(ticker).zfill(6)}.snapshot"),
                (77, 99),
            )
        ),
    )

    calls = {"count": 0}

    def _fake_get_market_ticker_name(_ticker: str) -> str:
        calls["count"] += 1
        return "삼성전자"

    fake_pykrx = types.ModuleType("pykrx")
    fake_pykrx.stock = types.SimpleNamespace(get_market_ticker_name=_fake_get_market_ticker_name)
    monkeypatch.setitem(sys.modules, "pykrx", fake_pykrx)

    first = collector._get_stock_name("5930")
    assert first == "삼성전자"
    assert calls["count"] == 1

    with collector._stock_name_cache_lock:
        collector._stock_name_cache.clear()

    fake_pykrx.stock = types.SimpleNamespace(
        get_market_ticker_name=lambda _ticker: (_ for _ in ()).throw(
            AssertionError("sqlite snapshot should be reused for stock name")
        )
    )

    second = collector._get_stock_name("005930")
    assert second == "삼성전자"
    assert calls["count"] == 1
