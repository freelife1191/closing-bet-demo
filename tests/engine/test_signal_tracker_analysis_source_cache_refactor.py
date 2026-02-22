#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Signal Tracker analysis source cache 리팩토링 테스트
"""

from __future__ import annotations

import os
import sqlite3
import threading
import time

import pandas as pd

import engine.signal_tracker_analysis_source_cache as source_cache


def _reset_csv_source_cache_state() -> None:
    source_cache.PERFORMANCE_SOURCE_CACHE.clear()
    source_cache.SUPPLY_SOURCE_CACHE.clear()
    source_cache.SIGNALS_LOG_SOURCE_CACHE.clear()
    with source_cache.CSV_SOURCE_SQLITE_READY_CONDITION:
        source_cache.CSV_SOURCE_SQLITE_READY.clear()
        source_cache.CSV_SOURCE_SQLITE_INIT_IN_PROGRESS.clear()
    with source_cache.CSV_SOURCE_SQLITE_KNOWN_KEYS_LOCK:
        source_cache.CSV_SOURCE_SQLITE_KNOWN_KEYS.clear()
    with source_cache.CSV_SOURCE_SQLITE_SAVE_COUNTER_LOCK:
        source_cache.CSV_SOURCE_SQLITE_SAVE_COUNTER = 0


def test_usecols_signature_is_compact_and_sorted():
    signature = source_cache._usecols_signature({"close", "ticker"})
    assert signature == '["close","ticker"]'


def test_load_csv_with_signature_cache_normalizes_relative_and_absolute_path(monkeypatch, tmp_path):
    csv_path = tmp_path / "sample.csv"
    pd.DataFrame([{"ticker": "005930", "score": 90}]).to_csv(csv_path, index=False, encoding="utf-8-sig")

    monkeypatch.chdir(tmp_path)
    calls = {"count": 0}
    original_read_csv = source_cache.pd.read_csv

    def _counted_read_csv(*args, **kwargs):
        calls["count"] += 1
        return original_read_csv(*args, **kwargs)

    monkeypatch.setattr(source_cache.pd, "read_csv", _counted_read_csv)

    cache: dict[str, tuple[tuple[int, int, int], pd.DataFrame]] = {}
    first = source_cache.load_csv_with_signature_cache(
        path="sample.csv",
        usecols_filter=None,
        cache=cache,
        sqlite_cache_kind=None,
    )
    second = source_cache.load_csv_with_signature_cache(
        path=str(csv_path),
        usecols_filter=None,
        cache=cache,
        sqlite_cache_kind=None,
    )

    assert len(first) == 1
    assert len(second) == 1
    assert calls["count"] == 1
    assert list(cache.keys()) == [os.path.abspath(str(csv_path))]


def test_load_csv_with_signature_cache_creates_sqlite_parent_dir_when_missing(monkeypatch, tmp_path):
    csv_path = tmp_path / "signals_log.csv"
    pd.DataFrame(
        [
            {
                "status": "OPEN",
                "return_pct": 0.0,
                "signal_date": "2026-02-20",
                "exit_date": "",
                "hold_days": 1,
            }
        ]
    ).to_csv(csv_path, index=False, encoding="utf-8-sig")

    db_path = tmp_path / "cache" / "nested" / "runtime_cache.db"
    _reset_csv_source_cache_state()
    monkeypatch.setattr(source_cache, "_source_cache_db_path", lambda _path: str(db_path))

    cache: dict[str, tuple[tuple[int, int, int], pd.DataFrame]] = {}
    loaded = source_cache.load_csv_with_signature_cache(
        path=str(csv_path),
        usecols_filter={"status", "return_pct", "signal_date", "exit_date", "hold_days"},
        cache=cache,
        sqlite_cache_kind="performance_source",
    )

    assert len(loaded) == 1
    assert db_path.exists()

    with sqlite3.connect(str(db_path)) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT COUNT(*)
            FROM signal_tracker_csv_source_cache
            WHERE cache_kind = ?
            """,
            ("performance_source",),
        )
        row = cursor.fetchone()
    assert row and row[0] >= 1


