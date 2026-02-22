#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Engine UsageTracker SQLite 리팩토링 회귀 테스트
"""

from __future__ import annotations

from pathlib import Path
import sqlite3

import engine.services.usage_tracker as engine_usage_tracker


def _build_tracker_with_db(monkeypatch, tmp_path: Path, *, max_free_usage: int = 2):
    db_path = tmp_path / "engine_usage.db"
    monkeypatch.setattr(engine_usage_tracker, "DB_PATH", str(db_path))
    monkeypatch.setattr(engine_usage_tracker, "MAX_FREE_USAGE", max_free_usage)
    return engine_usage_tracker.UsageTracker(), db_path


def test_engine_usage_tracker_respects_limit(monkeypatch, tmp_path):
    tracker, _db_path = _build_tracker_with_db(monkeypatch, tmp_path, max_free_usage=2)

    assert tracker.check_and_increment("u@example.com") is True
    assert tracker.check_and_increment("u@example.com") is True
    assert tracker.check_and_increment("u@example.com") is False
    assert tracker.get_usage("u@example.com") == 2


def test_engine_usage_tracker_legacy_get_usaage_alias(monkeypatch, tmp_path):
    tracker, _db_path = _build_tracker_with_db(monkeypatch, tmp_path, max_free_usage=3)
    tracker.check_and_increment("u@example.com")

    assert tracker.get_usaage("u@example.com") == 1
    assert tracker.get_usage("u@example.com") == 1


def test_engine_usage_tracker_connection_applies_busy_timeout(monkeypatch, tmp_path):
    tracker, _db_path = _build_tracker_with_db(monkeypatch, tmp_path, max_free_usage=1)

    with tracker._connect() as conn:
        cursor = conn.cursor()
        cursor.execute("PRAGMA busy_timeout")
        timeout_ms = int(cursor.fetchone()[0])

    assert timeout_ms == tracker.SQLITE_BUSY_TIMEOUT_MS


def test_engine_usage_tracker_normalizes_email_key(monkeypatch, tmp_path):
    tracker, _db_path = _build_tracker_with_db(monkeypatch, tmp_path, max_free_usage=3)

    assert tracker.check_and_increment(" User@Example.com ") is True
    assert tracker.check_and_increment("user@example.com") is True
    assert tracker.get_usage("USER@EXAMPLE.COM") == 2


def test_engine_usage_tracker_default_db_path_points_to_project_data_dir():
    db_path = Path(engine_usage_tracker.DB_PATH)

    assert db_path.name == "usage.db"
    assert db_path.parent.name == "data"
    assert db_path.parent.parent.name != "engine"


def test_engine_usage_tracker_recovers_when_usage_table_missing(monkeypatch, tmp_path):
    tracker, db_path = _build_tracker_with_db(monkeypatch, tmp_path, max_free_usage=3)
    email = "recover@example.com"

    with sqlite3.connect(db_path) as conn:
        conn.execute("DROP TABLE IF EXISTS api_usage")
        conn.commit()

    assert tracker.check_and_increment(email) is True
    assert tracker.get_usage(email) == 1

    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='api_usage'"
        ).fetchone()
    assert row is not None


def test_engine_usage_tracker_retries_on_transient_sqlite_lock(monkeypatch, tmp_path):
    tracker, _db_path = _build_tracker_with_db(monkeypatch, tmp_path, max_free_usage=3)
    email = "retry@example.com"

    original_connect = tracker._connect
    failure_state = {"failed": False}

    def _flaky_connect():
        if not failure_state["failed"]:
            failure_state["failed"] = True
            raise sqlite3.OperationalError("database is locked")
        return original_connect()

    monkeypatch.setattr(tracker, "_connect", _flaky_connect)

    assert tracker.check_and_increment(email) is True
    assert tracker.get_usage(email) == 1
    assert failure_state["failed"] is True
