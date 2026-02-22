#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
등락률 필터 경계값 회귀 테스트
"""

import os
import sys


sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from engine.grade_classifier import FilterValidator
from engine.models import ChartData, ScoreDetail, StockData, SupplyData


def _build_inputs(change_pct: float):
    stock = StockData(
        code="000001",
        name="테스트",
        market="KOSPI",
        close=10_000,
        change_pct=change_pct,
        trading_value=200_000_000_000,
        volume=1_000_000,
        high_52w=12_000,
        low_52w=8_000,
    )
    score = ScoreDetail(total=8, news=1)
    charts = ChartData(opens=[9_800], highs=[10_200], lows=[9_700], closes=[10_100])
    supply = SupplyData(foreign_buy_5d=1_000_000_000, inst_buy_5d=1_000_000_000)
    return stock, score, charts, supply


def test_price_change_29_9_passes_filter():
    """상한가 근처(29.9%)는 필터를 통과해야 한다."""
    validator = FilterValidator()
    stock, score, charts, supply = _build_inputs(29.9)

    result = validator.validate(
        stock=stock,
        score=score,
        score_details={},
        supply=supply,
        charts=charts,
        allow_no_news=True,
    )

    assert result.passed is True


def test_price_change_above_30_fails_filter():
    """30% 초과는 비정상 데이터로 간주해 필터에서 제외한다."""
    validator = FilterValidator()
    stock, score, charts, supply = _build_inputs(30.1)

    result = validator.validate(
        stock=stock,
        score=score,
        score_details={},
        supply=supply,
        charts=charts,
        allow_no_news=True,
    )

    assert result.passed is False


def test_upper_shadow_validation_handles_malformed_chart_values():
    """차트 값이 비정상이어도 필터 로직이 예외 없이 통과 처리된다."""
    validator = FilterValidator()
    stock, score, _charts, supply = _build_inputs(10.0)
    malformed_charts = ChartData(opens=["N/A"], highs=[10_200], lows=[9_700], closes=[10_100])

    result = validator.validate(
        stock=stock,
        score=score,
        score_details={},
        supply=supply,
        charts=malformed_charts,
        allow_no_news=True,
    )

    assert result.passed is True
