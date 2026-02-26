#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KR Market Data Cache Service 리팩토링 회귀 테스트
"""

from __future__ import annotations

import logging
import json
import os
import sqlite3
import threading
import time

import pandas as pd

import services.kr_market_data_cache_prices as cache_prices
import services.kr_market_data_cache_core as cache_core
import services.kr_market_data_cache_jongga as cache_jongga
import services.kr_market_data_cache_service as cache_service
from services.sqlite_utils import connect_sqlite


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


def test_load_latest_price_map_reuses_backtest_snapshot_cache(monkeypatch, tmp_path):
    _reset_data_cache_state()
    daily_prices = tmp_path / "daily_prices.csv"
    pd.DataFrame(
        [
            {"date": "2026-02-20", "ticker": "5930", "close": 100.0, "high": 101.0, "low": 99.0},
            {"date": "2026-02-21", "ticker": "5930", "close": 110.0, "high": 111.0, "low": 109.0},
        ]
    ).to_csv(daily_prices, index=False)

    cache_service.load_backtest_price_snapshot(
        data_dir=str(tmp_path),
        build_latest_price_map=lambda df: {"005930": float(df["close"].iloc[-1])},
    )

    monkeypatch.setattr(
        cache_prices.pd,
        "read_csv",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("read_csv should not be called")),
    )
    latest_price_map = cache_service.load_latest_vcp_price_map(
        data_dir=str(tmp_path),
        logger=logging.getLogger(__name__),
    )

    assert latest_price_map["005930"] == 110.0


def test_load_backtest_snapshot_reuses_latest_price_map_cache(tmp_path):
    _reset_data_cache_state()
    daily_prices = tmp_path / "daily_prices.csv"
    pd.DataFrame(
        [
            {"date": "2026-02-20", "ticker": "005930", "close": 100.0, "high": 101.0, "low": 99.0},
            {"date": "2026-02-21", "ticker": "005930", "close": 111.0, "high": 113.0, "low": 108.0},
        ]
    ).to_csv(daily_prices, index=False)

    cache_service.load_latest_vcp_price_map(
        data_dir=str(tmp_path),
        logger=logging.getLogger(__name__),
    )

    called = {"build_latest_price_map": 0}

    def _should_not_run(_df):
        called["build_latest_price_map"] += 1
        raise AssertionError("build_latest_price_map should not be called when latest cache exists")

    df_prices, latest_map = cache_service.load_backtest_price_snapshot(
        data_dir=str(tmp_path),
        build_latest_price_map=_should_not_run,
    )

    assert len(df_prices) == 2
    assert latest_map["005930"] == 111.0
    assert called["build_latest_price_map"] == 0


def test_load_jongga_result_payloads_reuses_json_cache_without_reopening(monkeypatch, tmp_path):
    _reset_data_cache_state()
    result_file = tmp_path / "jongga_v2_results_20260222.json"
    result_file.write_text(
        json.dumps({"date": "2026-02-22", "signals": [{"stock_code": "005930"}]}, ensure_ascii=False),
        encoding="utf-8",
    )

    first = cache_service.load_jongga_result_payloads(data_dir=str(tmp_path), limit=0)
    assert len(first) == 1

    monkeypatch.setattr(
        "builtins.open",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("open should not be called")),
    )
    second = cache_service.load_jongga_result_payloads(data_dir=str(tmp_path), limit=0)

    assert len(second) == 1
    assert second[0][1]["date"] == "2026-02-22"


def test_load_jongga_result_payloads_respects_limit_before_loading(monkeypatch, tmp_path):
    _reset_data_cache_state()
    for day in range(1, 6):
        (tmp_path / f"jongga_v2_results_2026020{day}.json").write_text(
            json.dumps({"date": f"2026-02-0{day}", "signals": [{"stock_code": "005930"}]}, ensure_ascii=False),
            encoding="utf-8",
        )

    calls = {"count": 0}

    def _counted_loader(_path: str, *, signature=None):
        calls["count"] += 1
        return {"date": "2026-02-05", "signals": [{"stock_code": "005930"}]}

    monkeypatch.setattr(cache_jongga, "_load_json_payload_from_path", _counted_loader)

    first = cache_service.load_jongga_result_payloads(data_dir=str(tmp_path), limit=2)
    second = cache_service.load_jongga_result_payloads(data_dir=str(tmp_path), limit=2)

    assert len(first) == 2
    assert len(second) == 2
    assert calls["count"] == 2


def test_load_jongga_result_payloads_uses_sqlite_snapshot_after_memory_clear(monkeypatch, tmp_path):
    _reset_data_cache_state()
    monkeypatch.setattr(
        cache_jongga,
        "_JONGGA_PAYLOAD_SQLITE_DB_PATH",
        str(tmp_path / "runtime_cache.db"),
    )
    cache_jongga._JONGGA_PAYLOAD_SQLITE_READY.clear()

    result_file = tmp_path / "jongga_v2_results_20260222.json"
    result_file.write_text(
        json.dumps({"date": "2026-02-22", "signals": [{"stock_code": "005930"}]}, ensure_ascii=False),
        encoding="utf-8",
    )

    first = cache_service.load_jongga_result_payloads(data_dir=str(tmp_path), limit=0)
    assert len(first) == 1

    with cache_service.FILE_CACHE_LOCK:
        cache_service.JONGGA_RESULT_PAYLOADS_CACHE["signature"] = None
        cache_service.JONGGA_RESULT_PAYLOADS_CACHE["payloads"] = []

    monkeypatch.setattr(
        cache_jongga,
        "_load_json_payload_from_path",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("json file loader should not run")),
    )
    second = cache_service.load_jongga_result_payloads(data_dir=str(tmp_path), limit=0)

    assert len(second) == 1
    assert second[0][1]["date"] == "2026-02-22"


def test_load_jongga_result_payloads_sqlite_load_uses_read_only_connection(monkeypatch, tmp_path):
    _reset_data_cache_state()
    monkeypatch.setattr(
        cache_jongga,
        "_JONGGA_PAYLOAD_SQLITE_DB_PATH",
        str(tmp_path / "runtime_cache.db"),
    )
    cache_jongga._JONGGA_PAYLOAD_SQLITE_READY.clear()

    result_file = tmp_path / "jongga_v2_results_20260222.json"
    result_file.write_text(
        json.dumps({"date": "2026-02-22", "signals": [{"stock_code": "005930"}]}, ensure_ascii=False),
        encoding="utf-8",
    )

    first = cache_service.load_jongga_result_payloads(data_dir=str(tmp_path), limit=0)
    assert len(first) == 1

    with cache_service.FILE_CACHE_LOCK:
        cache_service.JONGGA_RESULT_PAYLOADS_CACHE["signature"] = None
        cache_service.JONGGA_RESULT_PAYLOADS_CACHE["payloads"] = []

    read_only_flags: list[bool] = []
    original_connect = cache_jongga.connect_sqlite

    def _traced_connect(*args, **kwargs):
        if "read_only" in kwargs:
            read_only_flags.append(bool(kwargs["read_only"]))
        return original_connect(*args, **kwargs)

    monkeypatch.setattr(cache_jongga, "connect_sqlite", _traced_connect)

    second = cache_service.load_jongga_result_payloads(data_dir=str(tmp_path), limit=0)
    assert len(second) == 1
    assert second[0][1]["date"] == "2026-02-22"
    assert True in read_only_flags


def test_load_jongga_result_payloads_prunes_sqlite_cache_rows(monkeypatch, tmp_path):
    _reset_data_cache_state()
    monkeypatch.setattr(
        cache_jongga,
        "_JONGGA_PAYLOAD_SQLITE_DB_PATH",
        str(tmp_path / "runtime_cache.db"),
    )
    monkeypatch.setattr(cache_jongga, "_JONGGA_PAYLOAD_SQLITE_MAX_ROWS", 2)
    cache_jongga._JONGGA_PAYLOAD_SQLITE_READY.clear()

    for day in range(1, 5):
        (tmp_path / f"jongga_v2_results_2026020{day}.json").write_text(
            json.dumps({"date": f"2026-02-0{day}", "signals": [{"stock_code": "005930"}]}, ensure_ascii=False),
            encoding="utf-8",
        )
        _ = cache_service.load_jongga_result_payloads(data_dir=str(tmp_path), limit=0)

    with connect_sqlite(str(tmp_path / "runtime_cache.db")) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM jongga_results_payload_cache")
        row_count = int(cursor.fetchone()[0])

    assert row_count == 2


def test_load_jongga_result_payloads_creates_sqlite_parent_dir_when_missing(monkeypatch, tmp_path):
    _reset_data_cache_state()
    db_path = tmp_path / "cache" / "nested" / "runtime_cache.db"
    monkeypatch.setattr(cache_jongga, "_JONGGA_PAYLOAD_SQLITE_DB_PATH", str(db_path))
    cache_jongga._JONGGA_PAYLOAD_SQLITE_READY.clear()

    result_file = tmp_path / "jongga_v2_results_20260222.json"
    result_file.write_text(
        json.dumps({"date": "2026-02-22", "signals": [{"stock_code": "005930"}]}, ensure_ascii=False),
        encoding="utf-8",
    )

    payloads = cache_service.load_jongga_result_payloads(data_dir=str(tmp_path), limit=0)

    assert len(payloads) == 1
    assert db_path.exists()

    with connect_sqlite(str(db_path)) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM jongga_results_payload_cache")
        row_count = int(cursor.fetchone()[0])
    assert row_count >= 1


def test_load_jongga_result_payloads_recovers_when_sqlite_table_missing(monkeypatch, tmp_path):
    _reset_data_cache_state()
    monkeypatch.setattr(
        cache_jongga,
        "_JONGGA_PAYLOAD_SQLITE_DB_PATH",
        str(tmp_path / "runtime_cache.db"),
    )
    cache_jongga._JONGGA_PAYLOAD_SQLITE_READY.clear()

    result_file = tmp_path / "jongga_v2_results_20260222.json"
    result_file.write_text(
        json.dumps({"date": "2026-02-22", "signals": [{"stock_code": "005930"}]}, ensure_ascii=False),
        encoding="utf-8",
    )

    first = cache_service.load_jongga_result_payloads(data_dir=str(tmp_path), limit=0)
    assert len(first) == 1

    with connect_sqlite(str(tmp_path / "runtime_cache.db")) as conn:
        conn.execute("DROP TABLE jongga_results_payload_cache")
        conn.commit()

    with cache_service.FILE_CACHE_LOCK:
        cache_service.JONGGA_RESULT_PAYLOADS_CACHE["signature"] = None
        cache_service.JONGGA_RESULT_PAYLOADS_CACHE["payloads"] = []

    second = cache_service.load_jongga_result_payloads(data_dir=str(tmp_path), limit=0)
    assert len(second) == 1
    assert second[0][1]["date"] == "2026-02-22"

    with connect_sqlite(str(tmp_path / "runtime_cache.db")) as conn:
        row_count = int(conn.execute("SELECT COUNT(*) FROM jongga_results_payload_cache").fetchone()[0])
    assert row_count >= 1


def test_load_jongga_result_payloads_skips_delete_when_rows_within_limit(monkeypatch, tmp_path):
    _reset_data_cache_state()
    monkeypatch.setattr(
        cache_jongga,
        "_JONGGA_PAYLOAD_SQLITE_DB_PATH",
        str(tmp_path / "runtime_cache.db"),
    )
    monkeypatch.setattr(cache_jongga, "_JONGGA_PAYLOAD_SQLITE_MAX_ROWS", 16)
    cache_jongga._JONGGA_PAYLOAD_SQLITE_READY.clear()

    traced_sql: list[str] = []
    original_connect = cache_jongga.connect_sqlite

    def _traced_connect(*args, **kwargs):
        conn = original_connect(*args, **kwargs)
        conn.set_trace_callback(traced_sql.append)
        return conn

    monkeypatch.setattr(cache_jongga, "connect_sqlite", _traced_connect)

    (tmp_path / "jongga_v2_results_20260222.json").write_text(
        json.dumps({"date": "2026-02-22", "signals": [{"stock_code": "005930"}]}, ensure_ascii=False),
        encoding="utf-8",
    )

    payloads = cache_service.load_jongga_result_payloads(data_dir=str(tmp_path), limit=0)
    assert len(payloads) == 1
    assert not any("DELETE FROM jongga_results_payload_cache" in sql for sql in traced_sql)


def test_load_jongga_result_payloads_stores_compact_sqlite_payload_json(monkeypatch, tmp_path):
    _reset_data_cache_state()
    monkeypatch.setattr(
        cache_jongga,
        "_JONGGA_PAYLOAD_SQLITE_DB_PATH",
        str(tmp_path / "runtime_cache.db"),
    )
    cache_jongga._JONGGA_PAYLOAD_SQLITE_READY.clear()

    (tmp_path / "jongga_v2_results_20260222.json").write_text(
        json.dumps({"date": "2026-02-22", "signals": [{"stock_code": "005930"}]}, ensure_ascii=False),
        encoding="utf-8",
    )

    payloads = cache_service.load_jongga_result_payloads(data_dir=str(tmp_path), limit=0)
    assert len(payloads) == 1

    with connect_sqlite(str(tmp_path / "runtime_cache.db")) as conn:
        row = conn.execute(
            "SELECT payload_json FROM jongga_results_payload_cache LIMIT 1"
        ).fetchone()

    assert row is not None
    payload_json = str(row[0])
    assert ": " not in payload_json
    assert ", " not in payload_json


def test_jongga_payload_sqlite_ready_uses_normalized_db_key(monkeypatch, tmp_path):
    _reset_data_cache_state()
    cache_jongga._JONGGA_PAYLOAD_SQLITE_READY.clear()
    monkeypatch.chdir(tmp_path)

    connect_calls = {"count": 0}
    original_connect = cache_jongga.connect_sqlite

    def _counted_connect(*args, **kwargs):
        connect_calls["count"] += 1
        return original_connect(*args, **kwargs)

    monkeypatch.setattr(cache_jongga, "connect_sqlite", _counted_connect)

    relative_db_path = "./runtime_cache.db"
    absolute_db_path = str((tmp_path / "runtime_cache.db").resolve())

    monkeypatch.setattr(cache_jongga, "_JONGGA_PAYLOAD_SQLITE_DB_PATH", relative_db_path)
    assert cache_jongga._ensure_jongga_payload_sqlite(logging.getLogger(__name__)) is True

    monkeypatch.setattr(cache_jongga, "_JONGGA_PAYLOAD_SQLITE_DB_PATH", absolute_db_path)
    assert cache_jongga._ensure_jongga_payload_sqlite(logging.getLogger(__name__)) is True

    assert connect_calls["count"] == 1
    assert os.path.exists(absolute_db_path)


def test_jongga_payload_sqlite_init_is_single_flight_under_concurrency(monkeypatch, tmp_path):
    _reset_data_cache_state()
    db_path = str(tmp_path / "runtime_cache.db")
    monkeypatch.setattr(cache_jongga, "_JONGGA_PAYLOAD_SQLITE_DB_PATH", db_path)

    with cache_jongga._JONGGA_PAYLOAD_SQLITE_CONDITION:
        cache_jongga._JONGGA_PAYLOAD_SQLITE_READY.clear()
        cache_jongga._JONGGA_PAYLOAD_SQLITE_INIT_IN_PROGRESS.clear()

    monkeypatch.setattr(cache_jongga, "sqlite_db_path_exists", lambda _path: True)

    entered_event = threading.Event()
    release_event = threading.Event()
    run_calls = {"count": 0}

    def _run_once(_operation, *, max_retries, retry_delay_seconds):
        run_calls["count"] += 1
        if run_calls["count"] == 1:
            entered_event.set()
            assert release_event.wait(timeout=2.0)
        return None

    monkeypatch.setattr(cache_jongga, "run_sqlite_with_retry", _run_once)

    results: dict[str, bool] = {}

    def _worker(name: str) -> None:
        results[name] = bool(cache_jongga._ensure_jongga_payload_sqlite(logging.getLogger(__name__)))

    first_thread = threading.Thread(target=_worker, args=("first",))
    second_thread = threading.Thread(target=_worker, args=("second",))

    first_thread.start()
    assert entered_event.wait(timeout=2.0)
    second_thread.start()
    time.sleep(0.05)
    assert run_calls["count"] == 1

    release_event.set()
    first_thread.join(timeout=2.0)
    second_thread.join(timeout=2.0)

    assert first_thread.is_alive() is False
    assert second_thread.is_alive() is False
    assert run_calls["count"] == 1
    assert results == {"first": True, "second": True}


def test_jongga_payload_sqlite_waiter_retries_after_initializer_failure(monkeypatch, tmp_path):
    _reset_data_cache_state()
    db_path = str(tmp_path / "runtime_cache.db")
    monkeypatch.setattr(cache_jongga, "_JONGGA_PAYLOAD_SQLITE_DB_PATH", db_path)

    with cache_jongga._JONGGA_PAYLOAD_SQLITE_CONDITION:
        cache_jongga._JONGGA_PAYLOAD_SQLITE_READY.clear()
        cache_jongga._JONGGA_PAYLOAD_SQLITE_INIT_IN_PROGRESS.clear()

    monkeypatch.setattr(cache_jongga, "sqlite_db_path_exists", lambda _path: True)

    entered_event = threading.Event()
    release_event = threading.Event()
    run_calls = {"count": 0}

    def _fail_then_succeed(_operation, *, max_retries, retry_delay_seconds):
        run_calls["count"] += 1
        if run_calls["count"] == 1:
            entered_event.set()
            assert release_event.wait(timeout=2.0)
            raise sqlite3.OperationalError("forced init failure")
        return None

    monkeypatch.setattr(cache_jongga, "run_sqlite_with_retry", _fail_then_succeed)

    results: dict[str, bool] = {}

    def _worker(name: str) -> None:
        results[name] = bool(cache_jongga._ensure_jongga_payload_sqlite(logging.getLogger(__name__)))

    first_thread = threading.Thread(target=_worker, args=("first",))
    second_thread = threading.Thread(target=_worker, args=("second",))

    first_thread.start()
    assert entered_event.wait(timeout=2.0)
    second_thread.start()
    time.sleep(0.05)
    assert run_calls["count"] == 1

    release_event.set()
    first_thread.join(timeout=2.0)
    second_thread.join(timeout=2.0)

    assert first_thread.is_alive() is False
    assert second_thread.is_alive() is False
    assert run_calls["count"] == 2
    assert results.get("first") is False
    assert results.get("second") is True


def test_load_latest_price_map_normalizes_ticker_and_picks_latest_on_unsorted_dates(tmp_path):
    _reset_data_cache_state()
    daily_prices = tmp_path / "daily_prices.csv"
    pd.DataFrame(
        [
            {"date": "2026-02-22", "ticker": "5930", "close": 120.0},
            {"date": "2026-02-20", "ticker": "5930", "close": 100.0},
            {"date": "2026-02-21", "ticker": "000660", "close": 200.0},
        ]
    ).to_csv(daily_prices, index=False)

    latest_map = cache_service.load_latest_vcp_price_map(
        data_dir=str(tmp_path),
        logger=logging.getLogger(__name__),
    )

    assert latest_map["005930"] == 120.0
    assert latest_map["000660"] == 200.0


def test_load_latest_price_map_skips_invalid_close_values(tmp_path):
    _reset_data_cache_state()
    daily_prices = tmp_path / "daily_prices.csv"
    pd.DataFrame(
        [
            {"date": "2026-02-20", "ticker": "5930", "close": "N/A"},
            {"date": "2026-02-21", "ticker": "5930", "close": 130.0},
            {"date": "2026-02-22", "ticker": "000660", "close": "bad"},
        ]
    ).to_csv(daily_prices, index=False)

    latest_map = cache_service.load_latest_vcp_price_map(
        data_dir=str(tmp_path),
        logger=logging.getLogger(__name__),
    )

    assert latest_map["005930"] == 130.0
    assert "000660" not in latest_map


def test_load_latest_price_map_reuses_core_csv_cache(monkeypatch, tmp_path):
    _reset_data_cache_state()
    daily_prices = tmp_path / "daily_prices.csv"
    pd.DataFrame(
        [
            {"date": "2026-02-20", "ticker": "5930", "close": 100.0},
            {"date": "2026-02-21", "ticker": "5930", "close": 110.0},
        ]
    ).to_csv(daily_prices, index=False)

    calls = {"count": 0}
    original_read_csv = cache_core.pd.read_csv

    def _counted_read_csv(*args, **kwargs):
        calls["count"] += 1
        return original_read_csv(*args, **kwargs)

    monkeypatch.setattr(cache_core.pd, "read_csv", _counted_read_csv)

    _ = cache_service.load_csv_file(
        str(tmp_path),
        "daily_prices.csv",
        deep_copy=False,
        usecols=["date", "ticker", "close"],
    )
    latest_map = cache_service.load_latest_vcp_price_map(
        data_dir=str(tmp_path),
        logger=logging.getLogger(__name__),
    )

    assert latest_map["005930"] == 110.0
    assert calls["count"] == 1


def test_load_latest_price_map_uses_sqlite_snapshot_after_memory_clear(monkeypatch, tmp_path):
    _reset_data_cache_state()
    daily_prices = tmp_path / "daily_prices.csv"
    pd.DataFrame(
        [
            {"date": "2026-02-20", "ticker": "5930", "close": 100.0},
            {"date": "2026-02-21", "ticker": "5930", "close": 111.0},
        ]
    ).to_csv(daily_prices, index=False)

    first = cache_service.load_latest_vcp_price_map(
        data_dir=str(tmp_path),
        logger=logging.getLogger(__name__),
    )
    assert first["005930"] == 111.0

    with cache_service.FILE_CACHE_LOCK:
        cache_service.LATEST_VCP_PRICE_MAP_CACHE["signature"] = None
        cache_service.LATEST_VCP_PRICE_MAP_CACHE["value"] = {}
        cache_service.BACKTEST_PRICE_SNAPSHOT_CACHE["signature"] = None
        cache_service.BACKTEST_PRICE_SNAPSHOT_CACHE["df"] = pd.DataFrame()
        cache_service.BACKTEST_PRICE_SNAPSHOT_CACHE["price_map"] = {}

    monkeypatch.setattr(
        cache_prices,
        "_load_daily_prices_subset",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("daily prices loader should not run")),
    )
    second = cache_service.load_latest_vcp_price_map(
        data_dir=str(tmp_path),
        logger=logging.getLogger(__name__),
    )

    assert second["005930"] == 111.0


def test_load_csv_file_uses_sqlite_snapshot_after_memory_clear(monkeypatch, tmp_path):
    _reset_data_cache_state()
    daily_prices = tmp_path / "daily_prices.csv"
    pd.DataFrame(
        [
            {"date": "2026-02-20", "ticker": "005930", "close": 100.0},
            {"date": "2026-02-21", "ticker": "005930", "close": 111.0},
        ]
    ).to_csv(daily_prices, index=False)

    first = cache_service.load_csv_file(
        str(tmp_path),
        "daily_prices.csv",
        deep_copy=False,
        usecols=["date", "ticker", "close"],
    )
    assert len(first) == 2

    with cache_service.FILE_CACHE_LOCK:
        cache_service.CSV_FILE_CACHE.clear()

    monkeypatch.setattr(
        cache_core.pd,
        "read_csv",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("read_csv should not run")),
    )
    second = cache_service.load_csv_file(
        str(tmp_path),
        "daily_prices.csv",
        deep_copy=False,
        usecols=["date", "ticker", "close"],
    )
    assert len(second) == 2
    assert float(second.iloc[-1]["close"]) == 111.0


def test_load_csv_file_retries_without_usecols_on_schema_mismatch(monkeypatch, tmp_path):
    _reset_data_cache_state()
    daily_prices = tmp_path / "daily_prices.csv"
    pd.DataFrame(
        [
            {"date": "2026-02-20", "ticker": "005930", "close": 100.0},
            {"date": "2026-02-21", "ticker": "005930", "close": 111.0},
        ]
    ).to_csv(daily_prices, index=False)

    calls = {"usecols": 0, "full": 0}
    original_read_csv = cache_core.pd.read_csv

    def _fake_read_csv(*args, **kwargs):
        if kwargs.get("usecols") is not None:
            calls["usecols"] += 1
            raise ValueError("Usecols do not match columns")
        calls["full"] += 1
        return original_read_csv(*args, **kwargs)

    monkeypatch.setattr(cache_core.pd, "read_csv", _fake_read_csv)

    first = cache_service.load_csv_file(
        str(tmp_path),
        "daily_prices.csv",
        deep_copy=False,
        usecols=["ticker", "missing_col"],
    )
    assert list(first.columns) == ["ticker"]
    assert len(first) == 2
    assert calls == {"usecols": 1, "full": 1}

    with cache_service.FILE_CACHE_LOCK:
        cache_service.CSV_FILE_CACHE.clear()

    monkeypatch.setattr(
        cache_core.pd,
        "read_csv",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("read_csv should not run")),
    )
    second = cache_service.load_csv_file(
        str(tmp_path),
        "daily_prices.csv",
        deep_copy=False,
        usecols=["ticker", "missing_col"],
    )

    assert list(second.columns) == ["ticker"]
    assert len(second) == 2


def test_load_csv_file_full_snapshot_uses_sqlite_after_memory_clear(monkeypatch, tmp_path):
    _reset_data_cache_state()
    daily_prices = tmp_path / "daily_prices.csv"
    pd.DataFrame(
        [
            {"date": "2026-02-20", "ticker": "005930", "close": 100.0, "volume": 1_000},
            {"date": "2026-02-21", "ticker": "005930", "close": 111.0, "volume": 2_000},
        ]
    ).to_csv(daily_prices, index=False)

    first = cache_service.load_csv_file(
        str(tmp_path),
        "daily_prices.csv",
        deep_copy=False,
        usecols=None,
    )
    assert len(first) == 2

    with cache_service.FILE_CACHE_LOCK:
        cache_service.CSV_FILE_CACHE.clear()

    monkeypatch.setattr(
        cache_core.pd,
        "read_csv",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("read_csv should not run")),
    )
    second = cache_service.load_csv_file(
        str(tmp_path),
        "daily_prices.csv",
        deep_copy=False,
        usecols=None,
    )
    assert len(second) == 2
    assert float(second.iloc[-1]["close"]) == 111.0

    with connect_sqlite(str(tmp_path / "runtime_cache.db")) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT COUNT(*)
            FROM csv_file_payload_cache
            WHERE usecols_signature = ?
            """,
            ("[]",),
        )
        row_count = int(cursor.fetchone()[0])

    assert row_count >= 1