def test_load_csv_with_signature_cache_prunes_sqlite_rows(monkeypatch, tmp_path):
    db_path = tmp_path / "runtime_cache.db"
    _reset_csv_source_cache_state()
    monkeypatch.setattr(source_cache, "_source_cache_db_path", lambda _path: str(db_path))
    monkeypatch.setattr(source_cache, "CSV_SOURCE_SQLITE_MAX_ROWS", 2)

    for index in range(3):
        csv_path = tmp_path / f"signals_{index}.csv"
        pd.DataFrame(
            [
                {
                    "status": "OPEN",
                    "return_pct": float(index),
                    "signal_date": "2026-02-20",
                    "exit_date": "",
                    "hold_days": 1,
                }
            ]
        ).to_csv(csv_path, index=False, encoding="utf-8-sig")

        cache: dict[str, tuple[tuple[int, int, int], pd.DataFrame]] = {}
        loaded = source_cache.load_csv_with_signature_cache(
            path=str(csv_path),
            usecols_filter={"status", "return_pct", "signal_date", "exit_date", "hold_days"},
            cache=cache,
            sqlite_cache_kind=f"performance_source_{index}",
        )
        assert len(loaded) == 1

    with sqlite3.connect(str(db_path)) as conn:
        row_count = int(
            conn.execute("SELECT COUNT(*) FROM signal_tracker_csv_source_cache").fetchone()[0]
        )
    assert row_count == 2


def test_load_csv_with_signature_cache_recovers_when_sqlite_table_missing(monkeypatch, tmp_path):
    db_path = tmp_path / "runtime_cache.db"
    _reset_csv_source_cache_state()
    monkeypatch.setattr(source_cache, "_source_cache_db_path", lambda _path: str(db_path))

    first_csv = tmp_path / "signals_first.csv"
    pd.DataFrame(
        [
            {"status": "OPEN", "return_pct": 1.0, "signal_date": "2026-02-20", "exit_date": "", "hold_days": 1}
        ]
    ).to_csv(first_csv, index=False, encoding="utf-8-sig")

    cache: dict[str, tuple[tuple[int, int, int], pd.DataFrame]] = {}
    first_loaded = source_cache.load_csv_with_signature_cache(
        path=str(first_csv),
        usecols_filter={"status", "return_pct", "signal_date", "exit_date", "hold_days"},
        cache=cache,
        sqlite_cache_kind="performance_source",
    )
    assert len(first_loaded) == 1

    with sqlite3.connect(str(db_path)) as conn:
        conn.execute("DROP TABLE signal_tracker_csv_source_cache")
        conn.commit()

    second_csv = tmp_path / "signals_second.csv"
    pd.DataFrame(
        [
            {"status": "OPEN", "return_pct": 2.0, "signal_date": "2026-02-21", "exit_date": "", "hold_days": 2}
        ]
    ).to_csv(second_csv, index=False, encoding="utf-8-sig")

    cache = {}
    second_loaded = source_cache.load_csv_with_signature_cache(
        path=str(second_csv),
        usecols_filter={"status", "return_pct", "signal_date", "exit_date", "hold_days"},
        cache=cache,
        sqlite_cache_kind="performance_source",
    )
    assert len(second_loaded) == 1
    assert float(second_loaded.iloc[0]["return_pct"]) == 2.0

    with sqlite3.connect(str(db_path)) as conn:
        row_count = int(conn.execute("SELECT COUNT(*) FROM signal_tracker_csv_source_cache").fetchone()[0])
    assert row_count >= 1


def test_load_csv_with_signature_cache_sqlite_load_uses_read_only_connection(monkeypatch, tmp_path):
    db_path = tmp_path / "runtime_cache.db"
    _reset_csv_source_cache_state()
    monkeypatch.setattr(source_cache, "_source_cache_db_path", lambda _path: str(db_path))

    csv_path = tmp_path / "signals_read_only.csv"
    pd.DataFrame(
        [
            {"status": "OPEN", "return_pct": 1.0, "signal_date": "2026-02-22", "exit_date": "", "hold_days": 1}
        ]
    ).to_csv(csv_path, index=False, encoding="utf-8-sig")

    cache: dict[str, tuple[tuple[int, int, int], pd.DataFrame]] = {}
    first = source_cache.load_csv_with_signature_cache(
        path=str(csv_path),
        usecols_filter={"status", "return_pct", "signal_date", "exit_date", "hold_days"},
        cache=cache,
        sqlite_cache_kind="performance_source",
    )
    assert len(first) == 1

    source_cache.PERFORMANCE_SOURCE_CACHE.clear()
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

    second = source_cache.load_csv_with_signature_cache(
        path=str(csv_path),
        usecols_filter={"status", "return_pct", "signal_date", "exit_date", "hold_days"},
        cache={},
        sqlite_cache_kind="performance_source",
    )
    assert len(second) == 1
    assert True in read_only_flags


