#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KR Market realtime price cache(SQLite) 테스트
"""

from __future__ import annotations

import sqlite3
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
