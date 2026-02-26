#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Signal Tracker source cache 리팩토링 테스트
"""

from __future__ import annotations

import os
import sqlite3
import threading
import time

import pandas as pd

import engine.signal_tracker_source_cache as source_cache


def test_serialize_signatures_are_compact_json():
    usecols_signature = source_cache._serialize_usecols(["ticker", "close"])
    dtype_signature = source_cache._serialize_dtype({"ticker": "str", "close": "float64"})

    assert usecols_signature == '["ticker","close"]'
    assert dtype_signature == '{"close":"float64","ticker":"str"}'


def test_load_signal_tracker_csv_cached_creates_sqlite_parent_dir_when_missing(monkeypatch, tmp_path):
    csv_path = tmp_path / "daily_prices.csv"
    pd.DataFrame(
        [
            {"ticker": "005930", "close": 100.0, "volume": 1_000},
        ]
    ).to_csv(csv_path, index=False, encoding="utf-8-sig")

    db_path = tmp_path / "cache" / "nested" / "runtime_cache.db"
    source_cache.clear_signal_tracker_source_cache(reset_sqlite_state=True)
    monkeypatch.setattr(source_cache, "_resolve_db_path", lambda _path: str(db_path))

    loaded = source_cache.load_signal_tracker_csv_cached(
        path=str(csv_path),
        cache_kind="price_source",
        usecols=["ticker", "close"],
        dtype={"ticker": str},
    )

    assert len(loaded) == 1
    assert loaded.iloc[0]["ticker"] == "005930"
    assert db_path.exists()

    with sqlite3.connect(str(db_path)) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT COUNT(*)
            FROM signal_tracker_source_cache
            WHERE cache_kind = ?
            """,
            ("price_source",),
        )
        row = cursor.fetchone()
    assert row and row[0] >= 1


def test_load_signal_tracker_csv_cached_prunes_sqlite_rows(monkeypatch, tmp_path):
    db_path = tmp_path / "runtime_cache.db"
    source_cache.clear_signal_tracker_source_cache(reset_sqlite_state=True)
    monkeypatch.setattr(source_cache, "_resolve_db_path", lambda _path: str(db_path))
    monkeypatch.setattr(source_cache, "_SOURCE_SQLITE_MAX_ROWS", 2)

    for idx in range(3):
        csv_path = tmp_path / f"daily_prices_{idx}.csv"
        pd.DataFrame(
            [
                {"ticker": "005930", "close": 100.0 + idx, "volume": 1_000 + idx},
            ]
        ).to_csv(csv_path, index=False, encoding="utf-8-sig")

        loaded = source_cache.load_signal_tracker_csv_cached(
            path=str(csv_path),
            cache_kind=f"price_source_{idx}",
            usecols=["ticker", "close"],
            dtype={"ticker": str},
        )
        assert len(loaded) == 1

    with sqlite3.connect(str(db_path)) as conn:
        row_count = int(
            conn.execute("SELECT COUNT(*) FROM signal_tracker_source_cache").fetchone()[0]
        )
    assert row_count == 2


def test_load_signal_tracker_csv_cached_projects_existing_columns_on_usecols_mismatch(
    tmp_path,
):
    csv_path = tmp_path / "daily_prices_usecols_mismatch.csv"
    pd.DataFrame(
        [
            {"ticker": "005930", "close": 100.0, "volume": 1_000},
            {"ticker": "000660", "close": 200.0, "volume": 2_000},
        ]
    ).to_csv(csv_path, index=False, encoding="utf-8-sig")

    source_cache.clear_signal_tracker_source_cache(reset_sqlite_state=True)
    calls = {"usecols": 0, "full": 0}
    original_read_csv = pd.read_csv

    def _fake_read_csv(path, *args, **kwargs):
        if kwargs.get("usecols") is not None:
            calls["usecols"] += 1
            raise ValueError("Usecols do not match columns")
        calls["full"] += 1
        return original_read_csv(path, *args, **kwargs)

    first = source_cache.load_signal_tracker_csv_cached(
        path=str(csv_path),
        cache_kind="price_source",
        usecols=["ticker", "missing_col"],
        read_csv=_fake_read_csv,
    )
    assert list(first.columns) == ["ticker"]
    assert len(first) == 2
    assert calls == {"usecols": 1, "full": 1}

    source_cache.clear_signal_tracker_source_cache(reset_sqlite_state=False)
    second = source_cache.load_signal_tracker_csv_cached(
        path=str(csv_path),
        cache_kind="price_source",
        usecols=["ticker", "missing_col"],
        read_csv=lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("read_csv should not run when sqlite snapshot is warm")
        ),
    )

    assert list(second.columns) == ["ticker"]
    assert len(second) == 2


