#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Phase1Analyzer historical target_date 전달 회귀 테스트
"""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace

from engine.models import ChartData, StockData, SupplyData
from engine.phases_analysis import Phase1Analyzer


class _CollectorStub:
    def __init__(self):
        self.chart_target_dates: list[date | None] = []
        self.supply_target_dates: list[date | None] = []

    async def get_stock_detail(self, _code: str):
        return None

    async def get_chart_data(self, _code: str, _days: int, target_date=None):
        self.chart_target_dates.append(target_date)
        return ChartData(
            dates=[f"2026-01-{i:02d}" for i in range(1, 61)],
            opens=[100] * 60,
            highs=[110] * 60,
            lows=[90] * 60,
            closes=[105] * 60,
            volumes=[1_000] * 60,
        )

    async def get_supply_data(self, _code: str, target_date=None):
        self.supply_target_dates.append(target_date)
        return SupplyData(
            foreign_buy_5d=1_000_000_000,
            inst_buy_5d=2_000_000_000,
            retail_buy_5d=0,
        )


class _ScorerStub:
    def calculate(self, _stock, _charts, _news, _supply, _llm_result):
        score = SimpleNamespace(total=8)
        return score, None, {"volume_ratio": 1.2}

    def determine_grade(
        self,
        _stock,
        _score,
        _score_details,
        _supply,
        _charts,
        allow_no_news=False,
    ):
        _ = allow_no_news
        return "B"


async def test_phase1_execute_passes_target_date_to_chart_and_supply_collectors():
    collector = _CollectorStub()
    analyzer = Phase1Analyzer(
        collector=collector,
        scorer=_ScorerStub(),
        trading_value_min=50_000_000_000,
    )
    candidate = StockData(
        code="005930",
        name="삼성전자",
        market="KOSPI",
        close=70_000,
        change_pct=3.0,
        trading_value=100_000_000_000,
        volume=1_000_000,
    )

    results = await analyzer.execute([candidate], target_date=date(2026, 3, 4))

    assert len(results) == 1
    assert collector.chart_target_dates == [date(2026, 3, 4)]
    assert collector.supply_target_dates == [date(2026, 3, 4)]
