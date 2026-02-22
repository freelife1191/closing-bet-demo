#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KR Market CSV 유틸 테스트
"""

from __future__ import annotations

import pandas as pd

from services.kr_market_csv_utils import (
    build_latest_close_map_from_prices_df,
    get_ticker_padded_series,
    load_csv_readonly,
)


def test_load_csv_readonly_prefers_deep_copy_and_usecols():
    captured: dict[str, object] = {}

    def _loader(name: str, **kwargs):
        captured["name"] = name
        captured["kwargs"] = kwargs
        return pd.DataFrame()

    load_csv_readonly(_loader, "signals_log.csv", usecols=["signal_date"])

    assert captured["name"] == "signals_log.csv"
    assert captured["kwargs"] == {"deep_copy": False, "usecols": ["signal_date"]}


def test_load_csv_readonly_falls_back_when_loader_does_not_accept_kwargs():
    calls: list[dict[str, object]] = []

    def _loader(_name: str, **kwargs):
        calls.append(dict(kwargs))
        if kwargs:
            raise TypeError("unexpected kwargs")
        return pd.DataFrame([{"ok": 1}])

    result = load_csv_readonly(_loader, "signals_log.csv", usecols=["signal_date"])

    assert len(result) == 1
    assert calls == [
        {"deep_copy": False, "usecols": ["signal_date"]},
        {"usecols": ["signal_date"]},
        {},
    ]


def test_load_csv_readonly_reuses_fallback_strategy_cache_on_second_call():
    calls: list[dict[str, object]] = []

    def _loader(_name: str, **kwargs):
        calls.append(dict(kwargs))
        if kwargs:
            raise TypeError("unexpected kwargs")
        return pd.DataFrame([{"ok": 1}])

    first = load_csv_readonly(_loader, "signals_log.csv", usecols=["signal_date"])
    second = load_csv_readonly(_loader, "signals_log.csv", usecols=["signal_date"])

    assert len(first) == 1
    assert len(second) == 1
    assert calls == [
        {"deep_copy": False, "usecols": ["signal_date"]},
        {"usecols": ["signal_date"]},
        {},
        {},
    ]


def test_load_csv_readonly_retries_without_usecols_on_value_error():
    calls: list[dict[str, object]] = []

    def _loader(_name: str, **kwargs):
        calls.append(dict(kwargs))
        if "usecols" in kwargs:
            raise ValueError("bad usecols")
        return pd.DataFrame([{"ok": 1}])

    result = load_csv_readonly(_loader, "signals_log.csv", usecols=["signal_date"])

    assert len(result) == 1
    assert calls == [
        {"deep_copy": False, "usecols": ["signal_date"]},
        {"deep_copy": False},
    ]


def test_get_ticker_padded_series_reuses_cache_column():
    df = pd.DataFrame({"ticker": [5930, 660]})

    first = get_ticker_padded_series(df)
    second = get_ticker_padded_series(df)

    assert first.tolist() == ["005930", "000660"]
    assert second.tolist() == ["005930", "000660"]
    assert "_ticker_padded" in df.columns


def test_build_latest_close_map_from_prices_df_uses_latest_on_unsorted_iso_dates():
    df = pd.DataFrame(
        [
            {"date": "2026-02-22", "ticker": "5930", "close": 120.0},
            {"date": "2026-02-20", "ticker": "5930", "close": 100.0},
            {"date": "2026-02-21", "ticker": "000660", "close": 200.0},
        ]
    )

    result = build_latest_close_map_from_prices_df(df)

    assert result["005930"] == 120.0
    assert result["000660"] == 200.0


def test_build_latest_close_map_from_prices_df_parses_non_iso_dates():
    df = pd.DataFrame(
        [
            {"date": "2026/02/20", "ticker": "005930", "close": 100.0},
            {"date": "2026/02/22", "ticker": "005930", "close": 130.0},
        ]
    )

    result = build_latest_close_map_from_prices_df(df)

    assert result["005930"] == 130.0


def test_build_latest_close_map_from_prices_df_skips_invalid_close():
    df = pd.DataFrame(
        [
            {"date": "2026-02-20", "ticker": "005930", "close": "N/A"},
            {"date": "2026-02-21", "ticker": "005930", "close": 130.0},
            {"date": "2026-02-22", "ticker": "000660", "close": "bad"},
        ]
    )

    result = build_latest_close_map_from_prices_df(df)

    assert result["005930"] == 130.0
    assert "000660" not in result