def test_load_csv_file_full_snapshot_skips_sqlite_when_file_is_large(monkeypatch, tmp_path):
    _reset_data_cache_state()
    monkeypatch.setattr(cache_core, "_FULL_CSV_SQLITE_MAX_BYTES", 1)

    daily_prices = tmp_path / "daily_prices.csv"
    pd.DataFrame(
        [
            {"date": "2026-02-20", "ticker": "005930", "close": 100.0},
            {"date": "2026-02-21", "ticker": "005930", "close": 111.0},
            {"date": "2026-02-22", "ticker": "000660", "close": 200.0},
        ]
    ).to_csv(daily_prices, index=False)

    calls = {"count": 0}
    original_read_csv = cache_core.pd.read_csv

    def _counted_read_csv(*args, **kwargs):
        calls["count"] += 1
        return original_read_csv(*args, **kwargs)

    monkeypatch.setattr(cache_core.pd, "read_csv", _counted_read_csv)

    first = cache_service.load_csv_file(
        str(tmp_path),
        "daily_prices.csv",
        deep_copy=False,
        usecols=None,
    )
    assert len(first) == 3

    with cache_service.FILE_CACHE_LOCK:
        cache_service.CSV_FILE_CACHE.clear()

    second = cache_service.load_csv_file(
        str(tmp_path),
        "daily_prices.csv",
        deep_copy=False,
        usecols=None,
    )
    assert len(second) == 3
    assert calls["count"] == 2