def test_load_signal_tracker_csv_cached_recovers_when_sqlite_table_missing(monkeypatch, tmp_path):
    db_path = tmp_path / "runtime_cache.db"
    source_cache.clear_signal_tracker_source_cache(reset_sqlite_state=True)
    monkeypatch.setattr(source_cache, "_resolve_db_path", lambda _path: str(db_path))

    first_csv = tmp_path / "daily_prices_first.csv"
    first_csv.write_text("ticker,close\n005930,100\n", encoding="utf-8")
    loaded_first = source_cache.load_signal_tracker_csv_cached(
        path=str(first_csv),
        cache_kind="price_source",
        usecols=["ticker", "close"],
        dtype={"ticker": str},
    )
    assert len(loaded_first) == 1

    with sqlite3.connect(str(db_path)) as conn:
        conn.execute("DROP TABLE signal_tracker_source_cache")
        conn.commit()

    second_csv = tmp_path / "daily_prices_second.csv"
    second_csv.write_text("ticker,close\n000660,200\n", encoding="utf-8")
    loaded_second = source_cache.load_signal_tracker_csv_cached(
        path=str(second_csv),
        cache_kind="price_source",
        usecols=["ticker", "close"],
        dtype={"ticker": str},
    )
    assert len(loaded_second) == 1
    assert loaded_second.iloc[0]["ticker"] == "000660"

    with sqlite3.connect(str(db_path)) as conn:
        row_count = int(conn.execute("SELECT COUNT(*) FROM signal_tracker_source_cache").fetchone()[0])
    assert row_count >= 1


def test_load_signal_tracker_csv_cached_sqlite_load_uses_read_only_connection(monkeypatch, tmp_path):
    db_path = tmp_path / "runtime_cache.db"
    source_cache.clear_signal_tracker_source_cache(reset_sqlite_state=True)
    monkeypatch.setattr(source_cache, "_resolve_db_path", lambda _path: str(db_path))

    csv_path = tmp_path / "daily_prices_read_only.csv"
    pd.DataFrame([{"ticker": "005930", "close": 100.0}]).to_csv(csv_path, index=False, encoding="utf-8-sig")

    first = source_cache.load_signal_tracker_csv_cached(
        path=str(csv_path),
        cache_kind="price_source",
        usecols=["ticker", "close"],
        dtype={"ticker": str},
    )
    assert len(first) == 1

    source_cache.clear_signal_tracker_source_cache(reset_sqlite_state=False)
    read_only_flags: list[bool] = []
    original_connect = source_cache.connect_sqlite

    def _traced_connect(*args, **kwargs):
        if "read_only" in kwargs:
            read_only_flags.append(bool(kwargs["read_only"]))
        return original_connect(*args, **kwargs)

    monkeypatch.setattr(source_cache, "connect_sqlite", _traced_connect)
    monkeypatch.setattr(
        source_cache.pd,
        "read_csv",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("csv reader should not run when sqlite cache is warm")),
    )

    second = source_cache.load_signal_tracker_csv_cached(
        path=str(csv_path),
        cache_kind="price_source",
        usecols=["ticker", "close"],
        dtype={"ticker": str},
    )
    assert len(second) == 1
    assert True in read_only_flags


def test_load_signal_tracker_csv_cached_reuses_alias_memory_cache_without_sqlite_query(
    monkeypatch, tmp_path
):
    source_cache.clear_signal_tracker_source_cache(reset_sqlite_state=True)
    monkeypatch.chdir(tmp_path)

    csv_path = tmp_path / "daily_prices_alias.csv"
    pd.DataFrame([{"ticker": "005930", "close": 100.0}]).to_csv(csv_path, index=False, encoding="utf-8-sig")

    first = source_cache.load_signal_tracker_csv_cached(
        path="daily_prices_alias.csv",
        cache_kind="price_source",
        usecols=["ticker", "close"],
        dtype={"ticker": str},
    )
    assert len(first) == 1

    monkeypatch.setattr(
        source_cache,
        "connect_sqlite",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("should reuse source cache alias memory key")
        ),
    )
    monkeypatch.setattr(
        source_cache.pd,
        "read_csv",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("csv reader should not run when alias memory cache is warm")
        ),
    )

    second = source_cache.load_signal_tracker_csv_cached(
        path=str(csv_path),
        cache_kind="price_source",
        usecols=["ticker", "close"],
        dtype={"ticker": str},
    )
    assert len(second) == 1
    assert str(second.iloc[0]["ticker"]).zfill(6) == "005930"


