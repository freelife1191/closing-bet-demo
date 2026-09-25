#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SignalTracker 수급 헬퍼 리팩토링 테스트
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from engine.signal_tracker_supply_helpers import build_supply_score_frame


def _count_consecutive_positive(values: np.ndarray) -> int:
    count = 0
    for value in values[::-1]:
        if value > 0:
            count += 1
        else:
            break
    return count


def test_build_supply_score_frame_filters_by_score_and_foreign_min():
    raw_df = pd.DataFrame(
        [
            {"ticker": "1", "date": "2026-02-01", "foreign_buy": 400_000_000, "inst_buy": 150_000_000},
            {"ticker": "1", "date": "2026-02-02", "foreign_buy": 300_000_000, "inst_buy": 200_000_000},
            {"ticker": "1", "date": "2026-02-03", "foreign_buy": 350_000_000, "inst_buy": 120_000_000},
            {"ticker": "1", "date": "2026-02-04", "foreign_buy": 250_000_000, "inst_buy": 130_000_000},
            {"ticker": "1", "date": "2026-02-05", "foreign_buy": 300_000_000, "inst_buy": 140_000_000},
            {"ticker": "2", "date": "2026-02-01", "foreign_buy": 10_000, "inst_buy": 10_000},
            {"ticker": "2", "date": "2026-02-02", "foreign_buy": 10_000, "inst_buy": 10_000},
            {"ticker": "2", "date": "2026-02-03", "foreign_buy": 10_000, "inst_buy": 10_000},
            {"ticker": "2", "date": "2026-02-04", "foreign_buy": 10_000, "inst_buy": 10_000},
            {"ticker": "2", "date": "2026-02-05", "foreign_buy": 10_000, "inst_buy": 10_000},
            {"ticker": "3", "date": "2026-02-01", "foreign_buy": 500_000_000, "inst_buy": 300_000_000},
            {"ticker": "3", "date": "2026-02-02", "foreign_buy": 500_000_000, "inst_buy": 300_000_000},
            {"ticker": "3", "date": "2026-02-03", "foreign_buy": 500_000_000, "inst_buy": 300_000_000},
            {"ticker": "3", "date": "2026-02-04", "foreign_buy": 500_000_000, "inst_buy": 300_000_000},
        ]
    )

    result = build_supply_score_frame(
        raw_df,
        foreign_min=1_000_000,
        count_consecutive_positive=_count_consecutive_positive,
        logger=logging.getLogger(__name__),
    )

    assert len(result) == 1
    row = result.iloc[0]
    assert row["ticker"] == "000001"
    assert row["supply_demand_index"] >= 40


def test_build_supply_score_frame_returns_empty_when_required_column_missing():
    raw_df = pd.DataFrame(
        [
            {"ticker": "1", "date": "2026-02-01", "foreign_buy": 100},
        ]
    )
    result = build_supply_score_frame(
        raw_df,
        foreign_min=50_000,
        count_consecutive_positive=_count_consecutive_positive,
        logger=logging.getLogger(__name__),
    )
    assert result.empty


def test_build_supply_score_frame_normalizes_ticker_and_computes_consecutive_from_latest():
    raw_df = pd.DataFrame(
        [
            {"ticker": "1", "date": "2026-02-01", "foreign_buy": -1, "inst_buy": 1},
            {"ticker": "1", "date": "2026-02-02", "foreign_buy": 2, "inst_buy": 1},
            {"ticker": "1", "date": "2026-02-03", "foreign_buy": 2, "inst_buy": 1},
            {"ticker": "1", "date": "2026-02-04", "foreign_buy": 2, "inst_buy": 1},
            {"ticker": "1", "date": "2026-02-05", "foreign_buy": 2, "inst_buy": 1},
            {"ticker": "1", "date": "2026-02-06", "foreign_buy": 2, "inst_buy": 1},
        ]
    )

    result = build_supply_score_frame(
        raw_df,
        foreign_min=1,
        count_consecutive_positive=_count_consecutive_positive,
        logger=logging.getLogger(__name__),
    )

    assert len(result) == 1
    assert result.iloc[0]["ticker"] == "000001"
    assert result.iloc[0]["supply_demand_index"] >= 40


def test_build_supply_score_frame_drops_tickers_with_blank_values_in_the_window():
    """[FLOW-024] sum 은 빈 칸을 건너뛰므로 최근 5행에 빈 칸이 있으면 4일 합이 5일 값이 된다."""
    dates = ["2026-09-18", "2026-09-21", "2026-09-22", "2026-09-23", "2026-09-24"]

    def _rows(ticker, foreign, inst):
        return [
            {"ticker": ticker, "date": day, "foreign_buy": f, "inst_buy": i}
            for day, f, i in zip(dates, foreign, inst)
        ]

    full = [600_000_000] * 5
    blank = [600_000_000, 600_000_000, np.nan, 600_000_000, 600_000_000]
    raw_df = pd.DataFrame(
        _rows("1", blank, full)  # 외국인 빈 칸
        + _rows("2", full, blank)  # 기관 빈 칸
        + _rows("3", full, full)  # 정상
        # 창 밖(09-17)의 빈 칸은 최근 5행에 들지 않으므로 종목을 빼지 않는다
        + [{"ticker": "4", "date": "2026-09-17", "foreign_buy": np.nan, "inst_buy": np.nan}]
        + _rows("4", full, full)
    )

    result = build_supply_score_frame(
        raw_df,
        foreign_min=1,
        count_consecutive_positive=_count_consecutive_positive,
        logger=logging.getLogger(__name__),
    )

    assert sorted(result["ticker"]) == ["000003", "000004"]
    assert set(result["foreign_net_buy_5d"]) == {3_000_000_000}