def test_load_csv_file_prunes_sqlite_snapshot_rows(monkeypatch, tmp_path):
    _reset_data_cache_state()
    monkeypatch.setattr(cache_core, "_CSV_PAYLOAD_SQLITE_MAX_ROWS", 2)

    for index in range(1, 5):
        filename = f"sample_{index}.csv"
        (tmp_path / filename).write_text(
            "date,ticker,close\n2026-02-20,005930,100\n",
            encoding="utf-8",
        )
        _ = cache_service.load_csv_file(
            str(tmp_path),
            filename,
            deep_copy=False,
            usecols=["date", "ticker", "close"],
        )

    with connect_sqlite(str(tmp_path / "runtime_cache.db")) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM csv_file_payload_cache")
        row_count = int(cursor.fetchone()[0])

    assert row_count == 2


def test_load_latest_price_map_passes_signature_to_core_loader(monkeypatch, tmp_path):
    _reset_data_cache_state()
    daily_prices = tmp_path / "daily_prices.csv"
    pd.DataFrame(
        [
            {"date": "2026-02-20", "ticker": "5930", "close": 100.0},
            {"date": "2026-02-21", "ticker": "5930", "close": 111.0},
        ]
    ).to_csv(daily_prices, index=False)

    calls = {"count": 0}
    original_file_signature = cache_core.file_signature

    def _counted_file_signature(path: str):
        calls["count"] += 1
        return original_file_signature(path)

    monkeypatch.setattr(cache_prices, "file_signature", _counted_file_signature)
    monkeypatch.setattr(cache_core, "file_signature", _counted_file_signature)

    latest_map = cache_service.load_latest_vcp_price_map(
        data_dir=str(tmp_path),
        logger=logging.getLogger(__name__),
    )

    assert latest_map["005930"] == 111.0
    assert calls["count"] == 1


