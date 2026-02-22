#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Screener runtime helper 분해 회귀 테스트
"""

from __future__ import annotations

import logging

import pandas as pd

from engine.screener_runtime_helpers import (
    build_stock_candidate,
    prioritize_stocks_by_supply,
)


def test_prioritize_stocks_by_supply_sorts_by_recent_5d_supply_sum():
    stocks_df = pd.DataFrame(
        [
            {"ticker": "000660", "name": "SK", "market": "KOSPI"},
            {"ticker": "005930", "name": "삼성전자", "market": "KOSPI"},
        ]
    )
    inst_df = pd.DataFrame(
        [
            {"ticker": "005930", "date": pd.Timestamp("2026-02-20"), "foreign_buy": 10, "inst_buy": 5},
            {"ticker": "005930", "date": pd.Timestamp("2026-02-21"), "foreign_buy": 8, "inst_buy": 4},
            {"ticker": "005930", "date": pd.Timestamp("2026-02-22"), "foreign_buy": 8, "inst_buy": 4},
            {"ticker": "005930", "date": pd.Timestamp("2026-02-23"), "foreign_buy": 8, "inst_buy": 4},
            {"ticker": "005930", "date": pd.Timestamp("2026-02-24"), "foreign_buy": 8, "inst_buy": 4},
            {"ticker": "000660", "date": pd.Timestamp("2026-02-20"), "foreign_buy": 1, "inst_buy": 1},
            {"ticker": "000660", "date": pd.Timestamp("2026-02-21"), "foreign_buy": 1, "inst_buy": 1},
            {"ticker": "000660", "date": pd.Timestamp("2026-02-22"), "foreign_buy": 1, "inst_buy": 1},
            {"ticker": "000660", "date": pd.Timestamp("2026-02-23"), "foreign_buy": 1, "inst_buy": 1},
            {"ticker": "000660", "date": pd.Timestamp("2026-02-24"), "foreign_buy": 1, "inst_buy": 1},
        ]
    )

    sorted_df = prioritize_stocks_by_supply(
        stocks_df=stocks_df,
        inst_df=inst_df,
        target_date="2026-02-24",
        logger=logging.getLogger("test"),
    )

    assert sorted_df.iloc[0]["ticker"] == "005930"
    assert sorted_df.iloc[1]["ticker"] == "000660"


def test_prioritize_stocks_by_supply_keeps_original_order_when_inst_empty():
    stocks_df = pd.DataFrame(
        [
            {"ticker": "123", "name": "A", "market": "KOSDAQ"},
            {"ticker": "45", "name": "B", "market": "KOSPI"},
        ]
    )

    sorted_df = prioritize_stocks_by_supply(
        stocks_df=stocks_df,
        inst_df=pd.DataFrame(),
        target_date=None,
        logger=logging.getLogger("test"),
    )

    assert sorted_df["ticker"].tolist() == ["000123", "000045"]


def test_build_stock_candidate_normalizes_row_shape():
    row = type("Row", (), {"ticker": "1234", "name": "테스트", "market": "KOSDAQ"})()
    candidate = build_stock_candidate(row)

    assert candidate == {"ticker": "001234", "name": "테스트", "market": "KOSDAQ"}


def test_prioritize_stocks_by_supply_normalizes_inst_tickers_before_join():
    stocks_df = pd.DataFrame(
        [
            {"ticker": "5930", "name": "삼성전자", "market": "KOSPI"},
            {"ticker": "660", "name": "SK", "market": "KOSPI"},
        ]
    )
    inst_df = pd.DataFrame(
        [
            {"ticker": "5930", "date": pd.Timestamp("2026-02-24"), "foreign_buy": 10, "inst_buy": 10},
            {"ticker": "5930", "date": pd.Timestamp("2026-02-23"), "foreign_buy": 10, "inst_buy": 10},
            {"ticker": "5930", "date": pd.Timestamp("2026-02-22"), "foreign_buy": 10, "inst_buy": 10},
            {"ticker": "5930", "date": pd.Timestamp("2026-02-21"), "foreign_buy": 10, "inst_buy": 10},
            {"ticker": "5930", "date": pd.Timestamp("2026-02-20"), "foreign_buy": 10, "inst_buy": 10},
            {"ticker": "660", "date": pd.Timestamp("2026-02-24"), "foreign_buy": 1, "inst_buy": 1},
            {"ticker": "660", "date": pd.Timestamp("2026-02-23"), "foreign_buy": 1, "inst_buy": 1},
            {"ticker": "660", "date": pd.Timestamp("2026-02-22"), "foreign_buy": 1, "inst_buy": 1},
            {"ticker": "660", "date": pd.Timestamp("2026-02-21"), "foreign_buy": 1, "inst_buy": 1},
            {"ticker": "660", "date": pd.Timestamp("2026-02-20"), "foreign_buy": 1, "inst_buy": 1},
        ]
    )

    sorted_df = prioritize_stocks_by_supply(
        stocks_df=stocks_df,
        inst_df=inst_df,
        target_date="2026-02-24",
        logger=logging.getLogger("test"),
    )

    assert sorted_df.iloc[0]["ticker"] == "005930"
    assert sorted_df.iloc[1]["ticker"] == "000660"
