#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KR Market Cumulative Cache 단위 테스트
"""

from __future__ import annotations

import logging

import sqlite3
import threading
import time

from services import kr_market_cumulative_cache as cumulative_cache
from services.sqlite_utils import connect_sqlite


def _reset_cache_state() -> None:
    cumulative_cache.clear_cumulative_cache()
    with cumulative_cache._CUMULATIVE_SQLITE_CONDITION:
        cumulative_cache._CUMULATIVE_SQLITE_READY.clear()
        cumulative_cache._CUMULATIVE_SQLITE_INIT_IN_PROGRESS.clear()
    with cumulative_cache._CUMULATIVE_SQLITE_KNOWN_HASHES_LOCK:
        cumulative_cache._CUMULATIVE_SQLITE_KNOWN_HASHES.clear()
    with cumulative_cache._CUMULATIVE_SQLITE_SAVE_COUNTER_LOCK:
        cumulative_cache._CUMULATIVE_SQLITE_SAVE_COUNTER = 0


def test_save_cached_cumulative_payload_prunes_sqlite_rows(tmp_path, monkeypatch):
    _reset_cache_state()
    monkeypatch.setattr(
        cumulative_cache,
        "_CUMULATIVE_CACHE_DB_PATH",
        str(tmp_path / "runtime_cache.db"),
    )
    monkeypatch.setattr(cumulative_cache, "_CUMULATIVE_SQLITE_MAX_ROWS", 2)

    logger = logging.getLogger("test-cumulative-sqlite-prune")
    for idx in range(5):
        cumulative_cache.save_cached_cumulative_payload(
            signature=(("seed", idx),),
            payload={"kpi": {"count": idx}, "trades": [{"id": idx}]},
            logger=logger,
        )

    with connect_sqlite(str(tmp_path / "runtime_cache.db")) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM cumulative_performance_cache")
        row_count = int(cursor.fetchone()[0])

    assert row_count == 2


def test_get_cached_cumulative_payload_uses_sqlite_after_memory_clear(tmp_path, monkeypatch):
    _reset_cache_state()
    monkeypatch.setattr(
        cumulative_cache,
        "_CUMULATIVE_CACHE_DB_PATH",
        str(tmp_path / "runtime_cache.db"),
    )
    cumulative_cache._CUMULATIVE_SQLITE_READY.clear()

    signature = (("seed", 1),)
    expected = {"kpi": {"count": 1}, "trades": [{"id": "a"}]}
    logger = logging.getLogger("test-cumulative-sqlite-reuse")

    cumulative_cache.save_cached_cumulative_payload(
        signature=signature,
        payload=expected,
        logger=logger,
    )
    cumulative_cache.clear_cumulative_cache()

    loaded = cumulative_cache.get_cached_cumulative_payload(
        signature=signature,
        logger=logger,
    )
    assert loaded == expected


def test_get_cached_cumulative_payload_uses_read_only_connection(tmp_path, monkeypatch):
    _reset_cache_state()
    monkeypatch.setattr(
        cumulative_cache,
        "_CUMULATIVE_CACHE_DB_PATH",
        str(tmp_path / "runtime_cache.db"),
    )
    signature = (("seed", 3),)
    payload = {"kpi": {"count": 3}, "trades": [{"id": "r"}]}
    logger = logging.getLogger("test-cumulative-read-only")

    cumulative_cache.save_cached_cumulative_payload(
        signature=signature,
        payload=payload,
        logger=logger,
    )
    cumulative_cache.clear_cumulative_cache()

    read_only_flags: list[bool] = []
    original_connect = cumulative_cache.connect_sqlite

    def _traced_connect(*args, **kwargs):
        if "read_only" in kwargs:
            read_only_flags.append(bool(kwargs["read_only"]))
        return original_connect(*args, **kwargs)

    monkeypatch.setattr(cumulative_cache, "connect_sqlite", _traced_connect)

    loaded = cumulative_cache.get_cached_cumulative_payload(
        signature=signature,
        logger=logger,
    )
    assert loaded == payload
    assert True in read_only_flags


def test_save_cached_cumulative_payload_evicts_oldest_memory_entry(monkeypatch):
    _reset_cache_state()
    monkeypatch.setattr(cumulative_cache, "_CUMULATIVE_MEMORY_MAX_ENTRIES", 2)

    logger = logging.getLogger("test-cumulative-memory-lru")
    cumulative_cache.save_cached_cumulative_payload(
        signature=(("seed", 1),),
        payload={"kpi": {"count": 1}, "trades": [{"id": 1}]},
        logger=logger,
    )
    cumulative_cache.save_cached_cumulative_payload(
        signature=(("seed", 2),),
        payload={"kpi": {"count": 2}, "trades": [{"id": 2}]},
        logger=logger,
    )
    cumulative_cache.save_cached_cumulative_payload(
        signature=(("seed", 3),),
        payload={"kpi": {"count": 3}, "trades": [{"id": 3}]},
        logger=logger,
    )

    cache_keys = set(cumulative_cache._CUMULATIVE_CACHE.keys())
    assert cache_keys == {(("seed", 2),), (("seed", 3),)}


def test_save_cached_cumulative_payload_keeps_recently_used_entry_on_eviction(monkeypatch):
    _reset_cache_state()
    monkeypatch.setattr(cumulative_cache, "_CUMULATIVE_MEMORY_MAX_ENTRIES", 2)
    logger = logging.getLogger("test-cumulative-memory-lru-hit")

    cumulative_cache.save_cached_cumulative_payload(
        signature=(("seed", 1),),
        payload={"kpi": {"count": 1}, "trades": [{"id": 1}]},
        logger=logger,
    )
    cumulative_cache.save_cached_cumulative_payload(
        signature=(("seed", 2),),
        payload={"kpi": {"count": 2}, "trades": [{"id": 2}]},
        logger=logger,
    )
    cached = cumulative_cache.get_cached_cumulative_payload(
        signature=(("seed", 1),),
        logger=logger,
    )
    assert cached is not None
    cumulative_cache.save_cached_cumulative_payload(
        signature=(("seed", 3),),
        payload={"kpi": {"count": 3}, "trades": [{"id": 3}]},
        logger=logger,
    )

    cache_keys = set(cumulative_cache._CUMULATIVE_CACHE.keys())
    assert cache_keys == {(("seed", 1),), (("seed", 3),)}


def test_cumulative_cache_supports_sqlite_db_path_without_parent_dir(tmp_path, monkeypatch):
    _reset_cache_state()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cumulative_cache, "_CUMULATIVE_CACHE_DB_PATH", "runtime_cache.db")
    cumulative_cache._CUMULATIVE_SQLITE_READY.clear()

    signature = (("seed", 9),)
    payload = {"kpi": {"count": 9}, "trades": [{"id": "z"}]}
    logger = logging.getLogger("test-cumulative-sqlite-no-parent")

    cumulative_cache.save_cached_cumulative_payload(
        signature=signature,
        payload=payload,
        logger=logger,
    )
    cumulative_cache.clear_cumulative_cache()

    loaded = cumulative_cache.get_cached_cumulative_payload(
        signature=signature,
        logger=logger,
    )
    assert loaded == payload


def test_cumulative_cache_recovers_when_sqlite_table_missing(tmp_path, monkeypatch):
    _reset_cache_state()
    monkeypatch.setattr(
        cumulative_cache,
        "_CUMULATIVE_CACHE_DB_PATH",
        str(tmp_path / "runtime_cache.db"),
    )
    logger = logging.getLogger("test-cumulative-sqlite-recover")

    first_signature = (("seed", 1),)
    first_payload = {"kpi": {"count": 1}, "trades": [{"id": 1}]}
    cumulative_cache.save_cached_cumulative_payload(
        signature=first_signature,
        payload=first_payload,
        logger=logger,
    )

    db_path = tmp_path / "runtime_cache.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute("DROP TABLE cumulative_performance_cache")
        conn.commit()

    second_signature = (("seed", 2),)
    second_payload = {"kpi": {"count": 2}, "trades": [{"id": 2}]}
    cumulative_cache.save_cached_cumulative_payload(
        signature=second_signature,
        payload=second_payload,
        logger=logger,
    )
    cumulative_cache.clear_cumulative_cache()

    loaded = cumulative_cache.get_cached_cumulative_payload(
        signature=second_signature,
        logger=logger,
    )
    assert loaded == second_payload

    with sqlite3.connect(db_path) as conn:
        row_count = int(conn.execute("SELECT COUNT(*) FROM cumulative_performance_cache").fetchone()[0])
    assert row_count >= 1


def test_cumulative_cache_skips_delete_when_rows_within_limit(tmp_path, monkeypatch):
    _reset_cache_state()
    db_path = tmp_path / "runtime_cache.db"
    monkeypatch.setattr(cumulative_cache, "_CUMULATIVE_CACHE_DB_PATH", str(db_path))
    monkeypatch.setattr(cumulative_cache, "_CUMULATIVE_SQLITE_MAX_ROWS", 16)

    traced_sql: list[str] = []
    original_connect = cumulative_cache.connect_sqlite

    def _traced_connect(*args, **kwargs):
        conn = original_connect(*args, **kwargs)
        conn.set_trace_callback(traced_sql.append)
        return conn

    monkeypatch.setattr(cumulative_cache, "connect_sqlite", _traced_connect)

    cumulative_cache.save_cached_cumulative_payload(
        signature=(("seed", 42),),
        payload={"kpi": {"count": 42}, "trades": [{"id": 42}]},
        logger=logging.getLogger("test-cumulative-skip-delete"),
    )

    assert not any("DELETE FROM cumulative_performance_cache" in sql for sql in traced_sql)
    assert not any("SELECT COUNT(*) FROM cumulative_performance_cache" in sql for sql in traced_sql)


def test_cumulative_cache_repeated_signature_prunes_once(tmp_path, monkeypatch):
    _reset_cache_state()
    db_path = tmp_path / "runtime_cache.db"
    monkeypatch.setattr(cumulative_cache, "_CUMULATIVE_CACHE_DB_PATH", str(db_path))
    monkeypatch.setattr(cumulative_cache, "_CUMULATIVE_SQLITE_PRUNE_FORCE_INTERVAL", 10_000)

    prune_calls = {"count": 0}
    original_prune = cumulative_cache.prune_rows_by_updated_at_if_needed

    def _counted_prune(*args, **kwargs):
        prune_calls["count"] += 1
        return original_prune(*args, **kwargs)

    monkeypatch.setattr(cumulative_cache, "prune_rows_by_updated_at_if_needed", _counted_prune)

    logger = logging.getLogger("test-cumulative-repeated-signature-prune-once")
    signature = (("seed", 55),)
    cumulative_cache.save_cached_cumulative_payload(
        signature=signature,
        payload={"kpi": {"count": 1}, "trades": [{"id": 1}]},
        logger=logger,
    )
    cumulative_cache.save_cached_cumulative_payload(
        signature=signature,
        payload={"kpi": {"count": 2}, "trades": [{"id": 2}]},
        logger=logger,
    )

    assert prune_calls["count"] == 1


def test_cumulative_cache_forces_prune_on_configured_interval(tmp_path, monkeypatch):
    _reset_cache_state()
    db_path = tmp_path / "runtime_cache.db"
    monkeypatch.setattr(cumulative_cache, "_CUMULATIVE_CACHE_DB_PATH", str(db_path))
    monkeypatch.setattr(cumulative_cache, "_CUMULATIVE_SQLITE_PRUNE_FORCE_INTERVAL", 2)

    prune_calls = {"count": 0}
    original_prune = cumulative_cache.prune_rows_by_updated_at_if_needed

    def _counted_prune(*args, **kwargs):
        prune_calls["count"] += 1
        return original_prune(*args, **kwargs)

    monkeypatch.setattr(cumulative_cache, "prune_rows_by_updated_at_if_needed", _counted_prune)

    logger = logging.getLogger("test-cumulative-force-prune-interval")
    signature = (("seed", 66),)
    cumulative_cache.save_cached_cumulative_payload(
        signature=signature,
        payload={"kpi": {"count": 1}, "trades": [{"id": 1}]},
        logger=logger,
    )
    cumulative_cache.save_cached_cumulative_payload(
        signature=signature,
        payload={"kpi": {"count": 2}, "trades": [{"id": 2}]},
        logger=logger,
    )

    assert prune_calls["count"] == 2


def test_cumulative_cache_sqlite_ready_uses_normalized_db_key(tmp_path, monkeypatch):
    _reset_cache_state()
    monkeypatch.chdir(tmp_path)

    original_connect = cumulative_cache.connect_sqlite
    connect_calls = {"count": 0}
    logger = logging.getLogger("test-cumulative-ready-normalized")

    def _counted_connect(*args, **kwargs):
        connect_calls["count"] += 1
        return original_connect(*args, **kwargs)

    monkeypatch.setattr(cumulative_cache, "connect_sqlite", _counted_connect)

    relative_db_path = "./runtime_cache.db"
    absolute_db_path = str((tmp_path / "runtime_cache.db").resolve())

    monkeypatch.setattr(cumulative_cache, "_CUMULATIVE_CACHE_DB_PATH", relative_db_path)
    assert cumulative_cache._ensure_cumulative_sqlite(logger) is True

    monkeypatch.setattr(cumulative_cache, "_CUMULATIVE_CACHE_DB_PATH", absolute_db_path)
    assert cumulative_cache._ensure_cumulative_sqlite(logger) is True

    assert connect_calls["count"] == 1


def test_cumulative_cache_sqlite_init_is_single_flight_under_concurrency(tmp_path, monkeypatch):
    _reset_cache_state()
    db_path = str(tmp_path / "runtime_cache.db")
    monkeypatch.setattr(cumulative_cache, "_CUMULATIVE_CACHE_DB_PATH", db_path)
    logger = logging.getLogger("test-cumulative-single-flight")

    monkeypatch.setattr(cumulative_cache, "sqlite_db_path_exists", lambda _path: True)

    entered_event = threading.Event()
    release_event = threading.Event()
    run_calls = {"count": 0}

    def _run_once(_operation, *, max_retries, retry_delay_seconds):
        run_calls["count"] += 1
        if run_calls["count"] == 1:
            entered_event.set()
            assert release_event.wait(timeout=2.0)
        return None

    monkeypatch.setattr(cumulative_cache, "run_sqlite_with_retry", _run_once)

    results: dict[str, bool] = {}

    def _worker(name: str) -> None:
        results[name] = bool(cumulative_cache._ensure_cumulative_sqlite(logger))

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


def test_cumulative_cache_sqlite_waiter_retries_after_initializer_failure(tmp_path, monkeypatch):
    _reset_cache_state()
    db_path = str(tmp_path / "runtime_cache.db")
    monkeypatch.setattr(cumulative_cache, "_CUMULATIVE_CACHE_DB_PATH", db_path)
    logger = logging.getLogger("test-cumulative-waiter-retry")

    monkeypatch.setattr(cumulative_cache, "sqlite_db_path_exists", lambda _path: True)

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

    monkeypatch.setattr(cumulative_cache, "run_sqlite_with_retry", _fail_then_succeed)

    results: dict[str, bool] = {}

    def _worker(name: str) -> None:
        results[name] = bool(cumulative_cache._ensure_cumulative_sqlite(logger))

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
