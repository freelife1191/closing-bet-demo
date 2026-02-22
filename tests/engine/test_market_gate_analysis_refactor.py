#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Market Gate analyze 분해 회귀 테스트
"""

from __future__ import annotations

import logging

import pandas as pd

from engine.market_gate_analysis import analyze_market_state


class _FakeMarketGate:
    def _load_price_data(self, _target_date):
        return pd.DataFrame(
            [
                {
                    "date": pd.Timestamp("2026-02-20"),
                    "close": 100.0,
                    "change_pct": 1.2,
                    "rsi": 55.5,
                    "macd": 0.33,
                    "ma20": 98.0,
                    "ma60": 95.0,
                },
                {
                    "date": pd.Timestamp("2026-02-21"),
                    "close": 102.0,
                    "change_pct": 2.1,
                    "rsi": 60.2,
                    "macd": 0.44,
                    "ma20": 99.0,
                    "ma60": 96.0,
                },
            ]
        )

    def _fetch_benchmark_data(self, _start, _end):
        return pd.DataFrame([{"date": "2026-02-21", "close": 1.0}])

    def _calculate_indicators(self, df, _bench_df):
        return df

    def _get_usd_krw(self):
        return 1420.0

    def _load_supply_data(self):
        return {}

    def _score_trend(self, _row):
        return 20

    def _score_rsi(self, _row):
        return 20

    def _score_macd(self, _row):
        return 15

    def _score_volume(self, _row):
        return 10

    def _score_rs(self, _row):
        return 10

    def _score_macro(self, _usd_krw):
        return 15, "SAFE"

    def _score_supply(self, _supply_data):
        return 0

    def _get_global_data(self, _target_date):
        return {
            "indices": {
                "kospi": {"value": 2650.5, "change_pct": 0.7},
                "kosdaq": {"value": 880.1, "change_pct": -0.2},
            },
            "commodities": {},
            "crypto": {},
        }

    def _get_sector_data(self, _target_date, global_data=None):
        del global_data
        return {"반도체": 1.2, "은행": -0.3}

    def _default_result(self, msg):
        return {"error": msg}


class _EmptyFakeMarketGate(_FakeMarketGate):
    def _load_price_data(self, _target_date):
        return pd.DataFrame()


class _SupplyFailureGate(_FakeMarketGate):
    def _load_supply_data(self):
        raise AssertionError("supply path should not be used")

    def _score_supply(self, _supply_data):
        raise AssertionError("supply score should not be calculated")


def test_analyze_market_state_builds_expected_payload():
    result = analyze_market_state(_FakeMarketGate(), target_date="2026-02-21", logger=logging.getLogger("test"))

    assert result["is_gate_open"] is True
    assert result["total_score"] == 75
    assert result["kospi_close"] == 2650.5
    assert result["details"]["rsi_score"] == 20
    assert isinstance(result["sectors"], list)
    assert len(result["sectors"]) == 2


def test_analyze_market_state_returns_default_when_price_data_empty():
    result = analyze_market_state(_EmptyFakeMarketGate(), target_date=None, logger=logging.getLogger("test"))
    assert result == {"error": "가격 데이터 부족"}


def test_analyze_market_state_does_not_require_supply_side_path():
    result = analyze_market_state(_SupplyFailureGate(), target_date="2026-02-21", logger=logging.getLogger("test"))
    assert result["total_score"] == 75
