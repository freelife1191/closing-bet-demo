#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KR Market Analytics Service 리팩토링 회귀 테스트
"""

from __future__ import annotations

import os
import logging
import pandas as pd

import services.file_row_count_cache as file_row_count_cache
import services.kr_market_analytics_service as analytics_service
import services.kr_market_backtest_summary_cache as backtest_summary_cache
from services.kr_market_analytics_service import (
    build_backtest_summary_payload,
    build_data_status_payload,
    build_stock_chart_payload,
    clear_data_status_cache,
    resolve_chart_period_days,
)
from services.kr_market_backtest_summary_cache import clear_backtest_summary_cache


def test_resolve_chart_period_days_defaults_to_3m():
    assert resolve_chart_period_days("1m") == 30
    assert resolve_chart_period_days("6m") == 180
    assert resolve_chart_period_days("unknown") == 90
    assert resolve_chart_period_days(None) == 90


def test_build_stock_chart_payload_filters_by_ticker_and_numeric_validity():
    df = pd.DataFrame(
        [
            {"date": "2026-02-20", "ticker": "5930", "open": 100, "high": 110, "low": 90, "close": 105, "volume": 1000},
            {"date": "2026-02-21", "ticker": "005930", "open": 106, "high": 112, "low": 101, "close": 0, "volume": 2000},
            {"date": "2026-02-22", "ticker": "005930", "open": 107, "high": 115, "low": 102, "close": 111, "volume": 0},
            {"date": "2026-02-23", "ticker": "005930", "open": 108, "high": 116, "low": 103, "close": 112, "volume": 2500},
        ]
    )

    payload = build_stock_chart_payload(
        ticker="005930",
        period_days=365,
        load_csv_file=lambda _name: df,
    )

    assert payload["ticker"] == "005930"
    assert len(payload["data"]) == 2
    assert payload["data"][0]["close"] == 105.0
    assert payload["data"][1]["close"] == 112.0


def test_build_stock_chart_payload_normalizes_datetime_like_date_strings():
    df = pd.DataFrame(
        [
            {"date": "2025-11-26 00:00:00", "ticker": "005930", "open": 100, "high": 110, "low": 95, "close": 105, "volume": 1000},
            {"date": "20251127", "ticker": "005930", "open": 106, "high": 112, "low": 101, "close": 109, "volume": 1200},
        ]
    )

    payload = build_stock_chart_payload(
        ticker="005930",
        period_days=365,
        load_csv_file=lambda _name: df,
    )

    assert [row["date"] for row in payload["data"]] == ["2025-11-26", "2025-11-27"]


def test_build_stock_chart_payload_handles_missing_numeric_columns_and_reuses_ticker_padding():
    df = pd.DataFrame(
        [
            {"date": "2026-02-20", "ticker": "5930", "close": "101", "volume": "1234"},
            {"date": "2026-02-21", "ticker": "000660", "close": "202", "volume": "4567"},
        ]
    )
    assert "_ticker_padded" not in df.columns

    first = build_stock_chart_payload(
        ticker="005930",
        period_days=365,
        load_csv_file=lambda _name: df,
    )
    second = build_stock_chart_payload(
        ticker="005930",
        period_days=365,
        load_csv_file=lambda _name: df,
    )

    assert "_ticker_padded" in df.columns
    assert len(first["data"]) == 1
    assert first["data"][0]["open"] == 0.0
    assert first["data"][0]["high"] == 0.0
    assert first["data"][0]["low"] == 0.0
    assert first["data"][0]["close"] == 101.0
    assert first == second


def test_build_stock_chart_payload_returns_message_when_ticker_not_found():
    df = pd.DataFrame([{"date": "2026-02-20", "ticker": "000660", "close": 200, "volume": 1000}])

    payload = build_stock_chart_payload(
        ticker="005930",
        period_days=30,
        load_csv_file=lambda _name: df,
    )

    assert payload["ticker"] == "005930"
    assert payload["data"] == []
    assert payload["message"] == "해당 종목 데이터가 없습니다."


def test_build_data_status_payload_reuses_cache_when_file_signature_unchanged(tmp_path):
    clear_data_status_cache()
    file_row_count_cache.clear_file_row_count_cache()
    (tmp_path / "korean_stocks_list.csv").write_text("ticker\n005930\n", encoding="utf-8")
    (tmp_path / "daily_prices.csv").write_text("date,ticker,close\n2026-02-20,005930,100\n", encoding="utf-8")
    (tmp_path / "signals_log.csv").write_text("ticker\n005930\n", encoding="utf-8")
    (tmp_path / "market_gate.json").write_text('{"status":"BULL"}', encoding="utf-8")
    (tmp_path / "jongga_v2_latest.json").write_text('{"date":"2026-02-21"}', encoding="utf-8")

    row_count_calls = {"count": 0}
    json_calls: list[str] = []

    original_row_counter = file_row_count_cache.count_rows_for_path

    def _row_counter(path: str, logger):
        row_count_calls["count"] += 1
        return original_row_counter(path, logger)

    file_row_count_cache.count_rows_for_path = _row_counter

    def _load_json_file(name: str):
        json_calls.append(name)
        if name == "market_gate.json":
            return {"status": "BULL"}
        return {}

    get_data_path = lambda filename: str(tmp_path / filename)
    try:
        first = build_data_status_payload(get_data_path, lambda _name: pd.DataFrame(), _load_json_file)
        second = build_data_status_payload(get_data_path, lambda _name: pd.DataFrame(), _load_json_file)
    finally:
        file_row_count_cache.count_rows_for_path = original_row_counter

    assert first == second
    assert row_count_calls["count"] == 2
    assert json_calls == ["market_gate.json"]


def test_build_data_status_payload_requests_readonly_market_gate_load(tmp_path):
    clear_data_status_cache()
    file_row_count_cache.clear_file_row_count_cache()
    (tmp_path / "korean_stocks_list.csv").write_text("ticker\n005930\n", encoding="utf-8")
    (tmp_path / "daily_prices.csv").write_text("date,ticker,close\n2026-02-20,005930,100\n", encoding="utf-8")
    (tmp_path / "signals_log.csv").write_text("ticker\n005930\n", encoding="utf-8")
    (tmp_path / "market_gate.json").write_text('{"status":"BULL"}', encoding="utf-8")
    (tmp_path / "jongga_v2_latest.json").write_text('{"date":"2026-02-21"}', encoding="utf-8")

    captured = {"kwargs": None}

    def _load_json_file(name: str, **kwargs):
        if name == "market_gate.json":
            captured["kwargs"] = dict(kwargs)
            return {"status": "BULL"}
        return {}

    get_data_path = lambda filename: str(tmp_path / filename)
    payload = build_data_status_payload(
        get_data_path,
        lambda _name: pd.DataFrame(),
        _load_json_file,
    )

    assert payload["market_status"] == "BULL"
    assert captured["kwargs"]["deep_copy"] is False


def test_build_data_status_payload_invalidates_cache_when_file_mtime_changes(tmp_path):
    clear_data_status_cache()
    file_row_count_cache.clear_file_row_count_cache()
    signals_file = tmp_path / "signals_log.csv"
    (tmp_path / "korean_stocks_list.csv").write_text("ticker\n005930\n", encoding="utf-8")
    (tmp_path / "daily_prices.csv").write_text("date,ticker,close\n2026-02-20,005930,100\n", encoding="utf-8")
    signals_file.write_text("ticker\n005930\n", encoding="utf-8")
    (tmp_path / "market_gate.json").write_text('{"status":"BULL"}', encoding="utf-8")
    (tmp_path / "jongga_v2_latest.json").write_text('{"date":"2026-02-21"}', encoding="utf-8")

    calls = {"rows": 0, "json": 0}
    original_row_counter = file_row_count_cache.count_rows_for_path

    def _row_counter(path: str, logger):
        calls["rows"] += 1
        return original_row_counter(path, logger)

    def _load_json_file(_name: str):
        calls["json"] += 1
        return {"status": "BULL"}

    get_data_path = lambda filename: str(tmp_path / filename)
    file_row_count_cache.count_rows_for_path = _row_counter
    try:
        _ = build_data_status_payload(get_data_path, lambda _name: pd.DataFrame(), _load_json_file)
        first_calls = dict(calls)

        stat = signals_file.stat()
        updated_ns = stat.st_mtime_ns + 10_000_000
        os.utime(signals_file, ns=(updated_ns, updated_ns))

        _ = build_data_status_payload(get_data_path, lambda _name: pd.DataFrame(), _load_json_file)
    finally:
        file_row_count_cache.count_rows_for_path = original_row_counter

    assert calls["rows"] > first_calls["rows"]
    assert calls["json"] > first_calls["json"]


def test_build_data_status_payload_cache_is_bounded_lru(monkeypatch, tmp_path):
    clear_data_status_cache()
    file_row_count_cache.clear_file_row_count_cache()
    monkeypatch.setattr(analytics_service, "_DATA_STATUS_CACHE_MAX_ENTRIES", 2)

    def _prepare_data_dir(base_dir, status):
        base_dir.mkdir(parents=True, exist_ok=True)
        (base_dir / "korean_stocks_list.csv").write_text("ticker\n005930\n", encoding="utf-8")
        (base_dir / "daily_prices.csv").write_text("date,ticker,close\n2026-02-20,005930,100\n", encoding="utf-8")
        (base_dir / "signals_log.csv").write_text("ticker\n005930\n", encoding="utf-8")
        (base_dir / "market_gate.json").write_text(f'{{"status":"{status}"}}', encoding="utf-8")
        (base_dir / "jongga_v2_latest.json").write_text('{"date":"2026-02-21"}', encoding="utf-8")

    dir_a = tmp_path / "set_a"
    dir_b = tmp_path / "set_b"
    dir_c = tmp_path / "set_c"
    _prepare_data_dir(dir_a, "A")
    _prepare_data_dir(dir_b, "B")
    _prepare_data_dir(dir_c, "C")

    def _get_data_path_factory(base_dir):
        return lambda filename: str(base_dir / filename)

    def _load_json_file_factory(status):
        def _loader(name: str):
            if name == "market_gate.json":
                return {"status": status}
            return {}

        return _loader

    _ = build_data_status_payload(
        _get_data_path_factory(dir_a),
        lambda _name: pd.DataFrame(),
        _load_json_file_factory("A"),
    )
    _ = build_data_status_payload(
        _get_data_path_factory(dir_b),
        lambda _name: pd.DataFrame(),
        _load_json_file_factory("B"),
    )
    _ = build_data_status_payload(
        _get_data_path_factory(dir_a),
        lambda _name: pd.DataFrame(),
        _load_json_file_factory("A"),
    )
    _ = build_data_status_payload(
        _get_data_path_factory(dir_c),
        lambda _name: pd.DataFrame(),
        _load_json_file_factory("C"),
    )

    with analytics_service._DATA_STATUS_CACHE_LOCK:
        cache_statuses = {payload.get("market_status") for payload in analytics_service._DATA_STATUS_CACHE.values()}
        cache_size = len(analytics_service._DATA_STATUS_CACHE)

    assert cache_size == 2
    assert cache_statuses == {"A", "C"}


def test_build_backtest_summary_payload_reuses_signature_cache(tmp_path, monkeypatch):
    clear_backtest_summary_cache()
    monkeypatch.setattr(
        backtest_summary_cache,
        "_BACKTEST_SUMMARY_CACHE_DB_PATH",
        str(tmp_path / "runtime_cache.db"),
    )
    backtest_summary_cache._BACKTEST_SUMMARY_SQLITE_READY.clear()

    (tmp_path / "daily_prices.csv").write_text(
        "date,ticker,close,high,low\n2026-02-20,005930,100,110,90\n",
        encoding="utf-8",
    )
    (tmp_path / "signals_log.csv").write_text(
        "ticker,signal_date,entry_price\n005930,2026-02-20,100\n",
        encoding="utf-8",
    )
    (tmp_path / "jongga_v2_latest.json").write_text(
        '{"signals":[{"stock_code":"005930","entry_price":100}]}',
        encoding="utf-8",
    )
    history_file = tmp_path / "jongga_v2_results_2026-02-20.json"
    history_file.write_text(
        '{"date":"2026-02-20","signals":[{"stock_code":"005930","entry_price":100}]}',
        encoding="utf-8",
    )

    calls = {"json": 0, "price": 0, "history": 0, "signals": 0, "jb": 0, "vcp": 0}

    def _load_json_file(_name: str):
        calls["json"] += 1
        return {"signals": [{"stock_code": "005930", "entry_price": 100}]}

    def _load_backtest_price_snapshot():
        calls["price"] += 1
        df = pd.DataFrame(
            [
                {"date": "2026-02-20", "ticker": "005930", "close": 100, "high": 110, "low": 90},
            ]
        )
        return df, {"005930": 105.0}

    def _load_jongga_result_payloads(_limit: int):
        calls["history"] += 1
        return [(str(history_file), {"date": "2026-02-20", "signals": [{"stock_code": "005930"}]})]

    def _load_signals_csv(_name: str):
        calls["signals"] += 1
        return pd.DataFrame(
            [{"ticker": "005930", "signal_date": "2026-02-20", "entry_price": 100}]
        )

    def _calculate_jb(*_args, **_kwargs):
        calls["jb"] += 1
        return {"status": "OK", "count": 1, "win_rate": 100, "avg_return": 9.0, "candidates": []}

    def _calculate_vcp(*_args, **_kwargs):
        calls["vcp"] += 1
        return {"status": "OK", "count": 1, "win_rate": 100, "avg_return": 15.0}

    get_data_path = lambda filename: str(tmp_path / filename)
    data_dir_getter = lambda: str(tmp_path)
    logger = logging.getLogger("test-backtest-cache-hit")

    first = build_backtest_summary_payload(
        load_json_file=_load_json_file,
        load_backtest_price_snapshot=_load_backtest_price_snapshot,
        load_jongga_result_payloads=_load_jongga_result_payloads,
        calculate_jongga_backtest_stats=_calculate_jb,
        load_csv_file=_load_signals_csv,
        calculate_vcp_backtest_stats=_calculate_vcp,
        logger=logger,
        get_data_path=get_data_path,
        data_dir_getter=data_dir_getter,
    )
    second = build_backtest_summary_payload(
        load_json_file=_load_json_file,
        load_backtest_price_snapshot=_load_backtest_price_snapshot,
        load_jongga_result_payloads=_load_jongga_result_payloads,
        calculate_jongga_backtest_stats=_calculate_jb,
        load_csv_file=_load_signals_csv,
        calculate_vcp_backtest_stats=_calculate_vcp,
        logger=logger,
        get_data_path=get_data_path,
        data_dir_getter=data_dir_getter,
    )

    assert first == second
    assert calls == {"json": 1, "price": 1, "history": 1, "signals": 1, "jb": 1, "vcp": 1}


def test_build_backtest_summary_payload_requests_readonly_latest_payload(tmp_path):
    clear_backtest_summary_cache()
    (tmp_path / "daily_prices.csv").write_text(
        "date,ticker,close,high,low\n2026-02-20,005930,100,110,90\n",
        encoding="utf-8",
    )
    (tmp_path / "signals_log.csv").write_text(
        "ticker,signal_date,entry_price\n005930,2026-02-20,100\n",
        encoding="utf-8",
    )
    (tmp_path / "jongga_v2_latest.json").write_text(
        '{"signals":[{"stock_code":"005930","entry_price":100}]}',
        encoding="utf-8",
    )

    captured = {"kwargs": None}

    def _load_json_file(_name: str, **kwargs):
        captured["kwargs"] = dict(kwargs)
        return {"signals": [{"stock_code": "005930", "entry_price": 100}]}

    payload = build_backtest_summary_payload(
        load_json_file=_load_json_file,
        load_backtest_price_snapshot=lambda: (
            pd.DataFrame(
                [{"date": "2026-02-20", "ticker": "005930", "close": 100, "high": 110, "low": 90}]
            ),
            {"005930": 105.0},
        ),
        load_jongga_result_payloads=lambda _limit: [],
        calculate_jongga_backtest_stats=lambda *_args, **_kwargs: {
            "status": "Accumulating",
            "count": 0,
            "win_rate": 0,
            "avg_return": 0,
            "candidates": [],
        },
        load_csv_file=lambda _name: pd.DataFrame(
            [{"ticker": "005930", "signal_date": "2026-02-20", "entry_price": 100}]
        ),
        calculate_vcp_backtest_stats=lambda *_args, **_kwargs: {
            "status": "Accumulating",
            "count": 0,
            "win_rate": 0,
            "avg_return": 0,
        },
        logger=logging.getLogger("test-backtest-readonly"),
        get_data_path=lambda filename: str(tmp_path / filename),
        data_dir_getter=lambda: str(tmp_path),
    )

    assert payload["closing_bet"]["status"] == "Accumulating"
    assert captured["kwargs"]["deep_copy"] is False


def test_build_backtest_summary_payload_invalidates_cache_on_signature_change(tmp_path, monkeypatch):
    clear_backtest_summary_cache()
    monkeypatch.setattr(
        backtest_summary_cache,
        "_BACKTEST_SUMMARY_CACHE_DB_PATH",
        str(tmp_path / "runtime_cache.db"),
    )
    backtest_summary_cache._BACKTEST_SUMMARY_SQLITE_READY.clear()

    (tmp_path / "daily_prices.csv").write_text(
        "date,ticker,close,high,low\n2026-02-20,005930,100,110,90\n",
        encoding="utf-8",
    )
    signals_file = tmp_path / "signals_log.csv"
    signals_file.write_text(
        "ticker,signal_date,entry_price\n005930,2026-02-20,100\n",
        encoding="utf-8",
    )
    (tmp_path / "jongga_v2_latest.json").write_text(
        '{"signals":[{"stock_code":"005930","entry_price":100}]}',
        encoding="utf-8",
    )
    history_file = tmp_path / "jongga_v2_results_2026-02-20.json"
    history_file.write_text(
        '{"date":"2026-02-20","signals":[{"stock_code":"005930","entry_price":100}]}',
        encoding="utf-8",
    )

    calls = {"price": 0}

    def _load_json_file(_name: str):
        return {"signals": [{"stock_code": "005930", "entry_price": 100}]}

    def _load_backtest_price_snapshot():
        calls["price"] += 1
        df = pd.DataFrame(
            [
                {"date": "2026-02-20", "ticker": "005930", "close": 100, "high": 110, "low": 90},
            ]
        )
        return df, {"005930": 105.0}

    def _load_jongga_result_payloads(_limit: int):
        return [(str(history_file), {"date": "2026-02-20", "signals": [{"stock_code": "005930"}]})]

    def _load_signals_csv(_name: str):
        return pd.DataFrame(
            [{"ticker": "005930", "signal_date": "2026-02-20", "entry_price": 100}]
        )

    def _calculate_jb(*_args, **_kwargs):
        return {"status": "OK", "count": 1, "win_rate": 100, "avg_return": 9.0, "candidates": []}

    def _calculate_vcp(*_args, **_kwargs):
        return {"status": "OK", "count": 1, "win_rate": 100, "avg_return": 15.0}

    get_data_path = lambda filename: str(tmp_path / filename)
    data_dir_getter = lambda: str(tmp_path)
    logger = logging.getLogger("test-backtest-cache-invalidate")

    _ = build_backtest_summary_payload(
        load_json_file=_load_json_file,
        load_backtest_price_snapshot=_load_backtest_price_snapshot,
        load_jongga_result_payloads=_load_jongga_result_payloads,
        calculate_jongga_backtest_stats=_calculate_jb,
        load_csv_file=_load_signals_csv,
        calculate_vcp_backtest_stats=_calculate_vcp,
        logger=logger,
        get_data_path=get_data_path,
        data_dir_getter=data_dir_getter,
    )
    assert calls["price"] == 1

    stat = signals_file.stat()
    updated_ns = stat.st_mtime_ns + 10_000_000
    os.utime(signals_file, ns=(updated_ns, updated_ns))

    _ = build_backtest_summary_payload(
        load_json_file=_load_json_file,
        load_backtest_price_snapshot=_load_backtest_price_snapshot,
        load_jongga_result_payloads=_load_jongga_result_payloads,
        calculate_jongga_backtest_stats=_calculate_jb,
        load_csv_file=_load_signals_csv,
        calculate_vcp_backtest_stats=_calculate_vcp,
        logger=logger,
        get_data_path=get_data_path,
        data_dir_getter=data_dir_getter,
    )
    assert calls["price"] == 2


def test_build_backtest_summary_payload_uses_sqlite_snapshot_after_memory_clear(tmp_path, monkeypatch):
    clear_backtest_summary_cache()
    monkeypatch.setattr(
        backtest_summary_cache,
        "_BACKTEST_SUMMARY_CACHE_DB_PATH",
        str(tmp_path / "runtime_cache.db"),
    )
    backtest_summary_cache._BACKTEST_SUMMARY_SQLITE_READY.clear()

    (tmp_path / "daily_prices.csv").write_text(
        "date,ticker,close,high,low\n2026-02-20,005930,100,110,90\n",
        encoding="utf-8",
    )
    (tmp_path / "signals_log.csv").write_text(
        "ticker,signal_date,entry_price\n005930,2026-02-20,100\n",
        encoding="utf-8",
    )
    (tmp_path / "jongga_v2_latest.json").write_text(
        '{"signals":[{"stock_code":"005930","entry_price":100}]}',
        encoding="utf-8",
    )
    history_file = tmp_path / "jongga_v2_results_2026-02-20.json"
    history_file.write_text(
        '{"date":"2026-02-20","signals":[{"stock_code":"005930","entry_price":100}]}',
        encoding="utf-8",
    )

    get_data_path = lambda filename: str(tmp_path / filename)
    data_dir_getter = lambda: str(tmp_path)
    logger = logging.getLogger("test-backtest-cache-sqlite")

    first = build_backtest_summary_payload(
        load_json_file=lambda _name: {"signals": [{"stock_code": "005930", "entry_price": 100}]},
        load_backtest_price_snapshot=lambda: (
            pd.DataFrame(
                [{"date": "2026-02-20", "ticker": "005930", "close": 100, "high": 110, "low": 90}]
            ),
            {"005930": 105.0},
        ),
        load_jongga_result_payloads=lambda _limit: [
            (str(history_file), {"date": "2026-02-20", "signals": [{"stock_code": "005930"}]})
        ],
        calculate_jongga_backtest_stats=lambda *_a, **_k: {
            "status": "OK",
            "count": 1,
            "win_rate": 100,
            "avg_return": 9.0,
            "candidates": [],
        },
        load_csv_file=lambda _name: pd.DataFrame(
            [{"ticker": "005930", "signal_date": "2026-02-20", "entry_price": 100}]
        ),
        calculate_vcp_backtest_stats=lambda *_a, **_k: {
            "status": "OK",
            "count": 1,
            "win_rate": 100,
            "avg_return": 15.0,
        },
        logger=logger,
        get_data_path=get_data_path,
        data_dir_getter=data_dir_getter,
    )

    clear_backtest_summary_cache()
    second = build_backtest_summary_payload(
        load_json_file=lambda _name: (_ for _ in ()).throw(AssertionError("json loader should not run")),
        load_backtest_price_snapshot=lambda: (_ for _ in ()).throw(AssertionError("price loader should not run")),
        load_jongga_result_payloads=lambda _limit: (_ for _ in ()).throw(AssertionError("history loader should not run")),
        calculate_jongga_backtest_stats=lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("jb stats should not run")),
        load_csv_file=lambda _name: (_ for _ in ()).throw(AssertionError("signals loader should not run")),
        calculate_vcp_backtest_stats=lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("vcp stats should not run")),
        logger=logger,
        get_data_path=get_data_path,
        data_dir_getter=data_dir_getter,
    )

    assert first == second


def test_build_backtest_summary_payload_builds_price_index_once(monkeypatch):
    calls = {"build_index": 0, "jb": 0, "vcp": 0}
    shared_index = {"005930": pd.DataFrame([{"close": 100}])}

    def _build_index_once(_df: pd.DataFrame):
        calls["build_index"] += 1
        return shared_index

    monkeypatch.setattr(analytics_service, "build_ticker_price_index", _build_index_once)

    def _load_backtest_price_snapshot():
        df = pd.DataFrame(
            [
                {"date": "2026-02-20", "ticker": "005930", "close": 100, "high": 110, "low": 90},
            ]
        )
        return df, {"005930": 105.0}

    def _calculate_jb(_candidates, _history_payloads, _price_map, _price_df, **kwargs):
        calls["jb"] += 1
        assert kwargs.get("price_index") is shared_index
        return {"status": "OK", "count": 1, "win_rate": 100, "avg_return": 9.0, "candidates": []}

    def _calculate_vcp(_vcp_df, _price_map, _price_df, **kwargs):
        calls["vcp"] += 1
        assert kwargs.get("price_index") is shared_index
        return {"status": "OK", "count": 1, "win_rate": 100, "avg_return": 15.0}

    payload = build_backtest_summary_payload(
        load_json_file=lambda _name: {"signals": [{"stock_code": "005930", "entry_price": 100}]},
        load_backtest_price_snapshot=_load_backtest_price_snapshot,
        load_jongga_result_payloads=lambda _limit: [
            ("jongga_v2_results_20260220.json", {"date": "2026-02-20", "signals": [{"stock_code": "005930"}]}),
        ],
        calculate_jongga_backtest_stats=_calculate_jb,
        load_csv_file=lambda _name: pd.DataFrame(
            [{"ticker": "005930", "signal_date": "2026-02-20", "entry_price": 100}]
        ),
        calculate_vcp_backtest_stats=_calculate_vcp,
        logger=logging.getLogger("test-backtest-price-index-once"),
    )

    assert payload["closing_bet"]["status"] == "OK"
    assert payload["vcp"]["status"] == "OK"
    assert calls == {"build_index": 1, "jb": 1, "vcp": 1}


def test_build_backtest_summary_payload_supports_legacy_stats_callable_signature(monkeypatch):
    calls = {"jb": 0, "vcp": 0}

    monkeypatch.setattr(
        analytics_service,
        "build_ticker_price_index",
        lambda _df: {"005930": pd.DataFrame([{"close": 100}])},
    )

    def _legacy_jb(_candidates, _history_payloads, _price_map, _price_df):
        calls["jb"] += 1
        return {"status": "OK", "count": 1, "win_rate": 100, "avg_return": 9.0, "candidates": []}

    def _legacy_vcp(_vcp_df, _price_map, _price_df):
        calls["vcp"] += 1
        return {"status": "OK", "count": 1, "win_rate": 100, "avg_return": 15.0}

    payload = build_backtest_summary_payload(
        load_json_file=lambda _name: {"signals": [{"stock_code": "005930", "entry_price": 100}]},
        load_backtest_price_snapshot=lambda: (
            pd.DataFrame(
                [{"date": "2026-02-20", "ticker": "005930", "close": 100, "high": 110, "low": 90}]
            ),
            {"005930": 105.0},
        ),
        load_jongga_result_payloads=lambda _limit: [
            ("jongga_v2_results_20260220.json", {"date": "2026-02-20", "signals": [{"stock_code": "005930"}]}),
        ],
        calculate_jongga_backtest_stats=_legacy_jb,
        load_csv_file=lambda _name: pd.DataFrame(
            [{"ticker": "005930", "signal_date": "2026-02-20", "entry_price": 100}]
        ),
        calculate_vcp_backtest_stats=_legacy_vcp,
        logger=logging.getLogger("test-backtest-legacy-signature"),
    )

    assert payload["closing_bet"]["status"] == "OK"
    assert payload["vcp"]["status"] == "OK"
    assert calls == {"jb": 1, "vcp": 1}
