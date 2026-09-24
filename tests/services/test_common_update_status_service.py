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

import pytest

import services.common_update_status_service as status_service


def _logger():
    return types.SimpleNamespace(error=lambda *_a, **_k: None, info=lambda *_a, **_k: None)


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


def test_load_update_status_supports_deep_copy_false(monkeypatch, tmp_path: Path):
    status_service.clear_update_status_cache()
    status_path = tmp_path / "update_status.json"
    status_path.write_text(
        json.dumps({"isRunning": True, "items": []}),
        encoding="utf-8",
    )

    first = status_service.load_update_status(
        update_status_file=str(status_path),
        logger=_logger(),
        deep_copy=False,
    )
    second = status_service.load_update_status(
        update_status_file=str(status_path),
        logger=_logger(),
        deep_copy=False,
    )
    third = status_service.load_update_status(
        update_status_file=str(status_path),
        logger=_logger(),
        deep_copy=False,
    )
    fourth = status_service.load_update_status(
        update_status_file=str(status_path),
        logger=_logger(),
        deep_copy=True,
    )

    assert third is second
    assert fourth is not second
    assert first["isRunning"] is True
    assert fourth["isRunning"] is True


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


def test_load_update_status_uses_signature_matched_sqlite_snapshot_even_when_file_exists(
    tmp_path: Path,
    monkeypatch,
):
    status_service.clear_update_status_cache()
    sqlite_cache_path = tmp_path / "runtime_cache.db"
    monkeypatch.setattr(status_service, "_UPDATE_STATUS_CACHE_DB_PATH", str(sqlite_cache_path))
    status_service._UPDATE_STATUS_DB_READY.clear()

    status_path = tmp_path / "update_status.json"
    saved_status = {
        "isRunning": True,
        "startTime": "2026-02-22T13:10:00",
        "currentItem": "SQLite Hot Path",
        "items": [{"name": "SQLite Hot Path", "status": "running"}],
    }
    status_service.save_update_status(
        status=saved_status,
        update_status_file=str(status_path),
        logger=_logger(),
    )

    status_service.clear_update_status_cache()

    def _json_load_should_not_run(_handle):
        raise AssertionError("json.load should not run when signature-matched sqlite snapshot exists")

    monkeypatch.setattr(status_service.json, "load", _json_load_should_not_run)

    loaded = status_service.load_update_status(update_status_file=str(status_path), logger=_logger())
    assert loaded["isRunning"] is True
    assert loaded["currentItem"] == "SQLite Hot Path"


def test_load_update_status_signature_mismatch_reloads_file_and_warms_sqlite(
    tmp_path: Path,
    monkeypatch,
):
    status_service.clear_update_status_cache()
    sqlite_cache_path = tmp_path / "runtime_cache.db"
    monkeypatch.setattr(status_service, "_UPDATE_STATUS_CACHE_DB_PATH", str(sqlite_cache_path))
    status_service._UPDATE_STATUS_DB_READY.clear()

    status_path = tmp_path / "update_status.json"
    initial_status = {
        "isRunning": True,
        "startTime": "2026-02-22T13:20:00",
        "currentItem": "Old",
        "items": [{"name": "Old", "status": "running"}],
    }
    status_service.save_update_status(
        status=initial_status,
        update_status_file=str(status_path),
        logger=_logger(),
    )

    updated_status = {
        "isRunning": False,
        "startTime": "2026-02-22T13:21:00",
        "currentItem": "New",
        "items": [{"name": "New", "status": "done"}],
    }
    status_path.write_text(json.dumps(updated_status), encoding="utf-8")
    status_service.clear_update_status_cache()

    json_load_calls = {"count": 0}
    original_json_load = status_service.json.load

    def _json_load_spy(handle):
        json_load_calls["count"] += 1
        return original_json_load(handle)

    monkeypatch.setattr(status_service.json, "load", _json_load_spy)

    loaded = status_service.load_update_status(update_status_file=str(status_path), logger=_logger())
    assert loaded["isRunning"] is False
    assert loaded["currentItem"] == "New"
    assert json_load_calls["count"] == 1

    status_service.clear_update_status_cache()

    def _json_load_should_not_run(_handle):
        raise AssertionError("json.load should not run after sqlite warm-up")

    monkeypatch.setattr(status_service.json, "load", _json_load_should_not_run)
    warmed = status_service.load_update_status(update_status_file=str(status_path), logger=_logger())
    assert warmed["isRunning"] is False
    assert warmed["currentItem"] == "New"


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