def test_load_json_file_uses_sqlite_snapshot_after_memory_clear(monkeypatch, tmp_path):
    _reset_data_cache_state()
    target_file = tmp_path / "kr_ai_analysis.json"
    target_file.write_text(
        json.dumps({"signals": [{"ticker": "005930"}]}, ensure_ascii=False),
        encoding="utf-8",
    )

    first = cache_service.load_json_file(str(tmp_path), "kr_ai_analysis.json")
    assert first["signals"][0]["ticker"] == "005930"

    with cache_service.FILE_CACHE_LOCK:
        cache_service.JSON_FILE_CACHE.clear()

    monkeypatch.setattr(
        "builtins.open",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("open should not be called")),
    )
    second = cache_service.load_json_file(str(tmp_path), "kr_ai_analysis.json")
    assert second["signals"][0]["ticker"] == "005930"


def test_load_json_file_supports_deep_copy_false_for_read_only_path(tmp_path):
    _reset_data_cache_state()
    target_file = tmp_path / "kr_ai_analysis.json"
    target_file.write_text(
        json.dumps({"signals": [{"ticker": "005930"}]}, ensure_ascii=False),
        encoding="utf-8",
    )

    first = cache_service.load_json_file(
        str(tmp_path),
        "kr_ai_analysis.json",
        deep_copy=False,
    )
    second = cache_service.load_json_file(
        str(tmp_path),
        "kr_ai_analysis.json",
        deep_copy=False,
    )
    third = cache_service.load_json_file(str(tmp_path), "kr_ai_analysis.json")

    assert first is second
    assert third is not first
    assert third["signals"][0]["ticker"] == "005930"


