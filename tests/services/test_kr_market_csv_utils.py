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
    recent_trading_dates,
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


def test_load_csv_readonly_projects_columns_when_plain_strategy_cached():
    calls: list[dict[str, object]] = []

    def _loader(_name: str, **kwargs):
        calls.append(dict(kwargs))
        if kwargs:
            raise TypeError("unexpected kwargs")
        return pd.DataFrame(
            [
                {"signal_date": "2026-02-21", "ticker": "005930", "score": 10},
            ]
        )

    first = load_csv_readonly(_loader, "signals_log.csv", usecols=["signal_date"])
    second = load_csv_readonly(_loader, "signals_log.csv", usecols=["signal_date"])

    assert list(first.columns) == ["signal_date"]
    assert list(second.columns) == ["signal_date"]
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
    assert list(result.columns) == ["ok"]
    assert calls == [
        {"deep_copy": False, "usecols": ["signal_date"]},
        {"deep_copy": False},
    ]


def test_load_csv_readonly_projects_existing_columns_on_value_error_fallback():
    calls: list[dict[str, object]] = []

    def _loader(_name: str, **kwargs):
        calls.append(dict(kwargs))
        if "usecols" in kwargs:
            raise ValueError("bad usecols")
        return pd.DataFrame([{"signal_date": "2026-02-21", "ticker": "005930", "score": 10}])

    result = load_csv_readonly(
        _loader,
        "signals_log.csv",
        usecols=["signal_date", "missing_column"],
    )

    assert len(result) == 1
    assert list(result.columns) == ["signal_date"]
    assert calls == [
        {"deep_copy": False, "usecols": ["signal_date", "missing_column"]},
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


def _dates(counts: dict[str, int]) -> pd.Series:
    return pd.to_datetime(pd.Series([day for day, n in counts.items() for _ in range(n)]))


def test_recent_trading_dates_drops_partial_latest_dates():
    """[FLOW-025] 최신 날짜가 전날 행 수의 80% 에 못 미치면 수집이 덜 끝난 날이다. 행 수가 계속 줄어드는 끝쪽 날짜는 연달아 뺀다."""
    dates = _dates({"2026-09-15": 10, "2026-09-16": 10, "2026-09-17": 10, "2026-09-18": 10,
                    "2026-09-21": 10, "2026-09-22": 7, "2026-09-23": 2})
    assert [d.strftime("%Y-%m-%d") for d in recent_trading_dates(dates)] == [
        "2026-09-15", "2026-09-16", "2026-09-17", "2026-09-18", "2026-09-21"]


def test_recent_trading_dates_keeps_a_latest_date_with_more_rows():
    """[FLOW-025] 신규 상장으로 행이 늘어난 날은 부분 날짜가 아니다. 이전 날짜도 버리지 않는다."""
    dates = _dates({"2026-09-16": 1, "2026-09-17": 1, "2026-09-18": 1, "2026-09-21": 1, "2026-09-22": 3})
    assert len(recent_trading_dates(dates)) == 5


def test_recent_trading_dates_keeps_a_latest_date_at_exactly_the_ratio():
    """[FLOW-025] 전날의 딱 80% 인 날은 부분 날짜가 아니다(미만만 뺀다)."""
    dates = _dates({"2026-09-16": 10, "2026-09-17": 10, "2026-09-18": 10, "2026-09-21": 10, "2026-09-22": 8})
    assert recent_trading_dates(dates)[-1] == pd.Timestamp("2026-09-22")
