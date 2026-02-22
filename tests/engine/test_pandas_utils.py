#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import math
import os
import sys

import pandas as pd

sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

import engine.pandas_utils_io as pandas_utils_io
import services.kr_market_data_cache_core as cache_core
import services.kr_market_data_cache_service as cache_service
from engine.pandas_utils import (
    filter_by_date,
    filter_by_ticker,
    get_latest_values,
    load_json_file,
    merge_realtime_prices,
    safe_float,
    safe_int,
    safe_str,
    safe_value,
    sanitize_dataframe,
    sanitize_for_json,
    save_json_file,
    sort_signals_by_grade_and_score,
)


def _reset_data_cache_state() -> None:
    with cache_service.FILE_CACHE_LOCK:
        cache_service.JSON_FILE_CACHE.clear()
        cache_service.CSV_FILE_CACHE.clear()
        cache_service.LATEST_VCP_PRICE_MAP_CACHE["signature"] = None
        cache_service.LATEST_VCP_PRICE_MAP_CACHE["value"] = {}
        cache_service.SCANNED_STOCK_COUNT_CACHE["signature"] = None
        cache_service.SCANNED_STOCK_COUNT_CACHE["value"] = 0
        cache_service.BACKTEST_PRICE_SNAPSHOT_CACHE["signature"] = None
        cache_service.BACKTEST_PRICE_SNAPSHOT_CACHE["df"] = pd.DataFrame()
        cache_service.BACKTEST_PRICE_SNAPSHOT_CACHE["price_map"] = {}
        cache_service.JONGGA_RESULT_PAYLOADS_CACHE["signature"] = None
        cache_service.JONGGA_RESULT_PAYLOADS_CACHE["payloads"] = []
    cache_core._JSON_PAYLOAD_SQLITE_READY.clear()
    cache_core._CSV_PAYLOAD_SQLITE_READY.clear()


def test_safe_value_converters() -> None:
    assert safe_value(float('nan'), 10) == 10
    assert safe_int("12") == 12
    assert safe_int(float('nan'), 7) == 7
    assert safe_float("12.5") == 12.5
    assert safe_float(None, 1.5) == 1.5
    assert safe_str(float('nan'), "x") == "x"
    assert safe_str(123) == "123"


def test_save_and_load_json_file_roundtrip(tmp_path) -> None:
    target = tmp_path / "cache" / "sample.json"
    payload = {"ok": True, "name": "테스트", "count": 3}

    assert save_json_file(str(target), payload)
    loaded = load_json_file(str(target))
    assert loaded == payload


def test_load_json_file_returns_empty_for_non_dict_payload(tmp_path) -> None:
    target = tmp_path / "cache" / "list.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("[]", encoding="utf-8")

    assert load_json_file(str(target)) == {}


def test_save_json_file_uses_atomic_writer(monkeypatch, tmp_path) -> None:
    target = tmp_path / "cache" / "atomic.json"
    captured = {"path": None, "content": None}

    def _atomic_write(path: str, content: str):
        captured["path"] = path
        captured["content"] = content

    monkeypatch.setattr(pandas_utils_io, "atomic_write_text", _atomic_write)

    assert save_json_file(str(target), {"ok": True})
    assert captured["path"] == str(target)
    assert "\"ok\": true" in str(captured["content"]).lower()


def test_filter_by_date_does_not_mutate_source_dataframe() -> None:
    df = pd.DataFrame(
        {
            "date": ["2026-02-19", "2026-02-20", "2026-02-21"],
            "value": [1, 2, 3],
        }
    )

    filtered = filter_by_date(df, "date", target_date="2026-02-20")

    assert len(filtered) == 2
    assert df["date"].dtype == object
    assert df["date"].tolist() == ["2026-02-19", "2026-02-20", "2026-02-21"]


def test_filter_by_ticker_with_padding() -> None:
    df = pd.DataFrame(
        {
            "ticker": ["5930", "000660", "005930"],
            "name": ["삼성전자-a", "SK하이닉스", "삼성전자-b"],
        }
    )

    matched = filter_by_ticker(df, "5930")

    assert len(matched) == 2
    assert sorted(matched["name"].tolist()) == ["삼성전자-a", "삼성전자-b"]


def test_get_latest_values_returns_last_row_per_group() -> None:
    df = pd.DataFrame(
        {
            "ticker": ["005930", "005930", "000660"],
            "close": [70000, 71000, 150000],
            "date": ["2026-02-20", "2026-02-21", "2026-02-21"],
        }
    )

    latest = get_latest_values(df, "ticker", ["close", "date"])

    assert latest["005930"]["close"] == 71000
    assert latest["000660"]["date"] == "2026-02-21"


