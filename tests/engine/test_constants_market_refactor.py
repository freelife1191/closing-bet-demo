#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
constants_market 분해 회귀 테스트
"""

import os
import sys


sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

import engine.constants as constants_facade
import engine.constants_market as market_constants


def test_constants_market_reexports_core_singletons():
    assert market_constants.TRADING_VALUES.S_GRADE == 1_000_000_000_000
    assert market_constants.VCP_THRESHOLDS.MIN_SCORE == 50
    assert market_constants.MARKET_GATE.MIN_OPEN == 40
    assert market_constants.FILE_PATHS.SIGNALS_LOG == "signals_log.csv"
    assert market_constants.TICKERS.KOSPI_CODE == "1001"


def test_constants_facade_still_exposes_market_symbols():
    assert constants_facade.TRADING_VALUES.MINIMUM == 100_000_000_000
    assert constants_facade.SCREENING.DEFAULT_TOP_N == 300
    assert constants_facade.ResponseStatus.SUCCESS == "success"