def test_load_json_file_prunes_sqlite_rows(monkeypatch, tmp_path):
    _reset_data_cache_state()
    monkeypatch.setattr(cache_core, "_JSON_PAYLOAD_SQLITE_MAX_ROWS", 2)

    for index in range(1, 5):
        filename = f"ai_analysis_results_2026020{index}.json"
        (tmp_path / filename).write_text(
            json.dumps({"signals": [{"ticker": f"{index:06d}"}]}, ensure_ascii=False),
            encoding="utf-8",
        )
        _ = cache_service.load_json_file(str(tmp_path), filename)

    with connect_sqlite(str(tmp_path / "runtime_cache.db")) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM json_file_payload_cache")
        row_count = int(cursor.fetchone()[0])

    assert row_count == 2


def test_load_json_file_memory_cache_is_bounded_lru(monkeypatch, tmp_path):
    _reset_data_cache_state()
    monkeypatch.setattr(cache_core, "_JSON_FILE_CACHE_MAX_ENTRIES", 2)

    (tmp_path / "cache_a.json").write_text(
        json.dumps({"id": "A"}, ensure_ascii=False),
        encoding="utf-8",
    )
    (tmp_path / "cache_b.json").write_text(
        json.dumps({"id": "B"}, ensure_ascii=False),
        encoding="utf-8",
    )
    (tmp_path / "cache_c.json").write_text(
        json.dumps({"id": "C"}, ensure_ascii=False),
        encoding="utf-8",
    )

    _ = cache_service.load_json_file(str(tmp_path), "cache_a.json")
    _ = cache_service.load_json_file(str(tmp_path), "cache_b.json")
    _ = cache_service.load_json_file(str(tmp_path), "cache_a.json")
    _ = cache_service.load_json_file(str(tmp_path), "cache_c.json")

    with cache_service.FILE_CACHE_LOCK:
        cached_keys = list(cache_service.JSON_FILE_CACHE.keys())

    key_a = os.path.abspath(str(tmp_path / "cache_a.json"))
    key_b = os.path.abspath(str(tmp_path / "cache_b.json"))
    key_c = os.path.abspath(str(tmp_path / "cache_c.json"))

    assert len(cached_keys) == 2
    assert key_a in cached_keys
    assert key_c in cached_keys
    assert key_b not in cached_keys