def _slow_save_in_worker_a(monkeypatch, entered: threading.Event, release: threading.Event):
    original_save = status_service.save_update_status

    def _save(**kwargs):
        if threading.current_thread().name == "worker-a":
            entered.set()
            release.wait(2)
        original_save(**kwargs)

    monkeypatch.setattr(status_service, "save_update_status", _save)


def test_stop_from_other_worker_survives_item_update(monkeypatch, tmp_path: Path):
    # [INFRA-098] 워커마다 update_lock 이 따로다. 항목 저장 중에 끼어든 다른 워커의 중단이 덮이지 않아야 한다
    status_service.clear_update_status_cache()
    path = str(tmp_path / "update_status.json")
    status_service.save_update_status(
        status={"isRunning": True, "startTime": "run-1", "items": [{"name": "A", "status": "pending"}]},
        update_status_file=path,
        logger=_logger(),
    )
    entered, release = threading.Event(), threading.Event()
    _slow_save_in_worker_a(monkeypatch, entered, release)

    a = threading.Thread(
        name="worker-a",
        target=lambda: status_service.update_item_status(
            name="A", status_code="running", update_lock=threading.Lock(),
            update_status_file=path, logger=_logger(), start_time="run-1",
        ),
    )
    a.start()
    assert entered.wait(2)
    b = threading.Thread(
        target=lambda: status_service.stop_update(update_lock=threading.Lock(), update_status_file=path, logger=_logger()),
    )
    b.start()
    time.sleep(0.2)  # 잠금이 없으면 b 는 이 사이에 저장을 끝낸다
    release.set()
    a.join(2)
    b.join(2)
    assert not a.is_alive() and not b.is_alive()  # 잠금이 풀리지 않는 회귀면 여기서 멈추지 않고 실패한다

    final = json.loads(Path(path).read_text(encoding="utf-8"))
    assert final.get("stopRequested") is True
    assert final["isRunning"] is False


def test_finish_from_replaced_run_leaves_new_run(tmp_path: Path):
    # [INFRA-098] 옛 실행의 finish 는 잠금 안에서 startTime 을 보고 새 실행을 끝내지 않는다
    status_service.clear_update_status_cache()
    path = tmp_path / "update_status.json"
    status_service.save_update_status(
        status={"isRunning": True, "startTime": "run-2", "items": []}, update_status_file=str(path), logger=_logger(),
    )
    status_service.finish_update(
        update_lock=threading.Lock(), update_status_file=str(path), logger=_logger(), start_time="run-1",
    )
    assert json.loads(path.read_text(encoding="utf-8"))["isRunning"] is True
    status_service.finish_update(
        update_lock=threading.Lock(), update_status_file=str(path), logger=_logger(), start_time="run-2",
    )
    assert json.loads(path.read_text(encoding="utf-8"))["isRunning"] is False
    # 수동 finish(/system/finish-update)는 start_time 없이 부르며 파일의 startTime 과 무관하게 끝낸다
    status_service.save_update_status(
        status={"isRunning": True, "startTime": "run-3", "items": []}, update_status_file=str(path), logger=_logger(),
    )
    status_service.finish_update(update_lock=threading.Lock(), update_status_file=str(path), logger=_logger())
    assert json.loads(path.read_text(encoding="utf-8"))["isRunning"] is False


def test_stop_without_status_file_keeps_run_identity_from_snapshot(tmp_path: Path):
    # [INFRA-098] JSON 파일이 없어도 SQLite 스냅샷의 startTime 을 이어 써야 실행 중인 워커의 감시가 중단을 알아본다
    status_service.clear_update_status_cache()
    path = tmp_path / "update_status.json"
    status_service.save_update_status(
        status={"isRunning": True, "startTime": "run-1", "items": [{"name": "A", "status": "running"}]},
        update_status_file=str(path),
        logger=_logger(),
    )
    path.unlink()
    status_service.stop_update(update_lock=threading.Lock(), update_status_file=str(path), logger=_logger())
    final = json.loads(path.read_text(encoding="utf-8"))
    assert (final["startTime"], final["stopRequested"], final["items"]) == (
        "run-1",
        True,
        [{"name": "A", "status": "error"}],
    )


