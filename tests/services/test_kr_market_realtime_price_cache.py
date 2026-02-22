#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KR Market realtime price cache(SQLite) 테스트
"""

from __future__ import annotations

import os
import sqlite3
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path

import services.kr_market_realtime_price_cache as realtime_price_cache
from services.kr_market_realtime_price_cache import (
    load_cached_realtime_prices,
    load_recent_yfinance_failed_tickers,
    save_realtime_prices_to_cache,
    save_yfinance_failed_tickers,
)


def test_realtime_price_cache_roundtrip(tmp_path: Path):
    get_data_path = lambda filename: str(tmp_path / filename)

    save_realtime_prices_to_cache(
        {"5930": 123.4, "000660": 0.0},
        source="test",
        get_data_path=get_data_path,
    )

    loaded = load_cached_realtime_prices(
        ["005930", "000660"],
        get_data_path=get_data_path,
        max_age_seconds=3600,
    )
    assert loaded == {"005930": 123.4}

    with sqlite3.connect(tmp_path / "runtime_cache.db") as conn:
        row_count = conn.execute("SELECT COUNT(*) FROM realtime_price_cache").fetchone()[0]
    assert int(row_count) == 1


def test_realtime_price_cache_respects_ttl(tmp_path: Path):
    get_data_path = lambda filename: str(tmp_path / filename)

    save_realtime_prices_to_cache(
        {"005930": 101.0},
        source="test",
        get_data_path=get_data_path,
    )

    db_path = tmp_path / "runtime_cache.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "UPDATE realtime_price_cache SET updated_at = ? WHERE ticker = ?",
            ((datetime.now() - timedelta(hours=1)).isoformat(), "005930"),
        )
        conn.commit()

    loaded = load_cached_realtime_prices(
        ["005930"],
        get_data_path=get_data_path,
        max_age_seconds=60,
    )
    assert loaded == {}


def test_realtime_price_cache_supports_db_path_without_parent_dir(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    get_data_path = lambda filename: filename

    save_realtime_prices_to_cache(
        {"005930": 50500.0},
        source="test",
        get_data_path=get_data_path,
    )

    loaded = load_cached_realtime_prices(
        ["005930"],
        get_data_path=get_data_path,
        max_age_seconds=3600,
    )
    assert loaded == {"005930": 50500.0}


def test_yfinance_failed_ticker_cache_roundtrip_and_ttl(tmp_path: Path):
    get_data_path = lambda filename: str(tmp_path / filename)
    with realtime_price_cache._YFINANCE_FAILED_MEMORY_CACHE_LOCK:
        realtime_price_cache._YFINANCE_FAILED_MEMORY_CACHE.clear()

    save_yfinance_failed_tickers(
        ["5930", "005930", "000660"],
        get_data_path=get_data_path,
    )

    loaded = load_recent_yfinance_failed_tickers(
        ["005930", "000660", "035420"],
        get_data_path=get_data_path,
        max_age_seconds=3600,
    )
    assert loaded == {"005930", "000660"}

    db_path = tmp_path / "runtime_cache.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "UPDATE yfinance_failed_ticker_cache SET updated_at = ? WHERE ticker = ?",
            ((datetime.now() - timedelta(hours=2)).isoformat(), "005930"),
        )
        conn.commit()
    with realtime_price_cache._YFINANCE_FAILED_MEMORY_CACHE_LOCK:
        realtime_price_cache._YFINANCE_FAILED_MEMORY_CACHE.clear()

    loaded_after_ttl = load_recent_yfinance_failed_tickers(
        ["005930", "000660"],
        get_data_path=get_data_path,
        max_age_seconds=300,
    )
    assert loaded_after_ttl == {"000660"}


def test_load_cached_realtime_prices_chunks_large_ticker_query(monkeypatch, tmp_path: Path):
    get_data_path = lambda filename: str(tmp_path / filename)
    monkeypatch.setattr(realtime_price_cache, "_SQLITE_TICKER_QUERY_CHUNK_SIZE", 2)

    prices = {
        "005930": 100.0,
        "000660": 200.0,
        "035420": 300.0,
        "051910": 400.0,
    }
    save_realtime_prices_to_cache(prices, source="chunk-test", get_data_path=get_data_path)

    loaded = load_cached_realtime_prices(
        ["005930", "000660", "035420", "051910", "068270"],
        get_data_path=get_data_path,
        max_age_seconds=3600,
    )
    assert loaded == prices


def test_load_cached_realtime_prices_uses_read_only_connection(monkeypatch, tmp_path: Path):
    get_data_path = lambda filename: str(tmp_path / filename)
    save_realtime_prices_to_cache(
        {"005930": 100.0},
        source="read-only-test",
        get_data_path=get_data_path,
    )

    read_only_flags: list[bool] = []
    original_connect = realtime_price_cache.connect_sqlite

    def _traced_connect(*args, **kwargs):
        if "read_only" in kwargs:
            read_only_flags.append(bool(kwargs["read_only"]))
        return original_connect(*args, **kwargs)

    monkeypatch.setattr(realtime_price_cache, "connect_sqlite", _traced_connect)

    loaded = load_cached_realtime_prices(
        ["005930"],
        get_data_path=get_data_path,
        max_age_seconds=3600,
    )
    assert loaded == {"005930": 100.0}
    assert True in read_only_flags


def test_load_recent_yfinance_failed_tickers_chunks_large_query(monkeypatch, tmp_path: Path):
    get_data_path = lambda filename: str(tmp_path / filename)
    monkeypatch.setattr(realtime_price_cache, "_SQLITE_TICKER_QUERY_CHUNK_SIZE", 2)

    save_yfinance_failed_tickers(
        ["005930", "000660", "035420", "051910"],
        get_data_path=get_data_path,
    )

    loaded = load_recent_yfinance_failed_tickers(
        ["005930", "000660", "035420", "051910", "068270"],
        get_data_path=get_data_path,
        max_age_seconds=3600,
    )
    assert loaded == {"005930", "000660", "035420", "051910"}


def test_load_recent_yfinance_failed_tickers_uses_read_only_connection(monkeypatch, tmp_path: Path):
    get_data_path = lambda filename: str(tmp_path / filename)
    with realtime_price_cache._YFINANCE_FAILED_MEMORY_CACHE_LOCK:
        realtime_price_cache._YFINANCE_FAILED_MEMORY_CACHE.clear()

    save_yfinance_failed_tickers(
        ["005930"],
        get_data_path=get_data_path,
    )
    with realtime_price_cache._YFINANCE_FAILED_MEMORY_CACHE_LOCK:
        realtime_price_cache._YFINANCE_FAILED_MEMORY_CACHE.clear()

    read_only_flags: list[bool] = []
    original_connect = realtime_price_cache.connect_sqlite

    def _traced_connect(*args, **kwargs):
        if "read_only" in kwargs:
            read_only_flags.append(bool(kwargs["read_only"]))
        return original_connect(*args, **kwargs)

    monkeypatch.setattr(realtime_price_cache, "connect_sqlite", _traced_connect)

    loaded = load_recent_yfinance_failed_tickers(
        ["005930"],
        get_data_path=get_data_path,
        max_age_seconds=3600,
    )
    assert loaded == {"005930"}
    assert True in read_only_flags


def test_load_recent_yfinance_failed_tickers_pushes_ttl_filter_into_sql(monkeypatch, tmp_path: Path):
    get_data_path = lambda filename: str(tmp_path / filename)
    db_path = tmp_path / "runtime_cache.db"
    with realtime_price_cache._YFINANCE_FAILED_MEMORY_CACHE_LOCK:
        realtime_price_cache._YFINANCE_FAILED_MEMORY_CACHE.clear()

    save_yfinance_failed_tickers(
        ["005930"],
        get_data_path=get_data_path,
    )
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "UPDATE yfinance_failed_ticker_cache SET updated_at = ? WHERE ticker = ?",
            ((datetime.now() - timedelta(hours=2)).isoformat(), "005930"),
        )
        conn.commit()
    with realtime_price_cache._YFINANCE_FAILED_MEMORY_CACHE_LOCK:
        realtime_price_cache._YFINANCE_FAILED_MEMORY_CACHE.clear()

    traced_sql: list[str] = []
    original_connect = realtime_price_cache.connect_sqlite

    def _traced_connect(*args, **kwargs):
        conn = original_connect(*args, **kwargs)
        conn.set_trace_callback(traced_sql.append)
        return conn

    monkeypatch.setattr(realtime_price_cache, "connect_sqlite", _traced_connect)

    loaded = load_recent_yfinance_failed_tickers(
        ["005930"],
        get_data_path=get_data_path,
        max_age_seconds=300,
    )
    assert loaded == set()
    select_sql = [sql for sql in traced_sql if "FROM yfinance_failed_ticker_cache" in sql]
    assert select_sql
    assert any("updated_at >=" in sql.lower() for sql in select_sql)


def test_load_recent_yfinance_failed_tickers_reuses_memory_cache(monkeypatch, tmp_path: Path):
    get_data_path = lambda filename: str(tmp_path / filename)
    with realtime_price_cache._YFINANCE_FAILED_MEMORY_CACHE_LOCK:
        realtime_price_cache._YFINANCE_FAILED_MEMORY_CACHE.clear()

    save_yfinance_failed_tickers(
        ["005930"],
        get_data_path=get_data_path,
    )
    loaded_first = load_recent_yfinance_failed_tickers(
        ["005930"],
        get_data_path=get_data_path,
        max_age_seconds=3600,
    )
    assert loaded_first == {"005930"}

    monkeypatch.setattr(
        realtime_price_cache,
        "connect_sqlite",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("connect_sqlite should not be called when memory cache is warm")
        ),
    )

    loaded_second = load_recent_yfinance_failed_tickers(
        ["005930"],
        get_data_path=get_data_path,
        max_age_seconds=3600,
    )
    assert loaded_second == {"005930"}


def test_load_recent_yfinance_failed_tickers_invalidates_memory_on_signature_change(monkeypatch, tmp_path: Path):
    get_data_path = lambda filename: str(tmp_path / filename)
    with realtime_price_cache._YFINANCE_FAILED_MEMORY_CACHE_LOCK:
        realtime_price_cache._YFINANCE_FAILED_MEMORY_CACHE.clear()

    save_yfinance_failed_tickers(
        ["005930"],
        get_data_path=get_data_path,
    )
    load_recent_yfinance_failed_tickers(
        ["005930"],
        get_data_path=get_data_path,
        max_age_seconds=3600,
    )

    original_connect = realtime_price_cache.connect_sqlite
    connect_calls = {"count": 0}

    def _counted_connect(*args, **kwargs):
        connect_calls["count"] += 1
        return original_connect(*args, **kwargs)

    monkeypatch.setattr(realtime_price_cache, "connect_sqlite", _counted_connect)
    monkeypatch.setattr(
        realtime_price_cache,
        "_sqlite_storage_signature",
        lambda _db_path: ((999, 999, 999), None, None),
    )

    loaded = load_recent_yfinance_failed_tickers(
        ["005930"],
        get_data_path=get_data_path,
        max_age_seconds=3600,
    )
    assert loaded == {"005930"}
    assert connect_calls["count"] >= 1


def test_yfinance_failed_memory_cache_bounds_db_entries_lru(monkeypatch, tmp_path: Path):
    with realtime_price_cache._YFINANCE_FAILED_MEMORY_CACHE_LOCK:
        realtime_price_cache._YFINANCE_FAILED_MEMORY_CACHE.clear()
    monkeypatch.setattr(realtime_price_cache, "_YFINANCE_FAILED_MEMORY_CACHE_MAX_DBS", 2)

    first_dir = tmp_path / "db_first"
    second_dir = tmp_path / "db_second"
    third_dir = tmp_path / "db_third"
    first_get_data_path = lambda filename: str(first_dir / filename)
    second_get_data_path = lambda filename: str(second_dir / filename)
    third_get_data_path = lambda filename: str(third_dir / filename)

    save_yfinance_failed_tickers(["005930"], get_data_path=first_get_data_path)
    save_yfinance_failed_tickers(["000660"], get_data_path=second_get_data_path)

    loaded_first = load_recent_yfinance_failed_tickers(
        ["005930"],
        get_data_path=first_get_data_path,
        max_age_seconds=3600,
    )
    assert loaded_first == {"005930"}

    save_yfinance_failed_tickers(["035420"], get_data_path=third_get_data_path)

    first_db_path = str(first_dir / "runtime_cache.db")
    second_db_path = str(second_dir / "runtime_cache.db")
    third_db_path = str(third_dir / "runtime_cache.db")
    with realtime_price_cache._YFINANCE_FAILED_MEMORY_CACHE_LOCK:
        cache_keys = list(realtime_price_cache._YFINANCE_FAILED_MEMORY_CACHE.keys())

    assert len(cache_keys) == 2
    assert first_db_path in cache_keys
    assert second_db_path not in cache_keys
    assert third_db_path in cache_keys


def test_yfinance_failed_memory_cache_bounds_ticker_entries_lru(monkeypatch, tmp_path: Path):
    with realtime_price_cache._YFINANCE_FAILED_MEMORY_CACHE_LOCK:
        realtime_price_cache._YFINANCE_FAILED_MEMORY_CACHE.clear()
    monkeypatch.setattr(realtime_price_cache, "_YFINANCE_FAILED_MEMORY_PER_DB_MAX_ENTRIES", 2)
    monkeypatch.setattr(
        realtime_price_cache,
        "_sqlite_storage_signature",
        lambda _db_path: ((1, 1, 1), None, None),
    )

    get_data_path = lambda filename: str(tmp_path / filename)
    db_path = str(tmp_path / "runtime_cache.db")

    save_yfinance_failed_tickers(["005930"], get_data_path=get_data_path)
    with realtime_price_cache._YFINANCE_FAILED_MEMORY_CACHE_LOCK:
        realtime_price_cache._YFINANCE_FAILED_MEMORY_CACHE.clear()

    loaded_first = load_recent_yfinance_failed_tickers(
        ["005930"],
        get_data_path=get_data_path,
        max_age_seconds=3600,
    )
    assert loaded_first == {"005930"}
    loaded_second = load_recent_yfinance_failed_tickers(
        ["000660"],
        get_data_path=get_data_path,
        max_age_seconds=3600,
    )
    assert loaded_second == set()
    loaded_first_again = load_recent_yfinance_failed_tickers(
        ["005930"],
        get_data_path=get_data_path,
        max_age_seconds=3600,
    )
    assert loaded_first_again == {"005930"}
    loaded_third = load_recent_yfinance_failed_tickers(
        ["035420"],
        get_data_path=get_data_path,
        max_age_seconds=3600,
    )
    assert loaded_third == set()

    with realtime_price_cache._YFINANCE_FAILED_MEMORY_CACHE_LOCK:
        entry = realtime_price_cache._YFINANCE_FAILED_MEMORY_CACHE.get(db_path)
        assert entry is not None
        cache_keys = list(entry[1].keys())

    assert len(cache_keys) == 2
    assert "005930" in cache_keys
    assert "000660" not in cache_keys
    assert "035420" in cache_keys


def test_realtime_price_cache_recovers_when_price_table_missing(tmp_path: Path):
    get_data_path = lambda filename: str(tmp_path / filename)

    save_realtime_prices_to_cache(
        {"005930": 100.0},
        source="test",
        get_data_path=get_data_path,
    )
    db_path = tmp_path / "runtime_cache.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute("DROP TABLE realtime_price_cache")
        conn.commit()

    save_realtime_prices_to_cache(
        {"000660": 200.0},
        source="test",
        get_data_path=get_data_path,
    )

    loaded = load_cached_realtime_prices(
        ["000660"],
        get_data_path=get_data_path,
        max_age_seconds=3600,
    )
    assert loaded == {"000660": 200.0}


def test_realtime_price_cache_recovers_when_yfinance_table_missing(tmp_path: Path):
    get_data_path = lambda filename: str(tmp_path / filename)
    with realtime_price_cache._YFINANCE_FAILED_MEMORY_CACHE_LOCK:
        realtime_price_cache._YFINANCE_FAILED_MEMORY_CACHE.clear()

    save_yfinance_failed_tickers(
        ["005930"],
        get_data_path=get_data_path,
    )
    db_path = tmp_path / "runtime_cache.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute("DROP TABLE yfinance_failed_ticker_cache")
        conn.commit()

    save_yfinance_failed_tickers(
        ["000660"],
        get_data_path=get_data_path,
    )

    loaded = load_recent_yfinance_failed_tickers(
        ["000660"],
        get_data_path=get_data_path,
        max_age_seconds=3600,
    )
    assert loaded == {"000660"}


def test_realtime_price_cache_prune_runs_only_after_interval(tmp_path: Path):
    get_data_path = lambda filename: str(tmp_path / filename)
    db_path = tmp_path / "runtime_cache.db"

    save_realtime_prices_to_cache(
        {"005930": 100.0},
        source="test",
        get_data_path=get_data_path,
    )

    stale_iso = (datetime.now() - timedelta(days=10)).isoformat()
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO realtime_price_cache (ticker, price, source, updated_at)
            VALUES (?, ?, ?, ?)
            """,
            ("999999", 1.0, "stale", stale_iso),
        )
        conn.commit()

    with realtime_price_cache._SQLITE_PRUNE_STATE_LOCK:
        realtime_price_cache._REALTIME_PRICE_LAST_PRUNED_AT[str(db_path)] = datetime.now().timestamp()

    save_realtime_prices_to_cache(
        {"000660": 200.0},
        source="test",
        get_data_path=get_data_path,
    )
    with sqlite3.connect(db_path) as conn:
        stale_count_after_throttled_save = conn.execute(
            "SELECT COUNT(*) FROM realtime_price_cache WHERE ticker = ?",
            ("999999",),
        ).fetchone()[0]
    assert int(stale_count_after_throttled_save) == 1

    with realtime_price_cache._SQLITE_PRUNE_STATE_LOCK:
        realtime_price_cache._REALTIME_PRICE_LAST_PRUNED_AT[str(db_path)] = (
            datetime.now().timestamp() - realtime_price_cache._SQLITE_PRUNE_MIN_INTERVAL_SECONDS - 1
        )

    save_realtime_prices_to_cache(
        {"035420": 300.0},
        source="test",
        get_data_path=get_data_path,
    )
    with sqlite3.connect(db_path) as conn:
        stale_count_after_due_save = conn.execute(
            "SELECT COUNT(*) FROM realtime_price_cache WHERE ticker = ?",
            ("999999",),
        ).fetchone()[0]
    assert int(stale_count_after_due_save) == 0


