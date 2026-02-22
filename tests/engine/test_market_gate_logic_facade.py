#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Market Gate Logic 퍼사드/분해 회귀 테스트
"""

from __future__ import annotations

import math
import os
import sys
from dataclasses import dataclass


sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from engine.market_gate_logic import (
    build_gate_reason,
    build_market_status,
    build_sector_signals,
    resolve_analysis_date_str,
    sanitize_for_json,
    score_macro,
    score_supply,
)


@dataclass
class _Config:
    usd_krw_warning: float = 1450.0
    usd_krw_danger: float = 1480.0
    foreign_net_buy_threshold: int = 500_000_000_000


def test_sanitize_for_json_replaces_nan_and_inf_recursively():
    payload = {"a": math.nan, "b": [1.0, math.inf, {"c": -math.inf}]}
    sanitized = sanitize_for_json(payload)

    assert sanitized == {"a": None, "b": [1.0, None, {"c": None}]}


def test_resolve_analysis_date_str_prioritizes_target_date():
    result = {"dataset_date": "2026-02-20"}
    assert resolve_analysis_date_str(result, "2026-02-21") == "20260221"
    assert resolve_analysis_date_str(result, None) == "20260220"


def test_market_status_and_gate_reason_thresholds():
    assert build_market_status(75) == ("강세장 (Bullish)", "Bullish", "GREEN")
    assert build_market_status(55) == ("중립 (Neutral)", "Neutral", "YELLOW")
    assert build_market_status(10) == ("약세장 (Bearish)", "Bearish", "RED")

    assert build_gate_reason(35, "SAFE") == "기술적 점수 미달 (35/40)"
    assert build_gate_reason(80, "DANGER") == "시장 양호 (Technical) [환율 위험]"


def test_score_macro_and_supply_follow_config_thresholds():
    config = _Config()

    assert score_macro(1490.0, config) == (-20, "DANGER")
    assert score_macro(1460.0, config) == (0, "WARNING")
    assert score_macro(1420.0, config) == (15, "SAFE")

    assert score_supply({}, config) == 0
    assert score_supply({"foreign_buy": 1}, config) == 10
    assert (
        score_supply(
            {"foreign_buy": config.foreign_net_buy_threshold + 1},
            config,
        )
        == 15
    )


def test_build_sector_signals_applies_bullish_neutral_bearish_rules():
    sector_data = {"반도체": 1.2, "은행": 0.3, "자동차": -1.1}
    signals = build_sector_signals(sector_data)

    result_map = {item["name"]: item["signal"] for item in signals}
    assert result_map["반도체"] == "Bullish"
    assert result_map["은행"] == "Neutral"
    assert result_map["자동차"] == "Bearish"
