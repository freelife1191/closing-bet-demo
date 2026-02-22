#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Common Update Status Service 캐시/저장 회귀 테스트
"""

from __future__ import annotations

import json
from pathlib import Path
import sqlite3
import threading
import time
import types

import services.common_update_status_service as status_service


def _logger():
    return types.SimpleNamespace(error=lambda *_a, **_k: None)


def test_load_update_status_reuses_signature_cache(monkeypatch, tmp_path: Path):
    status_service.clear_update_status_cache()
    status_path = tmp_path / "update_status.json"
    status_path.write_text(
        json.dumps({"isRunning": True, "startTime": "2026-02-22T10:00:00"}),
        encoding="utf-8",
    )

    json_load_calls = {"count": 0}
    original_json_load = status_service.json.load

    def _json_load_spy(handle):
        json_load_calls["count"] += 1
        return original_json_load(handle)

    monkeypatch.setattr(status_service.json, "load", _json_load_spy)

    first = status_service.load_update_status(update_status_file=str(status_path), logger=_logger())
    second = status_service.load_update_status(update_status_file=str(status_path), logger=_logger())

    assert first["isRunning"] is True
    assert second["isRunning"] is True
    assert json_load_calls["count"] == 1

    status_path.write_text(
        json.dumps({"isRunning": False, "startTime": "2026-02-22T11:00:00"}),
        encoding="utf-8",
    )
    third = status_service.load_update_status(update_status_file=str(status_path), logger=_logger())

    assert third["isRunning"] is False
    assert json_load_calls["count"] == 2


def test_update_status_signature_cache_is_bounded_lru(monkeypatch, tmp_path: Path):
    status_service.clear_update_status_cache()
    monkeypatch.setattr(status_service, "_UPDATE_STATUS_CACHE_MAX_ENTRIES", 2)

    status_paths = [tmp_path / f"update_status_{idx}.json" for idx in range(3)]
    for idx, status_path in enumerate(status_paths):
        status_path.write_text(
            json.dumps({"isRunning": bool(idx % 2), "startTime": f"2026-02-22T1{idx}:00:00"}),
            encoding="utf-8",
        )

    status_service.load_update_status(update_status_file=str(status_paths[0]), logger=_logger())
    status_service.load_update_status(update_status_file=str(status_paths[1]), logger=_logger())
    status_service.load_update_status(update_status_file=str(status_paths[0]), logger=_logger())
    status_service.load_update_status(update_status_file=str(status_paths[2]), logger=_logger())

    with status_service._UPDATE_STATUS_CACHE_LOCK:
        cached_keys = list(status_service._UPDATE_STATUS_CACHE.keys())

    assert len(cached_keys) == 2
    assert str(status_paths[0]) in cached_keys
    assert str(status_paths[2]) in cached_keys
    assert str(status_paths[1]) not in cached_keys


def test_save_update_status_populates_cache_for_followup_load(monkeypatch, tmp_path: Path):
    status_service.clear_update_status_cache()
    status_path = tmp_path / "update_status.json"

    status = {
        "isRunning": True,
        "startTime": "2026-02-22T12:00:00",
        "currentItem": "Daily Prices",
        "items": [],
    }
    status_service.save_update_status(
        status=status,
        update_status_file=str(status_path),
        logger=_logger(),
    )

    def _json_load_should_not_run(_handle):
        raise AssertionError("json.load should not be called when cache is valid")

    monkeypatch.setattr(status_service.json, "load", _json_load_should_not_run)
    loaded = status_service.load_update_status(update_status_file=str(status_path), logger=_logger())

    assert loaded["isRunning"] is True
    assert loaded["currentItem"] == "Daily Prices"


def test_save_update_status_dedupes_relative_and_absolute_file_path_keys(tmp_path: Path, monkeypatch):
    status_service.clear_update_status_cache()
    sqlite_cache_path = tmp_path / "runtime_cache.db"
    monkeypatch.setattr(status_service, "_UPDATE_STATUS_CACHE_DB_PATH", str(sqlite_cache_path))
    status_service._UPDATE_STATUS_DB_READY.clear()
    monkeypatch.chdir(tmp_path)

    absolute_status_path = str((tmp_path / "update_status_alias.json").resolve())
    relative_status_path = "update_status_alias.json"

    status_service.save_update_status(
        status={
            "isRunning": False,
            "startTime": "2026-02-22T12:01:00",
            "currentItem": None,
            "items": [],
        },
        update_status_file=absolute_status_path,
        logger=_logger(),
    )
    status_service.save_update_status(
        status={
            "isRunning": True,
            "startTime": "2026-02-22T12:02:00",
            "currentItem": "alias",
            "items": [],
        },
        update_status_file=relative_status_path,
        logger=_logger(),
    )

    normalized_key = status_service.normalize_sqlite_db_key(absolute_status_path)
    with sqlite3.connect(sqlite_cache_path) as conn:
        row_count = int(conn.execute("SELECT COUNT(*) FROM update_status_snapshot").fetchone()[0])
        stored_key_row = conn.execute(
            "SELECT file_path FROM update_status_snapshot LIMIT 1"
        ).fetchone()

    assert row_count == 1
    assert stored_key_row is not None
    assert str(stored_key_row[0]) == normalized_key


def test_load_update_status_reads_legacy_sqlite_snapshot_key(tmp_path: Path, monkeypatch):
    status_service.clear_update_status_cache()
    sqlite_cache_path = tmp_path / "runtime_cache.db"
    monkeypatch.setattr(status_service, "_UPDATE_STATUS_CACHE_DB_PATH", str(sqlite_cache_path))
    status_service._UPDATE_STATUS_DB_READY.clear()
    monkeypatch.chdir(tmp_path)

    legacy_relative_path = "update_status_legacy.json"
    absolute_status_path = str((tmp_path / legacy_relative_path).resolve())
    assert status_service._ensure_update_status_sqlite(_logger()) is True

    payload = {
        "isRunning": True,
        "startTime": "2026-02-22T12:30:00",
        "currentItem": "legacy",
        "items": [{"name": "legacy", "status": "running"}],
    }
    with sqlite3.connect(sqlite_cache_path) as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO update_status_snapshot (file_path, payload_json, updated_at)
            VALUES (?, ?, ?)
            """,
            (
                legacy_relative_path,
                json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
                "2026-02-22T12:30:00",
            ),
        )
        conn.commit()

    loaded = status_service.load_update_status(
        update_status_file=absolute_status_path,
        logger=_logger(),
    )
    assert loaded["isRunning"] is True
    assert loaded["currentItem"] == "legacy"