def test_yfinance_failed_cache_prune_runs_only_after_interval(tmp_path: Path):
    get_data_path = lambda filename: str(tmp_path / filename)
    db_path = tmp_path / "runtime_cache.db"

    save_yfinance_failed_tickers(
        ["005930"],
        get_data_path=get_data_path,
    )

    stale_iso = (datetime.now() - timedelta(days=30)).isoformat()
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO yfinance_failed_ticker_cache (ticker, updated_at)
            VALUES (?, ?)
            """,
            ("999999", stale_iso),
        )
        conn.commit()

    with realtime_price_cache._SQLITE_PRUNE_STATE_LOCK:
        realtime_price_cache._YFINANCE_FAILED_LAST_PRUNED_AT[str(db_path)] = datetime.now().timestamp()

    save_yfinance_failed_tickers(
        ["000660"],
        get_data_path=get_data_path,
    )
    with sqlite3.connect(db_path) as conn:
        stale_count_after_throttled_save = conn.execute(
            "SELECT COUNT(*) FROM yfinance_failed_ticker_cache WHERE ticker = ?",
            ("999999",),
        ).fetchone()[0]
    assert int(stale_count_after_throttled_save) == 1

    with realtime_price_cache._SQLITE_PRUNE_STATE_LOCK:
        realtime_price_cache._YFINANCE_FAILED_LAST_PRUNED_AT[str(db_path)] = (
            datetime.now().timestamp() - realtime_price_cache._SQLITE_PRUNE_MIN_INTERVAL_SECONDS - 1
        )

    save_yfinance_failed_tickers(
        ["035420"],
        get_data_path=get_data_path,
    )
    with sqlite3.connect(db_path) as conn:
        stale_count_after_due_save = conn.execute(
            "SELECT COUNT(*) FROM yfinance_failed_ticker_cache WHERE ticker = ?",
            ("999999",),
        ).fetchone()[0]
    assert int(stale_count_after_due_save) == 0


def test_sqlite_prune_state_maps_are_bounded_lru(monkeypatch):
    with realtime_price_cache._SQLITE_PRUNE_STATE_LOCK:
        realtime_price_cache._REALTIME_PRICE_LAST_PRUNED_AT.clear()
        realtime_price_cache._YFINANCE_FAILED_LAST_PRUNED_AT.clear()
    monkeypatch.setattr(realtime_price_cache, "_SQLITE_PRUNE_STATE_MAX_ENTRIES", 2)

    now_ts = datetime.now().timestamp()
    realtime_price_cache._mark_sqlite_cache_pruned(
        realtime_price_cache._REALTIME_PRICE_LAST_PRUNED_AT,
        "db-a",
        now_ts,
    )
    realtime_price_cache._mark_sqlite_cache_pruned(
        realtime_price_cache._REALTIME_PRICE_LAST_PRUNED_AT,
        "db-b",
        now_ts,
    )
    realtime_price_cache._mark_sqlite_cache_pruned(
        realtime_price_cache._REALTIME_PRICE_LAST_PRUNED_AT,
        "db-c",
        now_ts,
    )

    realtime_price_cache._mark_sqlite_cache_pruned(
        realtime_price_cache._YFINANCE_FAILED_LAST_PRUNED_AT,
        "db-a",
        now_ts,
    )
    realtime_price_cache._mark_sqlite_cache_pruned(
        realtime_price_cache._YFINANCE_FAILED_LAST_PRUNED_AT,
        "db-b",
        now_ts,
    )
    realtime_price_cache._mark_sqlite_cache_pruned(
        realtime_price_cache._YFINANCE_FAILED_LAST_PRUNED_AT,
        "db-c",
        now_ts,
    )

    with realtime_price_cache._SQLITE_PRUNE_STATE_LOCK:
        realtime_price_keys = list(realtime_price_cache._REALTIME_PRICE_LAST_PRUNED_AT.keys())
        yfinance_keys = list(realtime_price_cache._YFINANCE_FAILED_LAST_PRUNED_AT.keys())

    assert len(realtime_price_keys) == 2
    assert "db-a" not in realtime_price_keys
    assert "db-b" in realtime_price_keys
    assert "db-c" in realtime_price_keys

    assert len(yfinance_keys) == 2
    assert "db-a" not in yfinance_keys
    assert "db-b" in yfinance_keys
    assert "db-c" in yfinance_keys


def test_realtime_price_prune_state_dedupes_relative_and_absolute_db_paths(monkeypatch, tmp_path: Path):
    with realtime_price_cache._SQLITE_PRUNE_STATE_LOCK:
        realtime_price_cache._REALTIME_PRICE_LAST_PRUNED_AT.clear()

    monkeypatch.chdir(tmp_path)
    absolute_get_data_path = lambda filename: str((tmp_path / filename).resolve())
    relative_get_data_path = lambda filename: filename

    save_realtime_prices_to_cache(
        {"005930": 100.0},
        source="test",
        get_data_path=absolute_get_data_path,
    )
    save_realtime_prices_to_cache(
        {"000660": 200.0},
        source="test",
        get_data_path=relative_get_data_path,
    )

    normalized_key = realtime_price_cache.normalize_sqlite_db_key(str((tmp_path / "runtime_cache.db").resolve()))
    with realtime_price_cache._SQLITE_PRUNE_STATE_LOCK:
        keys = list(realtime_price_cache._REALTIME_PRICE_LAST_PRUNED_AT.keys())

    assert len(keys) == 1
    assert normalized_key in keys


def test_yfinance_prune_state_dedupes_relative_and_absolute_db_paths(monkeypatch, tmp_path: Path):
    with realtime_price_cache._SQLITE_PRUNE_STATE_LOCK:
        realtime_price_cache._YFINANCE_FAILED_LAST_PRUNED_AT.clear()
    with realtime_price_cache._YFINANCE_FAILED_MEMORY_CACHE_LOCK:
        realtime_price_cache._YFINANCE_FAILED_MEMORY_CACHE.clear()

    monkeypatch.chdir(tmp_path)
    absolute_get_data_path = lambda filename: str((tmp_path / filename).resolve())
    relative_get_data_path = lambda filename: filename

    save_yfinance_failed_tickers(
        ["005930"],
        get_data_path=absolute_get_data_path,
    )
    save_yfinance_failed_tickers(
        ["000660"],
        get_data_path=relative_get_data_path,
    )

    normalized_key = realtime_price_cache.normalize_sqlite_db_key(str((tmp_path / "runtime_cache.db").resolve()))
    with realtime_price_cache._SQLITE_PRUNE_STATE_LOCK:
        keys = list(realtime_price_cache._YFINANCE_FAILED_LAST_PRUNED_AT.keys())

    assert len(keys) == 1
    assert normalized_key in keys


def test_yfinance_failed_memory_cache_reuses_alias_path_without_sqlite_query(monkeypatch, tmp_path: Path):
    with realtime_price_cache._YFINANCE_FAILED_MEMORY_CACHE_LOCK:
        realtime_price_cache._YFINANCE_FAILED_MEMORY_CACHE.clear()

    monkeypatch.chdir(tmp_path)
    absolute_get_data_path = lambda filename: str((tmp_path / filename).resolve())
    relative_get_data_path = lambda filename: filename

    save_yfinance_failed_tickers(
        ["005930"],
        get_data_path=absolute_get_data_path,
    )

    monkeypatch.setattr(
        realtime_price_cache,
        "connect_sqlite",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("connect_sqlite should not be called when alias memory cache is warm")
        ),
    )

    loaded = load_recent_yfinance_failed_tickers(
        ["005930"],
        get_data_path=relative_get_data_path,
        max_age_seconds=3600,
    )
    assert loaded == {"005930"}


def test_invalidate_realtime_price_sqlite_ready_clears_yfinance_failed_memory_cache(monkeypatch, tmp_path: Path):
    with realtime_price_cache._YFINANCE_FAILED_MEMORY_CACHE_LOCK:
        realtime_price_cache._YFINANCE_FAILED_MEMORY_CACHE.clear()
    with realtime_price_cache._SQLITE_PRUNE_STATE_LOCK:
        realtime_price_cache._REALTIME_PRICE_LAST_PRUNED_AT.clear()
        realtime_price_cache._YFINANCE_FAILED_LAST_PRUNED_AT.clear()

    monkeypatch.chdir(tmp_path)
    absolute_get_data_path = lambda filename: str((tmp_path / filename).resolve())

    save_realtime_prices_to_cache(
        {"005930": 100.0},
        source="test",
        get_data_path=absolute_get_data_path,
    )
    save_yfinance_failed_tickers(
        ["005930"],
        get_data_path=absolute_get_data_path,
    )

    runtime_db_alias = "./runtime_cache.db"
    normalized_key = realtime_price_cache.normalize_sqlite_db_key(runtime_db_alias)
    realtime_price_cache._invalidate_realtime_price_sqlite_ready(runtime_db_alias)

    with realtime_price_cache._YFINANCE_FAILED_MEMORY_CACHE_LOCK:
        assert normalized_key not in realtime_price_cache._YFINANCE_FAILED_MEMORY_CACHE
    with realtime_price_cache._SQLITE_PRUNE_STATE_LOCK:
        assert normalized_key not in realtime_price_cache._REALTIME_PRICE_LAST_PRUNED_AT
        assert normalized_key not in realtime_price_cache._YFINANCE_FAILED_LAST_PRUNED_AT


def test_realtime_price_sqlite_ready_uses_normalized_db_key(monkeypatch, tmp_path: Path):
    realtime_price_cache._REALTIME_PRICE_SQLITE_READY.clear()
    with realtime_price_cache._SQLITE_PRUNE_STATE_LOCK:
        realtime_price_cache._REALTIME_PRICE_LAST_PRUNED_AT.clear()
        realtime_price_cache._YFINANCE_FAILED_LAST_PRUNED_AT.clear()

    monkeypatch.chdir(tmp_path)
    connect_calls = {"count": 0}
    original_connect = realtime_price_cache.connect_sqlite

    def _counted_connect(*args, **kwargs):
        connect_calls["count"] += 1
        return original_connect(*args, **kwargs)

    monkeypatch.setattr(realtime_price_cache, "connect_sqlite", _counted_connect)

    relative_db_path = "./runtime_cache.db"
    absolute_db_path = str((tmp_path / "runtime_cache.db").resolve())

    assert realtime_price_cache._ensure_realtime_price_sqlite(relative_db_path, None) is True
    assert realtime_price_cache._ensure_realtime_price_sqlite(absolute_db_path, None) is True

    assert connect_calls["count"] == 1
    assert os.path.exists(absolute_db_path)


def test_realtime_price_sqlite_init_is_single_flight_under_concurrency(
    monkeypatch,
    tmp_path: Path,
):
    db_path = str(tmp_path / "runtime_cache.db")
    with realtime_price_cache._REALTIME_PRICE_SQLITE_READY_CONDITION:
        realtime_price_cache._REALTIME_PRICE_SQLITE_READY.clear()
        realtime_price_cache._REALTIME_PRICE_SQLITE_INIT_IN_PROGRESS.clear()

    monkeypatch.setattr(realtime_price_cache, "sqlite_db_path_exists", lambda _path: True)

    entered_event = threading.Event()
    release_event = threading.Event()
    run_calls = {"count": 0}

    def _run_once(_operation, *, max_retries, retry_delay_seconds):
        run_calls["count"] += 1
        if run_calls["count"] == 1:
            entered_event.set()
            assert release_event.wait(timeout=2.0)
        return None

    monkeypatch.setattr(realtime_price_cache, "run_sqlite_with_retry", _run_once)

    results: dict[str, bool] = {}

    def _worker(name: str) -> None:
        results[name] = bool(realtime_price_cache._ensure_realtime_price_sqlite(db_path, None))

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


def test_realtime_price_sqlite_waiter_retries_after_initializer_failure(
    monkeypatch,
    tmp_path: Path,
):
    db_path = str(tmp_path / "runtime_cache.db")
    with realtime_price_cache._REALTIME_PRICE_SQLITE_READY_CONDITION:
        realtime_price_cache._REALTIME_PRICE_SQLITE_READY.clear()
        realtime_price_cache._REALTIME_PRICE_SQLITE_INIT_IN_PROGRESS.clear()

    monkeypatch.setattr(realtime_price_cache, "sqlite_db_path_exists", lambda _path: True)

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

    monkeypatch.setattr(realtime_price_cache, "run_sqlite_with_retry", _fail_then_succeed)

    results: dict[str, bool] = {}

    def _worker(name: str) -> None:
        results[name] = bool(realtime_price_cache._ensure_realtime_price_sqlite(db_path, None))

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
