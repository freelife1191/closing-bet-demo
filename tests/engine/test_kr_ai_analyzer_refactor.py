#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KR AI Analyzer 분해 회귀 테스트
"""

import os
import sys


sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from engine.kr_ai_analyzer import KrAiAnalyzer, RecommendationCombiner
import engine.kr_ai_analyzer as kr_ai_analyzer_module
from engine.models import NewsItem


def test_recommendation_combiner_handles_empty_and_conflict_cases():
    none_case = RecommendationCombiner.combine(None, None)
    assert none_case["action"] == "HOLD"
    assert none_case["confidence"] == 0

    gemini = {"action": "BUY", "confidence": 80, "reason": "g"}
    gpt = {"action": "HOLD", "confidence": 70, "reason": "p"}
    conflict = RecommendationCombiner.combine(gemini, gpt)
    assert conflict["action"] == "BUY"
    assert conflict["confidence"] == 80
    assert "(우선권)" in conflict["reason"]


def test_analyze_stock_preserves_response_schema_with_unavailable_strategies():
    analyzer = KrAiAnalyzer(api_key="", openai_api_key="")
    analyzer._get_stock_info = lambda _ticker: {
        "ticker": "005930",
        "name": "삼성전자",
        "price": 70000,
        "change_pct": 1.2,
    }
    analyzer._collect_news = lambda _ticker, _name: [
        NewsItem(
            title="뉴스",
            summary="요약",
            source="테스트",
            url="http://example.com",
            published_at=None,
            weight=1.0,
        )
    ]

    result = analyzer.analyze_stock("005930")

    assert result["ticker"] == "005930"
    assert result["name"] == "삼성전자"
    assert "final_recommendation" in result
    assert result["final_recommendation"]["action"] == "HOLD"
    assert isinstance(result["news"], list)


def test_analyze_multiple_stocks_stops_when_stop_requested(monkeypatch):
    analyzer = KrAiAnalyzer(api_key="", openai_api_key="")
    monkeypatch.setattr(kr_ai_analyzer_module.shared_state, "STOP_REQUESTED", True)

    result = analyzer.analyze_multiple_stocks(["005930", "000660"])
    assert "error" in result
    assert result["signals"] == []

    monkeypatch.setattr(kr_ai_analyzer_module.shared_state, "STOP_REQUESTED", False)


def test_private_wrappers_delegate_to_data_service():
    class _DummyDataService:
        def get_stock_info(self, ticker):
            return {"ticker": ticker, "name": "T", "price": 1, "change_pct": 0}

        def get_stock_name(self, ticker):
            return f"N-{ticker}"

        def collect_news(self, _ticker, _name):
            return []

        def convert_to_news_items(self, _news_dicts):
            return []

        def news_item_to_dict(self, _news_item):
            return {"title": "ok"}

    analyzer = KrAiAnalyzer(api_key="", openai_api_key="", data_service=_DummyDataService())

    assert analyzer._get_stock_name("005930") == "N-005930"
    assert analyzer._get_stock_info("005930")["ticker"] == "005930"
    assert analyzer._collect_news("005930", "N") == []
    assert analyzer._convert_to_news_items([]) == []
