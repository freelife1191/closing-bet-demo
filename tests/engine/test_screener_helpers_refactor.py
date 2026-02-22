#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Screener helper 분해 회귀 테스트
"""

import os
import sys
from datetime import datetime

import pandas as pd


sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from engine.screener_scoring_helpers import (
    build_ticker_index,
    calculate_volume_score,
    scale_vcp_score,
    score_supply_from_csv,
    score_supply_from_toss_trend,
)


def test_build_ticker_index_normalizes_and_groups():
    df = pd.DataFrame(
        [
            {"ticker": "1", "date": "2026-02-20", "close": 100},
            {"ticker": "1", "date": "2026-02-21", "close": 101},
            {"ticker": "2", "date": "2026-02-21", "close": 200},
        ]
    )

    idx = build_ticker_index(df)
    assert set(idx.keys()) == {"000001", "000002"}
    assert len(idx["000001"]) == 2


def test_calculate_volume_score_applies_thresholds():
    series = pd.Series([100] * 19 + [350])
    score, ratio = calculate_volume_score(series)
    assert score == 20
    assert ratio > 3.0


def test_score_supply_from_toss_trend_returns_expected_shape():
    trend = {
        "foreign": 60_000_000_000,
        "institution": 25_000_000_000,
        "details": [
            {"netForeignerBuyVolume": 10, "netInstitutionBuyVolume": 20},
            {"netForeignerBuyVolume": 5, "netInstitutionBuyVolume": 0},
        ],
    }

    scored = score_supply_from_toss_trend(trend)
    assert scored["foreign_5d"] == 60_000_000_000
    assert scored["inst_5d"] == 25_000_000_000
    assert scored["foreign_1d"] == 10
    assert scored["inst_1d"] == 20
    assert scored["score"] > 0


def test_score_supply_from_csv_handles_target_datetime_and_columns():
    df = pd.DataFrame(
        [
            {"date": pd.Timestamp("2026-02-19"), "foreign_buy": 1, "inst_buy": 2},
            {"date": pd.Timestamp("2026-02-20"), "foreign_buy": 3, "inst_buy": 4},
            {"date": pd.Timestamp("2026-02-21"), "foreign_buy": 5, "inst_buy": 6},
            {"date": pd.Timestamp("2026-02-22"), "foreign_buy": 7, "inst_buy": 8},
            {"date": pd.Timestamp("2026-02-23"), "foreign_buy": 9, "inst_buy": 10},
        ]
    )

    scored = score_supply_from_csv(df, target_datetime=datetime(2026, 2, 23))
    assert scored["foreign_5d"] == 25
    assert scored["inst_5d"] == 30
    assert scored["foreign_1d"] == 9
    assert scored["inst_1d"] == 10


def test_score_supply_from_csv_builds_latest_first_details_without_iterrows_regression():
    df = pd.DataFrame(
        [
            {"date": pd.Timestamp("2026-02-19"), "foreign_buy": 0, "inst_buy": 1},
            {"date": pd.Timestamp("2026-02-20"), "foreign_buy": 1, "inst_buy": 1},
            {"date": pd.Timestamp("2026-02-21"), "foreign_buy": 1, "inst_buy": 1},
            {"date": pd.Timestamp("2026-02-22"), "foreign_buy": 1, "inst_buy": 1},
            {"date": pd.Timestamp("2026-02-23"), "foreign_buy": 1, "inst_buy": 1},
        ]
    )

    scored = score_supply_from_csv(df, target_datetime=datetime(2026, 2, 23))

    assert scored["score"] > 0
    assert scored["foreign_1d"] == 1


def test_scale_vcp_score_caps_to_ten():
    assert scale_vcp_score(55) == 6
    assert scale_vcp_score(1000) == 10