@pytest.mark.parametrize(
    ("mutate", "expected"),
    [
        (
            lambda path, log: status_service.finish_update(
                update_lock=threading.Lock(), update_status_file=path, logger=log, start_time="run-1",
            ),
            lambda final: final["isRunning"] is False,
        ),
        (
            lambda path, log: status_service.update_item_status(
                name="A", status_code="done", update_lock=threading.Lock(), update_status_file=path, logger=log,
                start_time="run-1",
            ),
            lambda final: final["items"] == [{"name": "A", "status": "done"}],
        ),
        (
            lambda path, log: status_service.stop_update(
                update_lock=threading.Lock(), update_status_file=path, logger=log,
            ),
            lambda final: final["items"] == [{"name": "A", "status": "error"}],
        ),
    ],
    ids=["finish", "item", "stop"],
)
def test_mutation_reads_file_not_stale_signature_cache(tmp_path: Path, mutate, expected):
    # [INFRA-098] 시그니처가 같은 옛 캐시(run-0, 항목 없음)가 있어도 상태 변경은 파일의 현재 값에서 출발한다
    status_service.clear_update_status_cache()
    path = tmp_path / "update_status.json"
    status_service.save_update_status(
        status={"isRunning": True, "startTime": "run-1", "stopRequested": False, "items": [{"name": "A", "status": "running"}]},
        update_status_file=str(path),
        logger=_logger(),
    )
    signature = status_service._status_file_signature(str(path))
    stale = {"isRunning": True, "startTime": "run-0", "stopRequested": False, "items": []}
    with status_service._UPDATE_STATUS_CACHE_LOCK:
        status_service._UPDATE_STATUS_CACHE[status_service._normalize_update_status_file_key(str(path))] = (
            signature,
            stale,
        )
    mutate(str(path), _logger())
    final = json.loads(path.read_text(encoding="utf-8"))
    assert final["startTime"] == "run-1"
    assert expected(final)


def test_finish_does_not_revert_start_from_other_worker(monkeypatch, tmp_path: Path):
    # [INFRA-098] 옛 실행의 finish 가 읽고 쓰는 사이에 다른 워커가 새 실행을 시작해도 그 새 실행이 남는다
    status_service.clear_update_status_cache()
    path = tmp_path / "update_status.json"
    status_service.save_update_status(
        status={"isRunning": True, "startTime": "run-1", "items": []}, update_status_file=str(path), logger=_logger(),
    )
    entered, release = threading.Event(), threading.Event()
    _slow_save_in_worker_a(monkeypatch, entered, release)

    a = threading.Thread(
        name="worker-a",
        target=lambda: status_service.finish_update(
            update_lock=threading.Lock(), update_status_file=str(path), logger=_logger(), start_time="run-1",
        ),
    )
    a.start()
    assert entered.wait(2)
    b = threading.Thread(
        target=lambda: status_service.start_update(
            items_list=["A"], update_lock=threading.Lock(), update_status_file=str(path),
            shared_state=types.SimpleNamespace(), logger=_logger(),
        ),
    )
    b.start()
    time.sleep(0.2)  # 잠금이 없으면 b 는 이 사이에 새 실행을 기록한다
    release.set()
    a.join(2)
    b.join(2)
    assert not a.is_alive() and not b.is_alive()  # 잠금이 풀리지 않는 회귀면 여기서 멈추지 않고 실패한다

    final = json.loads(path.read_text(encoding="utf-8"))
    assert final["startTime"] != "run-1"
    assert final["isRunning"] is True


def test_mutation_proceeds_when_lock_file_unavailable(tmp_path: Path):
    # [INFRA-098] 잠금 파일을 열 수 없어도(권한 등) 중단 요청은 종전처럼 저장된다. 예외를 내면 isRunning 이 고착된다
    status_service.clear_update_status_cache()
    path = tmp_path / "update_status.json"
    status_service.save_update_status(
        status={"isRunning": True, "startTime": "run-1", "items": []}, update_status_file=str(path), logger=_logger(),
    )
    (tmp_path / "update_status.json.lock").mkdir()  # 열기가 OSError 가 되게 한다
    status_service.stop_update(update_lock=threading.Lock(), update_status_file=str(path), logger=_logger())
    assert json.loads(path.read_text(encoding="utf-8"))["stopRequested"] is True
