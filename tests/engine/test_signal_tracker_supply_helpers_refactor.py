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
            # 4행 종목. [FLOW-025] 이후 최신 날짜가 빠지면 그날이 부분 날짜(전날의 80% 미만)가 되므로 가장 오래된 날을 뺀다
            {"ticker": "3", "date": "2026-02-02", "foreign_buy": 500_000_000, "inst_buy": 300_000_000},
            {"ticker": "3", "date": "2026-02-03", "foreign_buy": 500_000_000, "inst_buy": 300_000_000},
            {"ticker": "3", "date": "2026-02-04", "foreign_buy": 500_000_000, "inst_buy": 300_000_000},
            {"ticker": "3", "date": "2026-02-05", "foreign_buy": 500_000_000, "inst_buy": 300_000_000},
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


def test_build_supply_score_frame_drops_tickers_missing_a_day_in_the_window():
    """[FLOW-025] 마지막 5행 대신 모든 종목에 공통인 최근 5거래일을 쓴다. 하루라도 행이 없으면 점수에서 뺀다."""
    dates = ["2026-09-17", "2026-09-18", "2026-09-21", "2026-09-22", "2026-09-23", "2026-09-24"]

    def _rows(ticker, skip=None):
        return [
            {"ticker": ticker, "date": day, "foreign_buy": 600_000_000, "inst_buy": 300_000_000}
            for day in dates if day != skip
        ]

    raw_df = pd.DataFrame(
        _rows("1", skip="2026-09-22")  # 창 안의 하루가 빠져 마지막 5행이 6거래일에 걸친다
        + _rows("2", skip="2026-09-24")  # 최신 날짜가 빠져 창이 하루 앞에서 끝난다
        + _rows("3")
        + _rows("4", skip="2026-09-17")  # 창 밖 날짜만 빠졌다
        # 정상 종목을 더 둔다. 2 의 09-24 누락 하나가 그날을 부분 날짜(전날의 80% 미만)로 만들지 않게 한다
        + [row for n in range(5, 9) for row in _rows(str(n))]
    )

    result = build_supply_score_frame(
        raw_df,
        foreign_min=1,
        count_consecutive_positive=_count_consecutive_positive,
        logger=logging.getLogger(__name__),
    )

    assert sorted(result["ticker"]) == [f"00000{n}" for n in (3, 4, 5, 6, 7, 8)]
    assert set(result["foreign_net_buy_5d"]) == {3_000_000_000}
    assert set(result["supply_demand_index"]) == {100}
