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


class _CrashHighTechGate(_FakeMarketGate):
    def _score_trend(self, _row):
        return 25

    def _score_rsi(self, _row):
        return 25

    def _score_macd(self, _row):
        return 20

    def _score_volume(self, _row):
        return 15

    def _score_rs(self, _row):
        return 10

    def _get_global_data(self, _target_date):
        return {
            "indices": {
                "kospi": {"value": 2520.0, "change_pct": -3.8},
                "kosdaq": {"value": 780.0, "change_pct": -4.2},
            },
            "commodities": {},
            "crypto": {},
        }


class _MissingIndicesButSectorCrashGate(_FakeMarketGate):
    def _score_trend(self, _row):
        return 25

    def _score_rsi(self, _row):
        return 25

    def _score_macd(self, _row):
        return 20

    def _score_volume(self, _row):
        return 15

    def _score_rs(self, _row):
        return 10

    def _get_global_data(self, _target_date):
        return {
            "indices": {},
            "commodities": {},
            "crypto": {},
        }

    def _get_sector_data(self, _target_date, global_data=None):
        del global_data
        return {
            "반도체": -7.29,
            "2차전지": -9.11,
            "자동차": -2.53,
            "헬스케어": -8.04,
            "IT": -9.65,
            "은행": -5.14,
            "철강": -4.46,
            "증권": -7.98,
            "조선": -4.44,
            "에너지": -0.54,
            "KOSPI 200": -7.24,
        }


class _PartialSectorFailureGate(_MissingIndicesButSectorCrashGate):
    def _get_sector_data(self, _target_date, global_data=None):
        del global_data
        # [INFRA-105] 다섯 섹터는 -3%, 나머지는 조회 실패로 결측이다
        return {
            "반도체": -3.0,
            "2차전지": -3.0,
            "자동차": -3.0,
            "헬스케어": -3.0,
            "IT": -3.0,
            "은행": None,
            "철강": None,
            "증권": None,
            "조선": None,
            "에너지": None,
            "KOSPI 200": None,
        }


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


def test_analyze_market_state_applies_intraday_market_crash_penalty():
    result = analyze_market_state(_CrashHighTechGate(), target_date="2026-02-21", logger=logging.getLogger("test"))

    assert result["details"]["tech_score"] == 95
    assert result["total_score"] < 40
    assert result["status"] == "약세장 (Bearish)"


def test_analyze_market_state_penalizes_sector_crash_when_indices_missing():
    result = analyze_market_state(
        _MissingIndicesButSectorCrashGate(),
        target_date="2026-02-21",
        logger=logging.getLogger("test"),
    )

    assert result["details"]["tech_score"] == 95
    assert result["total_score"] < 40
    assert result["status"] == "약세장 (Bearish)"


def test_analyze_market_state_keeps_sector_penalty_and_missing_values_on_partial_failure():
    result = analyze_market_state(
        _PartialSectorFailureGate(),
        target_date="2026-02-21",
        logger=logging.getLogger("test"),
    )

    assert "error" not in result
    # 결측을 빼면 평균 -3%·하락 비율 1.0 이라 30 점 감점이다. 0 으로 채웠다면 감점 0 이다
    assert result["details"]["sector_penalty"] == 30
    # KOSPI 200 이 결측이면 가짜 0.0 이 아니라 가격 자료의 등락률로 폴백한다
    assert result["kospi_change"] == 2.1
    missing = {s["name"]: s for s in result["sectors"] if s["change_pct"] is None}
    assert set(missing) == {"은행", "철강", "증권", "조선", "에너지", "KOSPI 200"}
    assert {s["signal"] for s in missing.values()} == {"Neutral"}