def test_load_csv_with_signature_cache_reads_legacy_sqlite_source_path_key(
    monkeypatch, tmp_path
):
    db_path = tmp_path / "runtime_cache.db"
    _reset_csv_source_cache_state()
    monkeypatch.setattr(source_cache, "_source_cache_db_path", lambda _path: str(db_path))
    monkeypatch.chdir(tmp_path)

    csv_path = tmp_path / "signals_legacy.csv"
    pd.DataFrame(
        [
            {"status": "OPEN", "return_pct": 1.0, "signal_date": "2026-02-22", "exit_date": "", "hold_days": 1}
        ]
    ).to_csv(csv_path, index=False, encoding="utf-8-sig")

    first = source_cache.load_csv_with_signature_cache(
        path="signals_legacy.csv",
        usecols_filter={"status", "return_pct", "signal_date", "exit_date", "hold_days"},
        cache={},
        sqlite_cache_kind="performance_source",
    )
    assert len(first) == 1

    with sqlite3.connect(str(db_path)) as conn:
        conn.execute(
            """
            UPDATE signal_tracker_csv_source_cache
            SET source_path = ?
            WHERE source_path = ?
            """,
            ("signals_legacy.csv", source_cache._normalize_source_path(str(csv_path))),
        )
        conn.commit()

    source_cache.PERFORMANCE_SOURCE_CACHE.clear()
    source_cache.SUPPLY_SOURCE_CACHE.clear()
    source_cache.SIGNALS_LOG_SOURCE_CACHE.clear()
    monkeypatch.setattr(
        source_cache.pd,
        "read_csv",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("should load analysis source cache from legacy sqlite key")
        ),
    )

    second = source_cache.load_csv_with_signature_cache(
        path=str(csv_path),
        usecols_filter={"status", "return_pct", "signal_date", "exit_date", "hold_days"},
        cache={},
        sqlite_cache_kind="performance_source",
    )
    assert len(second) == 1
    assert float(second.iloc[0]["return_pct"]) == 1.0


def test_load_csv_with_signature_cache_skips_delete_when_rows_within_limit(monkeypatch, tmp_path):
    db_path = tmp_path / "runtime_cache.db"
    _reset_csv_source_cache_state()
    monkeypatch.setattr(source_cache, "_source_cache_db_path", lambda _path: str(db_path))
    monkeypatch.setattr(source_cache, "CSV_SOURCE_SQLITE_MAX_ROWS", 16)

    traced_sql: list[str] = []
    original_connect = source_cache.connect_sqlite

    def _traced_connect(*args, **kwargs):
        conn = original_connect(*args, **kwargs)
        conn.set_trace_callback(traced_sql.append)
        return conn

    monkeypatch.setattr(source_cache, "connect_sqlite", _traced_connect)

    csv_path = tmp_path / "signals_single.csv"
    pd.DataFrame(
        [
            {"status": "OPEN", "return_pct": 1.0, "signal_date": "2026-02-22", "exit_date": "", "hold_days": 1}
        ]
    ).to_csv(csv_path, index=False, encoding="utf-8-sig")

    cache: dict[str, tuple[tuple[int, int, int], pd.DataFrame]] = {}
    loaded = source_cache.load_csv_with_signature_cache(
        path=str(csv_path),
        usecols_filter={"status", "return_pct", "signal_date", "exit_date", "hold_days"},
        cache=cache,
        sqlite_cache_kind="performance_source",
    )
    assert len(loaded) == 1
    assert not any("DELETE FROM signal_tracker_csv_source_cache" in sql for sql in traced_sql)


