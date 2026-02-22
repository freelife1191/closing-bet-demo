#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

from engine.constants import (
    AI_ANALYSIS,
    MESSENGER,
    NEWS_SOURCE_WEIGHTS,
    TRADING_VALUES,
    TradingValueThresholds,
)


def test_constants_facade_exports_core_and_ai_constants():
    assert TRADING_VALUES.MINIMUM == 100_000_000_000
    assert MESSENGER.TELEGRAM_MAX_LENGTH == 4000
    assert AI_ANALYSIS.CONFIDENCE_MIN == 50


def test_constants_facade_exports_classes_and_methods():
    assert TradingValueThresholds().A_GRADE == 500_000_000_000
    assert NEWS_SOURCE_WEIGHTS.get_weight("매일경제") == 0.9
    assert NEWS_SOURCE_WEIGHTS.get_weight("알수없음") == NEWS_SOURCE_WEIGHTS.DEFAULT
