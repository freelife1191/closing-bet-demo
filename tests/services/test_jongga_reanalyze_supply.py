#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""closing-bet 재분석에서 supply 정보를 LLM 입력에 정확히 전달하는지 검증."""

from __future__ import annotations

from app.routes.kr_market_jongga_reanalysis_helpers import (
    _build_jongga_news_analysis_items,
)


def _signal(stock_code: str, foreign: int, inst: int, news: list | None = None) -> dict:
    return {
        "stock_code": stock_code,
        "stock_name": f"종목{stock_code}",
        "score": {"total": 11, "news": 2, "volume": 3, "chart": 2, "candle": 1, "timing": 1, "supply": 2},
        "score_details": {
            "foreign_net_buy": foreign,
            "inst_net_buy": inst,
            "bonus_breakdown": {"volume": 2, "candle": 1, "limit_up": 0},
            "bonus_score": 3,
        },
        "news_items": news if news is not None else [{"title": "테스트 뉴스", "weight": 1.0}],
    }


class TestBuildJonggaNewsAnalysisItemsSupply:
    def test_supply_dict_populated_from_score_details(self):
        signals = [_signal("005930", foreign=50_000_000_000, inst=30_000_000_000)]
        items = _build_jongga_news_analysis_items(signals)
        assert len(items) == 1
        supply = items[0]["supply"]
        assert isinstance(supply, dict)
        assert supply["foreign_buy_5d"] == 50_000_000_000
        assert supply["inst_buy_5d"] == 30_000_000_000

    def test_no_news_signal_skipped(self):
        signals = [_signal("000660", foreign=1, inst=1, news=[])]
        items = _build_jongga_news_analysis_items(signals)
        assert items == []

    def test_missing_score_details_supply_zero(self):
        sig = {
            "stock_code": "111111",
            "stock_name": "X",
            "news_items": [{"title": "n", "weight": 1.0}],
        }
        items = _build_jongga_news_analysis_items([sig])
        assert len(items) == 1
        supply = items[0]["supply"]
        assert isinstance(supply, dict)
        assert supply["foreign_buy_5d"] == 0
        assert supply["inst_buy_5d"] == 0

    def test_stock_passthrough(self):
        signals = [_signal("005930", foreign=10, inst=20)]
        items = _build_jongga_news_analysis_items(signals)
        assert items[0]["stock"] is signals[0]
        assert items[0]["news"] == signals[0]["news_items"]