def test_load_csv_with_signature_cache_repeated_snapshot_key_prunes_once(monkeypatch, tmp_path):
    db_path = tmp_path / "runtime_cache.db"
    _reset_csv_source_cache_state()
    monkeypatch.setattr(source_cache, "_source_cache_db_path", lambda _path: str(db_path))
    monkeypatch.setattr(source_cache, "CSV_SOURCE_SQLITE_PRUNE_FORCE_INTERVAL", 10_000)

    prune_calls = {"count": 0}
    original_prune = source_cache.prune_rows_by_updated_at_if_needed

    def _counted_prune(*args, **kwargs):
        prune_calls["count"] += 1
        return original_prune(*args, **kwargs)

    monkeypatch.setattr(source_cache, "prune_rows_by_updated_at_if_needed", _counted_prune)

    csv_path = tmp_path / "signals_single.csv"
    pd.DataFrame(
        [
            {"status": "OPEN", "return_pct": 1.0, "signal_date": "2026-02-22", "exit_date": "", "hold_days": 1}
        ]
    ).to_csv(csv_path, index=False, encoding="utf-8-sig")

    first = source_cache.load_csv_with_signature_cache(
        path=str(csv_path),
        usecols_filter={"status", "return_pct", "signal_date", "exit_date", "hold_days"},
        cache={},
        sqlite_cache_kind="performance_source",
    )
    assert len(first) == 1

    time.sleep(0.001)
    pd.DataFrame(
        [
            {"status": "OPEN", "return_pct": 2.0, "signal_date": "2026-02-23", "exit_date": "", "hold_days": 2}
        ]
    ).to_csv(csv_path, index=False, encoding="utf-8-sig")

    second = source_cache.load_csv_with_signature_cache(
        path=str(csv_path),
        usecols_filter={"status", "return_pct", "signal_date", "exit_date", "hold_days"},
        cache={},
        sqlite_cache_kind="performance_source",
    )
    assert len(second) == 1
    assert prune_calls["count"] == 1


def test_load_csv_with_signature_cache_forces_prune_on_configured_interval(monkeypatch, tmp_path):
    db_path = tmp_path / "runtime_cache.db"
    _reset_csv_source_cache_state()
    monkeypatch.setattr(source_cache, "_source_cache_db_path", lambda _path: str(db_path))
    monkeypatch.setattr(source_cache, "CSV_SOURCE_SQLITE_PRUNE_FORCE_INTERVAL", 2)

    prune_calls = {"count": 0}
    original_prune = source_cache.prune_rows_by_updated_at_if_needed

    def _counted_prune(*args, **kwargs):
        prune_calls["count"] += 1
        return original_prune(*args, **kwargs)

    monkeypatch.setattr(source_cache, "prune_rows_by_updated_at_if_needed", _counted_prune)

    csv_path = tmp_path / "signals_single.csv"
    pd.DataFrame(
        [
            {"status": "OPEN", "return_pct": 1.0, "signal_date": "2026-02-22", "exit_date": "", "hold_days": 1}
        ]
    ).to_csv(csv_path, index=False, encoding="utf-8-sig")

    first = source_cache.load_csv_with_signature_cache(
        path=str(csv_path),
        usecols_filter={"status", "return_pct", "signal_date", "exit_date", "hold_days"},
        cache={},
        sqlite_cache_kind="performance_source",
    )
    assert len(first) == 1

    time.sleep(0.001)
    pd.DataFrame(
        [
            {"status": "OPEN", "return_pct": 2.0, "signal_date": "2026-02-23", "exit_date": "", "hold_days": 2}
        ]
    ).to_csv(csv_path, index=False, encoding="utf-8-sig")

    second = source_cache.load_csv_with_signature_cache(
        path=str(csv_path),
        usecols_filter={"status", "return_pct", "signal_date", "exit_date", "hold_days"},
        cache={},
        sqlite_cache_kind="performance_source",
    )
    assert len(second) == 1
    assert prune_calls["count"] == 2