def test_load_signal_tracker_csv_cached_reads_legacy_sqlite_source_path_key(
    monkeypatch, tmp_path
):
    source_cache.clear_signal_tracker_source_cache(reset_sqlite_state=True)
    monkeypatch.chdir(tmp_path)

    csv_path = tmp_path / "daily_prices_legacy.csv"
    pd.DataFrame([{"ticker": "005930", "close": 100.0}]).to_csv(csv_path, index=False, encoding="utf-8-sig")

    first = source_cache.load_signal_tracker_csv_cached(
        path="daily_prices_legacy.csv",
        cache_kind="price_source",
        usecols=["ticker", "close"],
        dtype={"ticker": str},
    )
    assert len(first) == 1

    with sqlite3.connect(str(tmp_path / "runtime_cache.db")) as conn:
        conn.execute(
            """
            UPDATE signal_tracker_source_cache
            SET source_path = ?
            WHERE source_path = ?
            """,
            ("daily_prices_legacy.csv", source_cache._normalize_path(str(csv_path))),
        )
        conn.commit()

    source_cache.clear_signal_tracker_source_cache(reset_sqlite_state=False)
    monkeypatch.setattr(
        source_cache.pd,
        "read_csv",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("should load signal tracker source cache from legacy sqlite key")
        ),
    )

    second = source_cache.load_signal_tracker_csv_cached(
        path=str(csv_path),
        cache_kind="price_source",
        usecols=["ticker", "close"],
        dtype={"ticker": str},
    )
    assert len(second) == 1
    assert str(second.iloc[0]["ticker"]).zfill(6) == "005930"


def test_load_signal_tracker_csv_cached_skips_delete_when_rows_within_limit(monkeypatch, tmp_path):
    db_path = tmp_path / "runtime_cache.db"
    source_cache.clear_signal_tracker_source_cache(reset_sqlite_state=True)
    monkeypatch.setattr(source_cache, "_resolve_db_path", lambda _path: str(db_path))
    monkeypatch.setattr(source_cache, "_SOURCE_SQLITE_MAX_ROWS", 16)

    traced_sql: list[str] = []
    original_connect = source_cache.connect_sqlite

    def _traced_connect(*args, **kwargs):
        conn = original_connect(*args, **kwargs)
        conn.set_trace_callback(traced_sql.append)
        return conn

    monkeypatch.setattr(source_cache, "connect_sqlite", _traced_connect)

    csv_path = tmp_path / "daily_prices_single.csv"
    pd.DataFrame([{"ticker": "005930", "close": 100.0}]).to_csv(csv_path, index=False, encoding="utf-8-sig")

    loaded = source_cache.load_signal_tracker_csv_cached(
        path=str(csv_path),
        cache_kind="price_source",
        usecols=["ticker", "close"],
        dtype={"ticker": str},
    )
    assert len(loaded) == 1
    assert not any("DELETE FROM signal_tracker_source_cache" in sql for sql in traced_sql)


