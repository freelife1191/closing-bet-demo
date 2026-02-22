#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Scorer 보너스 계산 회귀 테스트
"""

import os
import sys


sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from engine.models import StockData, ChartData, SupplyData
from engine.scorer import Scorer


def test_calculate_does_not_raise_bonus_signature_error():
    """Scorer.calculate는 내부 bonus 계산에서 TypeError를 내면 안 된다."""
    scorer = Scorer()

    stock = StockData(
        code="000001",
        name="테스트",
        market="KOSPI",
        close=10_000,
        change_pct=12.0,
        trading_value=200_000_000_000,
        volume=2_000_000,
        high_52w=9_500,
        low_52w=5_000,
    )

    closes = [8_000 + (i * 30) for i in range(60)]
    charts = ChartData(
        opens=[c - 50 for c in closes],
        highs=[c + 100 for c in closes],
        lows=[c - 100 for c in closes],
        closes=closes,
        volumes=[1_000_000] * 59 + [2_000_000],
        dates=[f"202601{(i % 30) + 1:02d}" for i in range(60)],
    )
    supply = SupplyData(foreign_buy_5d=10_000_000_000, inst_buy_5d=8_000_000_000)

    score, checklist, details = scorer.calculate(
        stock=stock,
        charts=charts,
        news=[],
        supply=supply,
        llm_result=None,
    )

    assert score.total >= 0
    assert isinstance(details, dict)
    assert "bonus_score" in details