def test_csv_source_sqlite_ready_cache_uses_normalized_db_key(monkeypatch, tmp_path):
    db_path = tmp_path / "runtime_cache.db"
    _reset_csv_source_cache_state()
    connect_calls = {"count": 0}
    original_connect = source_cache.connect_sqlite

    def _counted_connect(*args, **kwargs):
        connect_calls["count"] += 1
        return original_connect(*args, **kwargs)

    monkeypatch.setattr(source_cache, "connect_sqlite", _counted_connect)

    assert source_cache._ensure_csv_source_sqlite_cache(str(db_path)) is True

    monkeypatch.chdir(tmp_path)
    assert source_cache._ensure_csv_source_sqlite_cache("runtime_cache.db") is True

    assert connect_calls["count"] == 1


def test_csv_source_sqlite_schema_init_is_single_flight_under_concurrency(monkeypatch, tmp_path):
    _reset_csv_source_cache_state()
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
        results[name] = bool(source_cache._ensure_csv_source_sqlite_cache(db_path))

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


def test_csv_source_sqlite_waiter_retries_after_initializer_failure(monkeypatch, tmp_path):
    _reset_csv_source_cache_state()
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
        results[name] = bool(source_cache._ensure_csv_source_sqlite_cache(db_path))

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


def test_csv_source_sqlite_ready_cache_is_bounded(monkeypatch, tmp_path):
    _reset_csv_source_cache_state()
    monkeypatch.setattr(source_cache, "CSV_SOURCE_SQLITE_READY_MAX_ENTRIES", 1)
    monkeypatch.setattr(source_cache, "sqlite_db_path_exists", lambda _path: True)
    monkeypatch.setattr(
        source_cache,
        "run_sqlite_with_retry",
        lambda _operation, *, max_retries, retry_delay_seconds: None,
    )

    first_db_path = str(tmp_path / "first.db")
    second_db_path = str(tmp_path / "second.db")

    assert source_cache._ensure_csv_source_sqlite_cache(first_db_path) is True
    assert source_cache._ensure_csv_source_sqlite_cache(second_db_path) is True

    with source_cache.CSV_SOURCE_SQLITE_READY_CONDITION:
        assert len(source_cache.CSV_SOURCE_SQLITE_READY) == 1
        assert source_cache.normalize_sqlite_db_key(second_db_path) in source_cache.CSV_SOURCE_SQLITE_READY


def test_load_csv_with_signature_cache_memory_cache_is_bounded_lru(monkeypatch, tmp_path):
    _reset_csv_source_cache_state()
    monkeypatch.setattr(source_cache, "CSV_SOURCE_MEMORY_CACHE_MAX_ENTRIES", 2)

    first_csv = tmp_path / "signals_first.csv"
    second_csv = tmp_path / "signals_second.csv"
    third_csv = tmp_path / "signals_third.csv"

    for index, path in enumerate((first_csv, second_csv, third_csv), start=1):
        pd.DataFrame(
            [
                {
                    "status": "OPEN",
                    "return_pct": float(index),
                    "signal_date": "2026-02-20",
                    "exit_date": "",
                    "hold_days": index,
                }
            ]
        ).to_csv(path, index=False, encoding="utf-8-sig")

    _ = source_cache.load_csv_with_signature_cache(
        path=str(first_csv),
        usecols_filter=None,
        cache=source_cache.PERFORMANCE_SOURCE_CACHE,
        sqlite_cache_kind=None,
    )
    _ = source_cache.load_csv_with_signature_cache(
        path=str(second_csv),
        usecols_filter=None,
        cache=source_cache.PERFORMANCE_SOURCE_CACHE,
        sqlite_cache_kind=None,
    )
    _ = source_cache.load_csv_with_signature_cache(
        path=str(first_csv),
        usecols_filter=None,
        cache=source_cache.PERFORMANCE_SOURCE_CACHE,
        sqlite_cache_kind=None,
    )
    _ = source_cache.load_csv_with_signature_cache(
        path=str(third_csv),
        usecols_filter=None,
        cache=source_cache.PERFORMANCE_SOURCE_CACHE,
        sqlite_cache_kind=None,
    )

    cached_keys = list(source_cache.PERFORMANCE_SOURCE_CACHE.keys())
    first_key = os.path.abspath(str(first_csv))
    second_key = os.path.abspath(str(second_csv))
    third_key = os.path.abspath(str(third_csv))

    assert len(cached_keys) == 2
    assert first_key in cached_keys
    assert third_key in cached_keys
    assert second_key not in cached_keys
