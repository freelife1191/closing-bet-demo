#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KR Market Backtest Summary Cache 단위 테스트
"""

from __future__ import annotations

import logging
import sqlite3
import threading
import time

from services import kr_market_backtest_summary_cache as summary_cache
from services.sqlite_utils import connect_sqlite


def _reset_cache_state() -> None:
    summary_cache.clear_backtest_summary_cache()
    with summary_cache._BACKTEST_SUMMARY_SQLITE_CONDITION:
        summary_cache._BACKTEST_SUMMARY_SQLITE_READY.clear()
        summary_cache._BACKTEST_SUMMARY_SQLITE_INIT_IN_PROGRESS.clear()
    with summary_cache._BACKTEST_SUMMARY_SQLITE_KNOWN_HASHES_LOCK:
        summary_cache._BACKTEST_SUMMARY_SQLITE_KNOWN_HASHES.clear()
    with summary_cache._BACKTEST_SUMMARY_SQLITE_SAVE_COUNTER_LOCK:
        summary_cache._BACKTEST_SUMMARY_SQLITE_SAVE_COUNTER = 0


def test_save_cached_backtest_summary_prunes_sqlite_rows(tmp_path, monkeypatch):
    _reset_cache_state()
    monkeypatch.setattr(
        summary_cache,
        "_BACKTEST_SUMMARY_CACHE_DB_PATH",
        str(tmp_path / "runtime_cache.db"),
    )
    monkeypatch.setattr(summary_cache, "_BACKTEST_SUMMARY_SQLITE_MAX_ROWS", 2)

    logger = logging.getLogger("test-backtest-sqlite-prune")

    for idx in range(5):
        summary_cache.save_cached_backtest_summary(
            signature=(("seed", idx),),
            payload={"vcp": {"count": idx}, "closing_bet": {"count": idx}},
            logger=logger,
        )

    with connect_sqlite(str(tmp_path / "runtime_cache.db")) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM backtest_summary_cache")
        row_count = int(cursor.fetchone()[0])

    assert row_count == 2


def test_save_cached_backtest_summary_bounds_memory_entries(monkeypatch):
    _reset_cache_state()
    monkeypatch.setattr(summary_cache, "_BACKTEST_SUMMARY_MEMORY_MAX_ENTRIES", 2)

    logger = logging.getLogger("test-backtest-memory-bound")

    summary_cache.save_cached_backtest_summary(
        signature=(("seed", 1),),
        payload={"id": 1},
        logger=logger,
    )
    summary_cache.save_cached_backtest_summary(
        signature=(("seed", 2),),
        payload={"id": 2},
        logger=logger,
    )
    summary_cache.save_cached_backtest_summary(
        signature=(("seed", 3),),
        payload={"id": 3},
        logger=logger,
    )

    assert len(summary_cache._BACKTEST_SUMMARY_CACHE) <= 2
    assert (("seed", 3),) in summary_cache._BACKTEST_SUMMARY_CACHE


def test_save_cached_backtest_summary_evicts_oldest_entry_instead_of_clearing(monkeypatch):
    _reset_cache_state()
    monkeypatch.setattr(summary_cache, "_BACKTEST_SUMMARY_MEMORY_MAX_ENTRIES", 2)
    logger = logging.getLogger("test-backtest-memory-lru")

    summary_cache.save_cached_backtest_summary(signature=(("seed", 1),), payload={"id": 1}, logger=logger)
    summary_cache.save_cached_backtest_summary(signature=(("seed", 2),), payload={"id": 2}, logger=logger)
    summary_cache.save_cached_backtest_summary(signature=(("seed", 3),), payload={"id": 3}, logger=logger)

    cache_keys = set(summary_cache._BACKTEST_SUMMARY_CACHE.keys())
    assert cache_keys == {(("seed", 2),), (("seed", 3),)}


def test_save_cached_backtest_summary_keeps_recently_used_entry_on_eviction(monkeypatch):
    _reset_cache_state()
    monkeypatch.setattr(summary_cache, "_BACKTEST_SUMMARY_MEMORY_MAX_ENTRIES", 2)
    logger = logging.getLogger("test-backtest-memory-lru-hit")

    summary_cache.save_cached_backtest_summary(signature=(("seed", 1),), payload={"id": 1}, logger=logger)
    summary_cache.save_cached_backtest_summary(signature=(("seed", 2),), payload={"id": 2}, logger=logger)
    cached = summary_cache.get_cached_backtest_summary(signature=(("seed", 1),), logger=logger)
    assert cached is not None
    summary_cache.save_cached_backtest_summary(signature=(("seed", 3),), payload={"id": 3}, logger=logger)

    cache_keys = set(summary_cache._BACKTEST_SUMMARY_CACHE.keys())
    assert cache_keys == {(("seed", 1),), (("seed", 3),)}


def test_get_cached_backtest_summary_sqlite_load_respects_memory_limit(tmp_path, monkeypatch):
    _reset_cache_state()
    monkeypatch.setattr(summary_cache, "_BACKTEST_SUMMARY_MEMORY_MAX_ENTRIES", 1)
    monkeypatch.setattr(
        summary_cache,
        "_BACKTEST_SUMMARY_CACHE_DB_PATH",
        str(tmp_path / "runtime_cache.db"),
    )
    logger = logging.getLogger("test-backtest-memory-bound-on-sqlite-load")

    summary_cache.save_cached_backtest_summary(
        signature=(("seed", 1),),
        payload={"id": 1},
        logger=logger,
    )
    summary_cache.save_cached_backtest_summary(
        signature=(("seed", 2),),
        payload={"id": 2},
        logger=logger,
    )
    summary_cache.clear_backtest_summary_cache()

    loaded_first = summary_cache.get_cached_backtest_summary(
        signature=(("seed", 1),),
        logger=logger,
    )
    assert loaded_first == {"id": 1}
    loaded_second = summary_cache.get_cached_backtest_summary(
        signature=(("seed", 2),),
        logger=logger,
    )
    assert loaded_second == {"id": 2}

    assert len(summary_cache._BACKTEST_SUMMARY_CACHE) == 1
    assert (("seed", 2),) in summary_cache._BACKTEST_SUMMARY_CACHE


def test_backtest_summary_cache_supports_sqlite_db_path_without_parent_dir(tmp_path, monkeypatch):
    _reset_cache_state()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(summary_cache, "_BACKTEST_SUMMARY_CACHE_DB_PATH", "runtime_cache.db")
    summary_cache._BACKTEST_SUMMARY_SQLITE_READY.clear()

    signature = (("seed", 7),)
    payload = {"vcp": {"count": 7}, "closing_bet": {"count": 7}}
    logger = logging.getLogger("test-backtest-sqlite-no-parent")

    summary_cache.save_cached_backtest_summary(
        signature=signature,
        payload=payload,
        logger=logger,
    )
    summary_cache.clear_backtest_summary_cache()

    loaded = summary_cache.get_cached_backtest_summary(
        signature=signature,
        logger=logger,
    )
    assert loaded == payload


def test_get_cached_backtest_summary_uses_read_only_connection(tmp_path, monkeypatch):
    _reset_cache_state()
    monkeypatch.setattr(
        summary_cache,
        "_BACKTEST_SUMMARY_CACHE_DB_PATH",
        str(tmp_path / "runtime_cache.db"),
    )
    signature = (("seed", 8),)
    payload = {"vcp": {"count": 8}, "closing_bet": {"count": 8}}
    logger = logging.getLogger("test-backtest-read-only")

    summary_cache.save_cached_backtest_summary(
        signature=signature,
        payload=payload,
        logger=logger,
    )
    summary_cache.clear_backtest_summary_cache()

    read_only_flags: list[bool] = []
    original_connect = summary_cache.connect_sqlite

    def _traced_connect(*args, **kwargs):
        if "read_only" in kwargs:
            read_only_flags.append(bool(kwargs["read_only"]))
        return original_connect(*args, **kwargs)

    monkeypatch.setattr(summary_cache, "connect_sqlite", _traced_connect)

    loaded = summary_cache.get_cached_backtest_summary(
        signature=signature,
        logger=logger,
    )
    assert loaded == payload
    assert True in read_only_flags


def test_backtest_summary_cache_recovers_when_sqlite_table_missing(tmp_path, monkeypatch):
    _reset_cache_state()
    monkeypatch.setattr(
        summary_cache,
        "_BACKTEST_SUMMARY_CACHE_DB_PATH",
        str(tmp_path / "runtime_cache.db"),
    )
    logger = logging.getLogger("test-backtest-sqlite-recover")

    first_signature = (("seed", 1),)
    first_payload = {"vcp": {"count": 1}, "closing_bet": {"count": 1}}
    summary_cache.save_cached_backtest_summary(
        signature=first_signature,
        payload=first_payload,
        logger=logger,
    )

    db_path = tmp_path / "runtime_cache.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute("DROP TABLE backtest_summary_cache")
        conn.commit()

    second_signature = (("seed", 2),)
    second_payload = {"vcp": {"count": 2}, "closing_bet": {"count": 2}}
    summary_cache.save_cached_backtest_summary(
        signature=second_signature,
        payload=second_payload,
        logger=logger,
    )
    summary_cache.clear_backtest_summary_cache()

    loaded = summary_cache.get_cached_backtest_summary(
        signature=second_signature,
        logger=logger,
    )
    assert loaded == second_payload

    with sqlite3.connect(db_path) as conn:
        row_count = int(conn.execute("SELECT COUNT(*) FROM backtest_summary_cache").fetchone()[0])
    assert row_count >= 1


def test_backtest_summary_cache_skips_delete_when_rows_within_limit(tmp_path, monkeypatch):
    _reset_cache_state()
    db_path = tmp_path / "runtime_cache.db"
    monkeypatch.setattr(summary_cache, "_BACKTEST_SUMMARY_CACHE_DB_PATH", str(db_path))
    monkeypatch.setattr(summary_cache, "_BACKTEST_SUMMARY_SQLITE_MAX_ROWS", 16)

    traced_sql: list[str] = []
    original_connect = summary_cache.connect_sqlite

    def _traced_connect(*args, **kwargs):
        conn = original_connect(*args, **kwargs)
        conn.set_trace_callback(traced_sql.append)
        return conn

    monkeypatch.setattr(summary_cache, "connect_sqlite", _traced_connect)

    summary_cache.save_cached_backtest_summary(
        signature=(("seed", 99),),
        payload={"vcp": {"count": 99}, "closing_bet": {"count": 99}},
        logger=logging.getLogger("test-backtest-skip-delete"),
    )

    assert not any("DELETE FROM backtest_summary_cache" in sql for sql in traced_sql)
    assert not any("SELECT COUNT(*) FROM backtest_summary_cache" in sql for sql in traced_sql)


def test_backtest_summary_cache_repeated_signature_prunes_once(tmp_path, monkeypatch):
    _reset_cache_state()
    db_path = tmp_path / "runtime_cache.db"
    monkeypatch.setattr(summary_cache, "_BACKTEST_SUMMARY_CACHE_DB_PATH", str(db_path))
    monkeypatch.setattr(summary_cache, "_BACKTEST_SUMMARY_SQLITE_PRUNE_FORCE_INTERVAL", 10_000)

    prune_calls = {"count": 0}
    original_prune = summary_cache.prune_rows_by_updated_at_if_needed

    def _counted_prune(*args, **kwargs):
        prune_calls["count"] += 1
        return original_prune(*args, **kwargs)

    monkeypatch.setattr(summary_cache, "prune_rows_by_updated_at_if_needed", _counted_prune)

    logger = logging.getLogger("test-backtest-repeated-signature-prune-once")
    signature = (("seed", 77),)

    summary_cache.save_cached_backtest_summary(
        signature=signature,
        payload={"vcp": {"count": 1}, "closing_bet": {"count": 1}},
        logger=logger,
    )
    summary_cache.save_cached_backtest_summary(
        signature=signature,
        payload={"vcp": {"count": 2}, "closing_bet": {"count": 2}},
        logger=logger,
    )

    assert prune_calls["count"] == 1


def test_backtest_summary_cache_forces_prune_on_configured_interval(tmp_path, monkeypatch):
    _reset_cache_state()
    db_path = tmp_path / "runtime_cache.db"
    monkeypatch.setattr(summary_cache, "_BACKTEST_SUMMARY_CACHE_DB_PATH", str(db_path))
    monkeypatch.setattr(summary_cache, "_BACKTEST_SUMMARY_SQLITE_PRUNE_FORCE_INTERVAL", 2)

    prune_calls = {"count": 0}
    original_prune = summary_cache.prune_rows_by_updated_at_if_needed

    def _counted_prune(*args, **kwargs):
        prune_calls["count"] += 1
        return original_prune(*args, **kwargs)

    monkeypatch.setattr(summary_cache, "prune_rows_by_updated_at_if_needed", _counted_prune)

    logger = logging.getLogger("test-backtest-force-prune-interval")
    signature = (("seed", 88),)

    summary_cache.save_cached_backtest_summary(
        signature=signature,
        payload={"vcp": {"count": 1}, "closing_bet": {"count": 1}},
        logger=logger,
    )
    summary_cache.save_cached_backtest_summary(
        signature=signature,
        payload={"vcp": {"count": 2}, "closing_bet": {"count": 2}},
        logger=logger,
    )

    assert prune_calls["count"] == 2


def test_backtest_summary_sqlite_ready_uses_normalized_db_key(tmp_path, monkeypatch):
    _reset_cache_state()
    monkeypatch.chdir(tmp_path)

    original_connect = summary_cache.connect_sqlite
    connect_calls = {"count": 0}
    logger = logging.getLogger("test-backtest-ready-normalized")

    def _counted_connect(*args, **kwargs):
        connect_calls["count"] += 1
        return original_connect(*args, **kwargs)

    monkeypatch.setattr(summary_cache, "connect_sqlite", _counted_connect)

    relative_db_path = "./runtime_cache.db"
    absolute_db_path = str((tmp_path / "runtime_cache.db").resolve())

    monkeypatch.setattr(summary_cache, "_BACKTEST_SUMMARY_CACHE_DB_PATH", relative_db_path)
    assert summary_cache._ensure_backtest_summary_sqlite(logger) is True

    monkeypatch.setattr(summary_cache, "_BACKTEST_SUMMARY_CACHE_DB_PATH", absolute_db_path)
    assert summary_cache._ensure_backtest_summary_sqlite(logger) is True

    assert connect_calls["count"] == 1


def test_backtest_summary_sqlite_init_is_single_flight_under_concurrency(tmp_path, monkeypatch):
    _reset_cache_state()
    db_path = str(tmp_path / "runtime_cache.db")
    monkeypatch.setattr(summary_cache, "_BACKTEST_SUMMARY_CACHE_DB_PATH", db_path)
    logger = logging.getLogger("test-backtest-single-flight")

    monkeypatch.setattr(summary_cache, "sqlite_db_path_exists", lambda _path: True)

    entered_event = threading.Event()
    release_event = threading.Event()
    run_calls = {"count": 0}

    def _run_once(_operation, *, max_retries, retry_delay_seconds):
        run_calls["count"] += 1
        if run_calls["count"] == 1:
            entered_event.set()
            assert release_event.wait(timeout=2.0)
        return None

    monkeypatch.setattr(summary_cache, "run_sqlite_with_retry", _run_once)

    results: dict[str, bool] = {}

    def _worker(name: str) -> None:
        results[name] = bool(summary_cache._ensure_backtest_summary_sqlite(logger))

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


def test_backtest_summary_sqlite_waiter_retries_after_initializer_failure(tmp_path, monkeypatch):
    _reset_cache_state()
    db_path = str(tmp_path / "runtime_cache.db")
    monkeypatch.setattr(summary_cache, "_BACKTEST_SUMMARY_CACHE_DB_PATH", db_path)
    logger = logging.getLogger("test-backtest-waiter-retry")

    monkeypatch.setattr(summary_cache, "sqlite_db_path_exists", lambda _path: True)

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

    monkeypatch.setattr(summary_cache, "run_sqlite_with_retry", _fail_then_succeed)

    results: dict[str, bool] = {}

    def _worker(name: str) -> None:
        results[name] = bool(summary_cache._ensure_backtest_summary_sqlite(logger))

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
