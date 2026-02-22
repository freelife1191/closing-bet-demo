#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Engine UsageTracker SQLite 리팩토링 회귀 테스트
"""

from __future__ import annotations

from pathlib import Path
import sqlite3
import threading
import time

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


def test_engine_usage_tracker_get_usage_uses_read_only_connection(monkeypatch, tmp_path):
    tracker, _db_path = _build_tracker_with_db(monkeypatch, tmp_path, max_free_usage=3)
    email = "readonly@example.com"
    assert tracker.check_and_increment(email) is True

    read_only_flags: list[bool] = []
    original_connect = engine_usage_tracker.connect_sqlite

    def _traced_connect(*args, **kwargs):
        if "read_only" in kwargs:
            read_only_flags.append(bool(kwargs["read_only"]))
        return original_connect(*args, **kwargs)

    monkeypatch.setattr(engine_usage_tracker, "connect_sqlite", _traced_connect)

    assert tracker.get_usage(email) == 1
    assert True in read_only_flags


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


def test_engine_usage_tracker_init_db_is_single_flight_under_concurrency(monkeypatch, tmp_path):
    tracker, _db_path = _build_tracker_with_db(monkeypatch, tmp_path, max_free_usage=3)

    with tracker._db_init_condition:
        tracker._db_ready = False
        tracker._db_init_in_progress = False

    monkeypatch.setattr(engine_usage_tracker, "sqlite_db_path_exists", lambda _path: True)

    entered_event = threading.Event()
    release_event = threading.Event()
    run_calls = {"count": 0}

    def _run_once(_operation, *, max_retries, retry_delay_seconds):
        run_calls["count"] += 1
        if run_calls["count"] == 1:
            entered_event.set()
            assert release_event.wait(timeout=2.0)
        return None

    monkeypatch.setattr(engine_usage_tracker, "run_sqlite_with_retry", _run_once)

    results: dict[str, bool] = {}

    def _worker(name: str) -> None:
        results[name] = bool(tracker._init_db())

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


def test_engine_usage_tracker_init_db_waiter_retries_after_initializer_failure(monkeypatch, tmp_path):
    tracker, _db_path = _build_tracker_with_db(monkeypatch, tmp_path, max_free_usage=3)

    with tracker._db_init_condition:
        tracker._db_ready = False
        tracker._db_init_in_progress = False

    monkeypatch.setattr(engine_usage_tracker, "sqlite_db_path_exists", lambda _path: True)

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

    monkeypatch.setattr(engine_usage_tracker, "run_sqlite_with_retry", _fail_then_succeed)

    results: dict[str, bool] = {}

    def _worker(name: str) -> None:
        results[name] = bool(tracker._init_db())

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
