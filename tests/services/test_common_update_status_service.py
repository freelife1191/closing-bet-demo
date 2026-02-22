#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Common Update Status Service 캐시/저장 회귀 테스트
"""

from __future__ import annotations

import json
from pathlib import Path
import sqlite3
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
