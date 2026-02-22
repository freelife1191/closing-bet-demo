#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GlobalDataFetcher 회귀 테스트
"""

import pandas as pd

from engine.data_sources import GlobalDataFetcher


class _DummyManager:
    def __init__(self, index_map=None, stock_map=None):
        self.index_map = index_map or {}
        self.stock_map = stock_map or {}

    def fetch_index_data(self, symbol, start_date, end_date=None):
        del start_date, end_date
        return self.index_map.get(symbol, pd.DataFrame())

    def fetch_stock_data(self, ticker, start_date, end_date=None):
        del start_date, end_date
        return self.stock_map.get(ticker, pd.DataFrame())


def _build_close_df(values):
    return pd.DataFrame({"close": values})


def test_extract_valid_value_pair_skips_nan_and_zero():
    fetcher = GlobalDataFetcher(manager=_DummyManager())
    df = _build_close_df([100, 0, float("nan"), 110])

    pair = fetcher._extract_valid_value_pair(df, "sp500", "Index")

    assert pair == {"value": 110.0, "change_pct": 10.0}


def test_extract_valid_value_pair_returns_none_without_two_valid_points():
    fetcher = GlobalDataFetcher(manager=_DummyManager())
    df = _build_close_df([0, float("nan"), 120])

    assert fetcher._extract_valid_value_pair(df, "gold", "Commodity") is None


def test_fetch_commodities_merges_global_and_krx_results():
    manager = _DummyManager(
        index_map={
            "GC=F": _build_close_df([2000, 2020]),
            "SI=F": _build_close_df([25, 24]),
        },
        stock_map={
            "132030": _build_close_df([10000, 10100]),
            "144600": _build_close_df([5000, 5050]),
        },
    )
    fetcher = GlobalDataFetcher(manager=manager)

    result = fetcher.fetch_commodities(start_date="2026-01-01", end_date="2026-02-21")

    assert set(result.keys()) == {"gold", "silver", "krx_gold", "krx_silver"}
    assert result["gold"]["value"] == 2020.0
    assert result["krx_gold"]["value"] == 10100.0