def test_merge_realtime_prices_updates_current_and_return_pct() -> None:
    signals = [
        {"ticker": "5930", "entry_price": 100.0},
        {"ticker": "000660", "entry_price": 0.0},
    ]
    prices = pd.DataFrame(
        {
            "ticker": ["005930", "000660"],
            "close": [110.0, 120.0],
            "date": ["2026-02-21", "2026-02-21"],
        }
    )

    merged = merge_realtime_prices(signals, prices)

    assert merged[0]["current_price"] == 110.0
    assert merged[0]["return_pct"] == 10.0
    assert merged[1]["current_price"] == 120.0
    assert "return_pct" not in merged[1]


def test_sort_signals_by_grade_and_score() -> None:
    signals = [
        {"ticker": "A", "grade": "B", "score": 95},
        {"ticker": "B", "grade": "S", "score": {"total": 60}},
        {"ticker": "C", "grade": "A", "score": {"total": 99}},
    ]

    sorted_signals = sort_signals_by_grade_and_score(signals)

    assert [s["ticker"] for s in sorted_signals] == ["B", "C", "A"]


def test_sanitize_for_json_nested_nan_and_inf() -> None:
    source = {
        "a": float('nan'),
        "b": [1.0, float('inf'), {"c": float('-inf')}],
    }

    sanitized = sanitize_for_json(source)

    assert sanitized["a"] is None
    assert sanitized["b"][1] is None
    assert sanitized["b"][2]["c"] is None


def test_sanitize_dataframe_nan_to_none() -> None:
    df = pd.DataFrame({"a": [1.0, float('nan')], "b": ["x", "y"]})

    rows = sanitize_dataframe(df)

    assert rows[0]["a"] == 1.0
    assert rows[1]["a"] is None
    assert rows[1]["b"] == "y"
    assert not math.isnan(rows[0]["a"])


def test_load_csv_file_uses_shared_sqlite_cache_after_memory_clear(monkeypatch, tmp_path) -> None:
    _reset_data_cache_state()
    csv_path = tmp_path / "sample.csv"
    pd.DataFrame(
        [
            {"ticker": "005930", "close": 100.0},
            {"ticker": "005930", "close": 111.0},
        ]
    ).to_csv(csv_path, index=False)

    first = pandas_utils_io.load_csv_file(str(csv_path), usecols=["ticker", "close"])
    assert len(first) == 2

    with cache_service.FILE_CACHE_LOCK:
        cache_service.CSV_FILE_CACHE.clear()

    monkeypatch.setattr(
        pandas_utils_io.pd,
        "read_csv",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("direct read_csv should not run")),
    )
    second = pandas_utils_io.load_csv_file(str(csv_path), usecols=["ticker", "close"])
    assert len(second) == 2
    assert float(second.iloc[-1]["close"]) == 111.0


def test_load_csv_file_skips_shared_cache_when_dtype_requested(monkeypatch, tmp_path) -> None:
    csv_path = tmp_path / "sample_dtype.csv"
    pd.DataFrame([{"ticker": "005930", "close": 111.0}]).to_csv(csv_path, index=False)

    monkeypatch.setattr(
        pandas_utils_io,
        "_load_csv_via_shared_cache",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("shared cache should not run")),
    )

    loaded = pandas_utils_io.load_csv_file(
        str(csv_path),
        dtype={"ticker": str},
    )
    assert len(loaded) == 1
    assert loaded.iloc[0]["ticker"] == "005930"


def test_load_csv_file_returns_cached_empty_dataframe_without_direct_reread(monkeypatch, tmp_path) -> None:
    _reset_data_cache_state()
    csv_path = tmp_path / "empty.csv"
    csv_path.write_text("ticker,close\n", encoding="utf-8")

    first = pandas_utils_io.load_csv_file(str(csv_path), usecols=["ticker", "close"])
    assert first.empty

    with cache_service.FILE_CACHE_LOCK:
        cache_service.CSV_FILE_CACHE.clear()

    monkeypatch.setattr(
        pandas_utils_io.pd,
        "read_csv",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("direct read_csv should not run for empty cache hit")),
    )
    second = pandas_utils_io.load_csv_file(str(csv_path), usecols=["ticker", "close"])
    assert second.empty
    assert list(second.columns) == ["ticker", "close"]