def test_load_csv_file_memory_cache_is_bounded_lru(monkeypatch, tmp_path):
    _reset_data_cache_state()
    monkeypatch.setattr(cache_core, "_CSV_FILE_CACHE_MAX_ENTRIES", 2)

    for index in range(1, 4):
        (tmp_path / f"cache_{index}.csv").write_text(
            "date,ticker,close\n2026-02-20,005930,100\n",
            encoding="utf-8",
        )

    usecols = ["date", "ticker", "close"]
    usecols_signature = tuple(usecols)

    _ = cache_service.load_csv_file(str(tmp_path), "cache_1.csv", deep_copy=False, usecols=usecols)
    _ = cache_service.load_csv_file(str(tmp_path), "cache_2.csv", deep_copy=False, usecols=usecols)
    _ = cache_service.load_csv_file(str(tmp_path), "cache_1.csv", deep_copy=False, usecols=usecols)
    _ = cache_service.load_csv_file(str(tmp_path), "cache_3.csv", deep_copy=False, usecols=usecols)

    with cache_service.FILE_CACHE_LOCK:
        cached_keys = list(cache_service.CSV_FILE_CACHE.keys())

    key_1 = (os.path.abspath(str(tmp_path / "cache_1.csv")), usecols_signature)
    key_2 = (os.path.abspath(str(tmp_path / "cache_2.csv")), usecols_signature)
    key_3 = (os.path.abspath(str(tmp_path / "cache_3.csv")), usecols_signature)

    assert len(cached_keys) == 2
    assert key_1 in cached_keys
    assert key_3 in cached_keys
    assert key_2 not in cached_keys