def test_load_signal_tracker_csv_cached_repeated_snapshot_key_prunes_once(monkeypatch, tmp_path):
    db_path = tmp_path / "runtime_cache.db"
    source_cache.clear_signal_tracker_source_cache(reset_sqlite_state=True)
    monkeypatch.setattr(source_cache, "_resolve_db_path", lambda _path: str(db_path))
    monkeypatch.setattr(source_cache, "_SOURCE_SQLITE_PRUNE_FORCE_INTERVAL", 10_000)

    prune_calls = {"count": 0}
    original_prune = source_cache.prune_rows_by_updated_at_if_needed

    def _counted_prune(*args, **kwargs):
        prune_calls["count"] += 1
        return original_prune(*args, **kwargs)

    monkeypatch.setattr(source_cache, "prune_rows_by_updated_at_if_needed", _counted_prune)

    csv_path = tmp_path / "daily_prices_single.csv"
    pd.DataFrame([{"ticker": "005930", "close": 100.0}]).to_csv(csv_path, index=False, encoding="utf-8-sig")

    first = source_cache.load_signal_tracker_csv_cached(
        path=str(csv_path),
        cache_kind="price_source",
        usecols=["ticker", "close"],
        dtype={"ticker": str},
    )
    assert len(first) == 1

    time.sleep(0.001)
    pd.DataFrame([{"ticker": "005930", "close": 101.0}]).to_csv(csv_path, index=False, encoding="utf-8-sig")
    source_cache.clear_signal_tracker_source_cache(reset_sqlite_state=False)

    second = source_cache.load_signal_tracker_csv_cached(
        path=str(csv_path),
        cache_kind="price_source",
        usecols=["ticker", "close"],
        dtype={"ticker": str},
    )
    assert len(second) == 1
    assert prune_calls["count"] == 1


def test_load_signal_tracker_csv_cached_forces_prune_on_configured_interval(monkeypatch, tmp_path):
    db_path = tmp_path / "runtime_cache.db"
    source_cache.clear_signal_tracker_source_cache(reset_sqlite_state=True)
    monkeypatch.setattr(source_cache, "_resolve_db_path", lambda _path: str(db_path))
    monkeypatch.setattr(source_cache, "_SOURCE_SQLITE_PRUNE_FORCE_INTERVAL", 2)

    prune_calls = {"count": 0}
    original_prune = source_cache.prune_rows_by_updated_at_if_needed

    def _counted_prune(*args, **kwargs):
        prune_calls["count"] += 1
        return original_prune(*args, **kwargs)

    monkeypatch.setattr(source_cache, "prune_rows_by_updated_at_if_needed", _counted_prune)

    csv_path = tmp_path / "daily_prices_single.csv"
    pd.DataFrame([{"ticker": "005930", "close": 100.0}]).to_csv(csv_path, index=False, encoding="utf-8-sig")

    first = source_cache.load_signal_tracker_csv_cached(
        path=str(csv_path),
        cache_kind="price_source",
        usecols=["ticker", "close"],
        dtype={"ticker": str},
    )
    assert len(first) == 1

    time.sleep(0.001)
    pd.DataFrame([{"ticker": "005930", "close": 101.0}]).to_csv(csv_path, index=False, encoding="utf-8-sig")
    source_cache.clear_signal_tracker_source_cache(reset_sqlite_state=False)

    second = source_cache.load_signal_tracker_csv_cached(
        path=str(csv_path),
        cache_kind="price_source",
        usecols=["ticker", "close"],
        dtype={"ticker": str},
    )
    assert len(second) == 1
    assert prune_calls["count"] == 2


def test_signal_tracker_source_sqlite_ready_cache_uses_normalized_db_key(monkeypatch, tmp_path):
    source_cache.clear_signal_tracker_source_cache(reset_sqlite_state=True)
    db_path = tmp_path / "runtime_cache.db"
    connect_calls = {"count": 0}
    original_connect = source_cache.connect_sqlite

    def _counted_connect(*args, **kwargs):
        connect_calls["count"] += 1
        return original_connect(*args, **kwargs)

    monkeypatch.setattr(source_cache, "connect_sqlite", _counted_connect)

    assert source_cache._ensure_source_cache_sqlite(str(db_path), None) is True

    monkeypatch.chdir(tmp_path)
    relative_db_path = os.path.relpath(str(db_path), str(tmp_path))
    assert source_cache._ensure_source_cache_sqlite(relative_db_path, None) is True

    assert connect_calls["count"] == 1


def test_signal_tracker_source_sqlite_schema_init_is_single_flight_under_concurrency(
    monkeypatch,
    tmp_path,
):
    source_cache.clear_signal_tracker_source_cache(reset_sqlite_state=True)
    db_path = str(tmp_path / "runtime_cache.db")

    monkeypatch.setattr(source_cache, "sqlite_db_path_exists", lambda _path: True)

    entered_event = threading.Event()
    release_event = threading.Event()
    run_calls = {"count": 0}

    def _run_once(_operation, *, max_retries, retry_delay_seconds):
        run_calls["count"] += 1
        if run_calls["count"] == 1:
            entered_event.set()
            assert release_event.wait(timeout=2.0)
        return None

    monkeypatch.setattr(source_cache, "run_sqlite_with_retry", _run_once)

    results: dict[str, bool] = {}

    def _worker(name: str) -> None:
        results[name] = bool(source_cache._ensure_source_cache_sqlite(db_path, None))

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


