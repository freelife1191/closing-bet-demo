#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Common Update Status Service 캐시/저장 회귀 테스트
"""

from __future__ import annotations

import json
from pathlib import Path
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
