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