def test_load_update_status_legacy_lookup_uses_single_sqlite_connection(tmp_path: Path, monkeypatch):
    status_service.clear_update_status_cache()
    sqlite_cache_path = tmp_path / "runtime_cache.db"
    monkeypatch.setattr(status_service, "_UPDATE_STATUS_CACHE_DB_PATH", str(sqlite_cache_path))
    status_service._UPDATE_STATUS_DB_READY.clear()
    monkeypatch.chdir(tmp_path)

    legacy_relative_path = "update_status_legacy_single_conn.json"
    absolute_status_path = str((tmp_path / legacy_relative_path).resolve())
    assert status_service._ensure_update_status_sqlite(_logger()) is True

    payload = {
        "isRunning": True,
        "startTime": "2026-02-22T12:40:00",
        "currentItem": "legacy-single-conn",
        "items": [{"name": "legacy-single-conn", "status": "running"}],
    }
    with sqlite3.connect(sqlite_cache_path) as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO update_status_snapshot (file_path, payload_json, updated_at)
            VALUES (?, ?, ?)
            """,
            (
                legacy_relative_path,
                json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
                "2026-02-22T12:40:00",
            ),
        )
        conn.commit()

    status_service.clear_update_status_cache()

    connect_calls = {"count": 0}
    original_connect = status_service.connect_sqlite

    def _counted_connect(*args, **kwargs):
        if bool(kwargs.get("read_only", False)):
            connect_calls["count"] += 1
        return original_connect(*args, **kwargs)

    monkeypatch.setattr(status_service, "connect_sqlite", _counted_connect)

    loaded = status_service.load_update_status(
        update_status_file=absolute_status_path,
        logger=_logger(),
    )

    assert loaded["isRunning"] is True
    assert loaded["currentItem"] == "legacy-single-conn"
    assert connect_calls["count"] == 1


def test_load_update_status_falls_back_to_sqlite_snapshot_when_file_missing(tmp_path: Path, monkeypatch):
    status_service.clear_update_status_cache()
    sqlite_cache_path = tmp_path / "runtime_cache.db"
    monkeypatch.setattr(status_service, "_UPDATE_STATUS_CACHE_DB_PATH", str(sqlite_cache_path))
    status_service._UPDATE_STATUS_DB_READY.clear()

    status_path = tmp_path / "update_status.json"
    saved_status = {
        "isRunning": True,
        "startTime": "2026-02-22T13:00:00",
        "currentItem": "AI Analysis",
        "items": [{"name": "AI Analysis", "status": "running"}],
    }
    status_service.save_update_status(
        status=saved_status,
        update_status_file=str(status_path),
        logger=_logger(),
    )

    status_path.unlink()
    status_service.clear_update_status_cache()

    loaded = status_service.load_update_status(update_status_file=str(status_path), logger=_logger())
    assert loaded["isRunning"] is True
    assert loaded["currentItem"] == "AI Analysis"


def test_load_update_status_falls_back_to_sqlite_snapshot_when_json_corrupted(tmp_path: Path, monkeypatch):
    status_service.clear_update_status_cache()
    sqlite_cache_path = tmp_path / "runtime_cache.db"
    monkeypatch.setattr(status_service, "_UPDATE_STATUS_CACHE_DB_PATH", str(sqlite_cache_path))
    status_service._UPDATE_STATUS_DB_READY.clear()

    status_path = tmp_path / "update_status.json"
    saved_status = {
        "isRunning": False,
        "startTime": "2026-02-22T14:00:00",
        "currentItem": None,
        "items": [],
    }
    status_service.save_update_status(
        status=saved_status,
        update_status_file=str(status_path),
        logger=_logger(),
    )

    status_path.write_text("{broken json", encoding="utf-8")
    status_service.clear_update_status_cache()

    loaded = status_service.load_update_status(update_status_file=str(status_path), logger=_logger())
    assert loaded["startTime"] == "2026-02-22T14:00:00"
    assert loaded["isRunning"] is False


def test_load_update_status_uses_read_only_connection_for_sqlite_snapshot(tmp_path: Path, monkeypatch):
    status_service.clear_update_status_cache()
    sqlite_cache_path = tmp_path / "runtime_cache.db"
    monkeypatch.setattr(status_service, "_UPDATE_STATUS_CACHE_DB_PATH", str(sqlite_cache_path))
    status_service._UPDATE_STATUS_DB_READY.clear()

    status_path = tmp_path / "update_status.json"
    saved_status = {
        "isRunning": True,
        "startTime": "2026-02-22T14:30:00",
        "currentItem": "ReadOnly Check",
        "items": [],
    }
    status_service.save_update_status(
        status=saved_status,
        update_status_file=str(status_path),
        logger=_logger(),
    )
    status_path.unlink()
    status_service.clear_update_status_cache()

    read_only_flags: list[bool] = []
    original_connect = status_service.connect_sqlite

    def _traced_connect(*args, **kwargs):
        if "read_only" in kwargs:
            read_only_flags.append(bool(kwargs["read_only"]))
        return original_connect(*args, **kwargs)

    monkeypatch.setattr(status_service, "connect_sqlite", _traced_connect)

    loaded = status_service.load_update_status(update_status_file=str(status_path), logger=_logger())
    assert loaded["isRunning"] is True
    assert loaded["currentItem"] == "ReadOnly Check"
    assert True in read_only_flags


def test_save_update_status_handles_path_without_parent_dir(tmp_path: Path, monkeypatch):
    status_service.clear_update_status_cache()
    monkeypatch.chdir(tmp_path)

    status = {
        "isRunning": True,
        "startTime": "2026-02-22T15:00:00",
        "currentItem": "CSV Build",
        "items": [],
    }
    status_service.save_update_status(
        status=status,
        update_status_file="update_status.json",
        logger=_logger(),
    )

    loaded = status_service.load_update_status(update_status_file="update_status.json", logger=_logger())
    assert loaded["isRunning"] is True
    assert loaded["currentItem"] == "CSV Build"


def test_save_update_status_prunes_sqlite_rows(tmp_path: Path, monkeypatch):
    status_service.clear_update_status_cache()
    sqlite_cache_path = tmp_path / "runtime_cache.db"
    monkeypatch.setattr(status_service, "_UPDATE_STATUS_CACHE_DB_PATH", str(sqlite_cache_path))
    monkeypatch.setattr(status_service, "_UPDATE_STATUS_SQLITE_MAX_ROWS", 2)
    status_service._UPDATE_STATUS_DB_READY.clear()

    for idx in range(4):
        status_path = tmp_path / f"update_status_{idx}.json"
        status_service.save_update_status(
            status={
                "isRunning": bool(idx % 2),
                "startTime": f"2026-02-22T1{idx}:00:00",
                "currentItem": f"item-{idx}",
                "items": [],
            },
            update_status_file=str(status_path),
            logger=_logger(),
        )

    with sqlite3.connect(sqlite_cache_path) as conn:
        row_count = int(conn.execute("SELECT COUNT(*) FROM update_status_snapshot").fetchone()[0])
    assert row_count == 2


def test_save_update_status_recovers_when_sqlite_table_missing(tmp_path: Path, monkeypatch):
    status_service.clear_update_status_cache()
    sqlite_cache_path = tmp_path / "runtime_cache.db"
    monkeypatch.setattr(status_service, "_UPDATE_STATUS_CACHE_DB_PATH", str(sqlite_cache_path))
    status_service._UPDATE_STATUS_DB_READY.clear()

    status_path = tmp_path / "update_status.json"
    initial_status = {
        "isRunning": False,
        "startTime": "2026-02-22T16:00:00",
        "currentItem": None,
        "items": [],
    }
    status_service.save_update_status(
        status=initial_status,
        update_status_file=str(status_path),
        logger=_logger(),
    )

    with sqlite3.connect(sqlite_cache_path) as conn:
        conn.execute("DROP TABLE IF EXISTS update_status_snapshot")
        conn.commit()

    recovered_status = {
        "isRunning": True,
        "startTime": "2026-02-22T17:00:00",
        "currentItem": "recover",
        "items": [{"name": "recover", "status": "running"}],
    }
    status_service.save_update_status(
        status=recovered_status,
        update_status_file=str(status_path),
        logger=_logger(),
    )

    status_path.unlink()
    status_service.clear_update_status_cache()
    loaded = status_service.load_update_status(update_status_file=str(status_path), logger=_logger())

    assert loaded["isRunning"] is True
    assert loaded["currentItem"] == "recover"

    with sqlite3.connect(sqlite_cache_path) as conn:
        table_row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='update_status_snapshot'"
        ).fetchone()
        row_count = int(conn.execute("SELECT COUNT(*) FROM update_status_snapshot").fetchone()[0])

    assert table_row is not None
    assert row_count == 1


def test_update_status_sqlite_ready_cache_uses_normalized_db_key(tmp_path: Path, monkeypatch):
    status_service.clear_update_status_cache()
    status_service._UPDATE_STATUS_DB_READY.clear()
    monkeypatch.chdir(tmp_path)

    original_connect = status_service.connect_sqlite
    connect_calls = {"count": 0}

    def _counted_connect(*args, **kwargs):
        connect_calls["count"] += 1
        return original_connect(*args, **kwargs)

    monkeypatch.setattr(status_service, "connect_sqlite", _counted_connect)

    rel_db_path = "./runtime_cache.db"
    abs_db_path = str((tmp_path / "runtime_cache.db").resolve())

    monkeypatch.setattr(status_service, "_UPDATE_STATUS_CACHE_DB_PATH", rel_db_path)
    assert status_service._ensure_update_status_sqlite(_logger()) is True

    monkeypatch.setattr(status_service, "_UPDATE_STATUS_CACHE_DB_PATH", abs_db_path)
    assert status_service._ensure_update_status_sqlite(_logger()) is True

    assert connect_calls["count"] == 1


def test_update_status_sqlite_init_is_single_flight_under_concurrency(tmp_path: Path, monkeypatch):
    status_service.clear_update_status_cache()
    db_path = str(tmp_path / "runtime_cache.db")
    monkeypatch.setattr(status_service, "_UPDATE_STATUS_CACHE_DB_PATH", db_path)

    with status_service._UPDATE_STATUS_DB_INIT_CONDITION:
        status_service._UPDATE_STATUS_DB_READY.clear()
        status_service._UPDATE_STATUS_DB_INIT_IN_PROGRESS.clear()

    monkeypatch.setattr(status_service, "sqlite_db_path_exists", lambda _path: True)

    entered_event = threading.Event()
    release_event = threading.Event()
    run_calls = {"count": 0}

    def _run_once(_operation, *, max_retries, retry_delay_seconds):
        run_calls["count"] += 1
        if run_calls["count"] == 1:
            entered_event.set()
            assert release_event.wait(timeout=2.0)
        return None

    monkeypatch.setattr(status_service, "run_sqlite_with_retry", _run_once)

    results: dict[str, bool] = {}

    def _worker(name: str) -> None:
        results[name] = bool(status_service._ensure_update_status_sqlite(_logger()))

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


def test_update_status_sqlite_waiter_retries_after_initializer_failure(tmp_path: Path, monkeypatch):
    status_service.clear_update_status_cache()
    db_path = str(tmp_path / "runtime_cache.db")
    monkeypatch.setattr(status_service, "_UPDATE_STATUS_CACHE_DB_PATH", db_path)

    with status_service._UPDATE_STATUS_DB_INIT_CONDITION:
        status_service._UPDATE_STATUS_DB_READY.clear()
        status_service._UPDATE_STATUS_DB_INIT_IN_PROGRESS.clear()

    monkeypatch.setattr(status_service, "sqlite_db_path_exists", lambda _path: True)

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

    monkeypatch.setattr(status_service, "run_sqlite_with_retry", _fail_then_succeed)

    results: dict[str, bool] = {}

    def _worker(name: str) -> None:
        results[name] = bool(status_service._ensure_update_status_sqlite(_logger()))

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


def test_update_status_sqlite_schema_init_retries_on_transient_lock(tmp_path: Path, monkeypatch):
    status_service.clear_update_status_cache()
    status_service._UPDATE_STATUS_DB_READY.clear()

    sqlite_cache_path = tmp_path / "runtime_cache.db"
    monkeypatch.setattr(status_service, "_UPDATE_STATUS_CACHE_DB_PATH", str(sqlite_cache_path))

    original_connect = status_service.connect_sqlite
    failure_state = {"count": 0}

    def _flaky_connect(*args, **kwargs):
        if failure_state["count"] == 0:
            failure_state["count"] += 1
            raise sqlite3.OperationalError("database is locked")
        return original_connect(*args, **kwargs)

    monkeypatch.setattr(status_service, "connect_sqlite", _flaky_connect)

    assert status_service._ensure_update_status_sqlite(_logger()) is True
    assert failure_state["count"] == 1


def test_save_update_status_skips_delete_when_within_limit(tmp_path: Path, monkeypatch):
    status_service.clear_update_status_cache()
    sqlite_cache_path = tmp_path / "runtime_cache.db"
    monkeypatch.setattr(status_service, "_UPDATE_STATUS_CACHE_DB_PATH", str(sqlite_cache_path))
    monkeypatch.setattr(status_service, "_UPDATE_STATUS_SQLITE_MAX_ROWS", 16)
    status_service._UPDATE_STATUS_DB_READY.clear()

    traced_sql: list[str] = []
    original_connect = status_service.connect_sqlite

    def _traced_connect(*args, **kwargs):
        conn = original_connect(*args, **kwargs)
        conn.set_trace_callback(traced_sql.append)
        return conn

    monkeypatch.setattr(status_service, "connect_sqlite", _traced_connect)

    status_path = tmp_path / "update_status.json"
    status_service.save_update_status(
        status={
            "isRunning": False,
            "startTime": "2026-02-22T18:00:00",
            "currentItem": None,
            "items": [],
        },
        update_status_file=str(status_path),
        logger=_logger(),
    )

    assert not any("DELETE FROM update_status_snapshot" in sql for sql in traced_sql)


def test_save_update_status_runs_prune_only_once_for_repeated_same_file(tmp_path: Path, monkeypatch):
    status_service.clear_update_status_cache()
    sqlite_cache_path = tmp_path / "runtime_cache.db"
    monkeypatch.setattr(status_service, "_UPDATE_STATUS_CACHE_DB_PATH", str(sqlite_cache_path))
    status_service._UPDATE_STATUS_DB_READY.clear()

    prune_calls = {"count": 0}
    original_prune = status_service.prune_rows_by_updated_at_if_needed

    def _traced_prune(*args, **kwargs):
        prune_calls["count"] += 1
        return original_prune(*args, **kwargs)

    monkeypatch.setattr(status_service, "prune_rows_by_updated_at_if_needed", _traced_prune)

    status_path = tmp_path / "update_status.json"
    status_service.save_update_status(
        status={"isRunning": False, "startTime": "2026-02-22T18:10:00", "currentItem": None, "items": []},
        update_status_file=str(status_path),
        logger=_logger(),
    )
    status_service.save_update_status(
        status={"isRunning": True, "startTime": "2026-02-22T18:11:00", "currentItem": "step-1", "items": []},
        update_status_file=str(status_path),
        logger=_logger(),
    )

    assert prune_calls["count"] == 1


def test_save_update_status_runs_prune_for_each_new_file_path(tmp_path: Path, monkeypatch):
    status_service.clear_update_status_cache()
    sqlite_cache_path = tmp_path / "runtime_cache.db"
    monkeypatch.setattr(status_service, "_UPDATE_STATUS_CACHE_DB_PATH", str(sqlite_cache_path))
    status_service._UPDATE_STATUS_DB_READY.clear()

    prune_calls = {"count": 0}
    original_prune = status_service.prune_rows_by_updated_at_if_needed

    def _traced_prune(*args, **kwargs):
        prune_calls["count"] += 1
        return original_prune(*args, **kwargs)

    monkeypatch.setattr(status_service, "prune_rows_by_updated_at_if_needed", _traced_prune)

    first_status_path = tmp_path / "update_status_1.json"
    second_status_path = tmp_path / "update_status_2.json"

    status_service.save_update_status(
        status={"isRunning": False, "startTime": "2026-02-22T18:20:00", "currentItem": None, "items": []},
        update_status_file=str(first_status_path),
        logger=_logger(),
    )
    status_service.save_update_status(
        status={"isRunning": True, "startTime": "2026-02-22T18:21:00", "currentItem": "same", "items": []},
        update_status_file=str(first_status_path),
        logger=_logger(),
    )
    status_service.save_update_status(
        status={"isRunning": True, "startTime": "2026-02-22T18:22:00", "currentItem": "new", "items": []},
        update_status_file=str(second_status_path),
        logger=_logger(),
    )

    assert prune_calls["count"] == 2


def test_save_update_status_forces_periodic_prune_for_same_file(tmp_path: Path, monkeypatch):
    status_service.clear_update_status_cache()
    sqlite_cache_path = tmp_path / "runtime_cache.db"
    monkeypatch.setattr(status_service, "_UPDATE_STATUS_CACHE_DB_PATH", str(sqlite_cache_path))
    monkeypatch.setattr(status_service, "_UPDATE_STATUS_SQLITE_PRUNE_FORCE_INTERVAL", 2)
    status_service._UPDATE_STATUS_DB_READY.clear()

    prune_calls = {"count": 0}
    original_prune = status_service.prune_rows_by_updated_at_if_needed

    def _traced_prune(*args, **kwargs):
        prune_calls["count"] += 1
        return original_prune(*args, **kwargs)

    monkeypatch.setattr(status_service, "prune_rows_by_updated_at_if_needed", _traced_prune)

    status_path = tmp_path / "update_status_force.json"
    status_service.save_update_status(
        status={"isRunning": False, "startTime": "2026-02-22T18:30:00", "currentItem": None, "items": []},
        update_status_file=str(status_path),
        logger=_logger(),
    )
    status_service.save_update_status(
        status={"isRunning": True, "startTime": "2026-02-22T18:31:00", "currentItem": "force", "items": []},
        update_status_file=str(status_path),
        logger=_logger(),
    )

    assert prune_calls["count"] == 2