def test_signal_tracker_source_sqlite_waiter_retries_after_initializer_failure(
    monkeypatch,
    tmp_path,
):
    source_cache.clear_signal_tracker_source_cache(reset_sqlite_state=True)
    db_path = str(tmp_path / "runtime_cache.db")

    monkeypatch.setattr(source_cache, "sqlite_db_path_exists", lambda _path: True)

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

    monkeypatch.setattr(source_cache, "run_sqlite_with_retry", _fail_then_succeed)

    results: dict[str, bool] = {}

    def _worker(name: str) -> None:
        results[name] = bool(source_cache._ensure_source_cache_sqlite(db_path, None))

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


def test_signal_tracker_source_sqlite_ready_cache_is_bounded(monkeypatch, tmp_path):
    source_cache.clear_signal_tracker_source_cache(reset_sqlite_state=True)
    monkeypatch.setattr(source_cache, "_SOURCE_SQLITE_READY_MAX_ENTRIES", 1)
    monkeypatch.setattr(source_cache, "sqlite_db_path_exists", lambda _path: True)
    monkeypatch.setattr(
        source_cache,
        "run_sqlite_with_retry",
        lambda _operation, *, max_retries, retry_delay_seconds: None,
    )

    first_db_path = str(tmp_path / "first.db")
    second_db_path = str(tmp_path / "second.db")

    assert source_cache._ensure_source_cache_sqlite(first_db_path, None) is True
    assert source_cache._ensure_source_cache_sqlite(second_db_path, None) is True

    with source_cache._SOURCE_SQLITE_READY_CONDITION:
        assert len(source_cache._SOURCE_SQLITE_READY) == 1
        assert source_cache.normalize_sqlite_db_key(second_db_path) in source_cache._SOURCE_SQLITE_READY


def test_load_signal_tracker_csv_cached_memory_cache_is_bounded_lru(monkeypatch, tmp_path):
    source_cache.clear_signal_tracker_source_cache(reset_sqlite_state=True)
    monkeypatch.setattr(source_cache, "_SOURCE_MEMORY_CACHE_MAX_ENTRIES", 2)

    first_csv = tmp_path / "daily_prices_first_lru.csv"
    second_csv = tmp_path / "daily_prices_second_lru.csv"
    third_csv = tmp_path / "daily_prices_third_lru.csv"

    for index, path in enumerate((first_csv, second_csv, third_csv), start=1):
        pd.DataFrame(
            [
                {"ticker": "005930", "close": 100.0 + index},
            ]
        ).to_csv(path, index=False, encoding="utf-8-sig")

    usecols = ["ticker", "close"]
    dtype = {"ticker": str}

    _ = source_cache.load_signal_tracker_csv_cached(
        path=str(first_csv),
        cache_kind="price_source",
        usecols=usecols,
        dtype=dtype,
    )
    _ = source_cache.load_signal_tracker_csv_cached(
        path=str(second_csv),
        cache_kind="price_source",
        usecols=usecols,
        dtype=dtype,
    )
    _ = source_cache.load_signal_tracker_csv_cached(
        path=str(first_csv),
        cache_kind="price_source",
        usecols=usecols,
        dtype=dtype,
    )
    _ = source_cache.load_signal_tracker_csv_cached(
        path=str(third_csv),
        cache_kind="price_source",
        usecols=usecols,
        dtype=dtype,
    )

    usecols_signature = source_cache._serialize_usecols(usecols)
    dtype_signature = source_cache._serialize_dtype(dtype)
    first_key = (source_cache._normalize_path(str(first_csv)), "price_source", usecols_signature, dtype_signature)
    second_key = (source_cache._normalize_path(str(second_csv)), "price_source", usecols_signature, dtype_signature)
    third_key = (source_cache._normalize_path(str(third_csv)), "price_source", usecols_signature, dtype_signature)

    with source_cache._SOURCE_CACHE_LOCK:
        cached_keys = list(source_cache._SOURCE_CACHE.keys())

    assert len(cached_keys) == 2
    assert first_key in cached_keys
    assert third_key in cached_keys
    assert second_key not in cached_keys
