#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Engine - Market Gate Logic Helpers (Facade)

기존 import 경로를 유지하면서 구현을 fetchers/scoring/utils 모듈로 분리한다.
"""

from __future__ import annotations

from engine.market_gate_logic_fetchers import (
    fetch_benchmark_data,
    get_global_data,
    get_sector_data,
    get_usd_krw,
    load_price_data,
    load_supply_data,
)
from engine.market_gate_logic_scoring import (
    build_gate_reason,
    build_market_status,
    build_sector_signals,
    calculate_indicators,
    score_macro,
    score_macd,
    score_rs,
    score_rsi,
    score_supply,
    score_trend,
    score_volume,
)
from engine.market_gate_logic_utils import (
    build_default_result,
    resolve_analysis_date_str,
    sanitize_for_json,
)

__all__ = [
    "fetch_benchmark_data",
    "get_global_data",
    "get_sector_data",
    "load_price_data",
    "sanitize_for_json",
    "resolve_analysis_date_str",
    "get_usd_krw",
    "load_supply_data",
    "calculate_indicators",
    "score_trend",
    "score_rsi",
    "score_macd",
    "score_volume",
    "score_rs",
    "score_macro",
    "score_supply",
    "build_market_status",
    "build_gate_reason",
    "build_sector_signals",
    "build_default_result",
]
