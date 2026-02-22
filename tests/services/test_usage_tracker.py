#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
UsageTracker SQLite 최적화 회귀 테스트
"""

from __future__ import annotations

import sqlite3
import threading
import time
import uuid
from pathlib import Path

import services.usage_tracker as usage_tracker_module
from services.usage_tracker import UsageTracker


def _build_tracker(tmp_path: Path, *, limit: int = 2) -> UsageTracker:
    db_path = tmp_path / f"usage_test_{uuid.uuid4().hex}.db"
    return UsageTracker(db_path=str(db_path), limit=limit)


def test_check_and_increment_respects_limit(tmp_path):
    tracker = _build_tracker(tmp_path, limit=2)
    email = "user@example.com"

    assert tracker.check_and_increment(email) is True
    assert tracker.check_and_increment(email) is True
    assert tracker.check_and_increment(email) is False
    assert tracker.get_usage(email) == 2


def test_get_usage_returns_zero_for_unknown_email(tmp_path):
    tracker = _build_tracker(tmp_path, limit=3)
    assert tracker.get_usage("missing@example.com") == 0


def test_usage_tracker_creates_last_used_index(tmp_path):
    tracker = _build_tracker(tmp_path, limit=3)

    with sqlite3.connect(tracker.db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'index'
              AND name = 'idx_usage_log_last_used'
            """
        )
        row = cursor.fetchone()

    assert row is not None
    assert row[0] == "idx_usage_log_last_used"


def test_usage_tracker_connection_applies_busy_timeout(tmp_path):
    tracker = _build_tracker(tmp_path, limit=1)

    with tracker._connect() as conn:
        cursor = conn.cursor()
        cursor.execute("PRAGMA busy_timeout")
        timeout_ms = int(cursor.fetchone()[0])

    assert timeout_ms == tracker.SQLITE_BUSY_TIMEOUT_MS


def test_usage_tracker_connection_closes_after_context_exit(tmp_path):
    tracker = _build_tracker(tmp_path, limit=1)
    conn = tracker._connect()

    with conn as active_conn:
        active_conn.execute("SELECT 1")

    try:
        conn.execute("SELECT 1")
        assert False, "connection should be closed after context exit"
    except sqlite3.ProgrammingError:
        pass


def test_usage_tracker_get_usage_uses_read_only_connection(tmp_path, monkeypatch):
    tracker = _build_tracker(tmp_path, limit=3)
    email = "readonly@example.com"
    assert tracker.check_and_increment(email) is True

    read_only_flags: list[bool] = []
    original_connect = usage_tracker_module.connect_sqlite

    def _traced_connect(*args, **kwargs):
        if "read_only" in kwargs:
            read_only_flags.append(bool(kwargs["read_only"]))
        return original_connect(*args, **kwargs)

    monkeypatch.setattr(usage_tracker_module, "connect_sqlite", _traced_connect)

    assert tracker.get_usage(email) == 1
    assert True in read_only_flags


def test_usage_tracker_normalizes_email_key(tmp_path):
    tracker = _build_tracker(tmp_path, limit=3)

    assert tracker.check_and_increment(" User@Example.com ") is True
    assert tracker.check_and_increment("user@example.com") is True
    assert tracker.get_usage("USER@EXAMPLE.COM") == 2


def test_usage_tracker_recovers_when_usage_table_missing(tmp_path):
    tracker = _build_tracker(tmp_path, limit=3)
    email = "recover@example.com"

    with sqlite3.connect(tracker.db_path) as conn:
        conn.execute("DROP TABLE IF EXISTS usage_log")
        conn.commit()

    assert tracker.check_and_increment(email) is True
    assert tracker.get_usage(email) == 1

    with sqlite3.connect(tracker.db_path) as conn:
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='usage_log'"
        ).fetchone()
    assert row is not None


def test_usage_tracker_retries_on_transient_sqlite_lock(monkeypatch, tmp_path):
    tracker = _build_tracker(tmp_path, limit=3)
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


def test_usage_tracker_init_db_is_single_flight_under_concurrency(monkeypatch, tmp_path):
    tracker = _build_tracker(tmp_path, limit=3)

    with tracker._db_init_condition:
        tracker._db_ready = False
        tracker._db_init_in_progress = False

    monkeypatch.setattr(usage_tracker_module, "sqlite_db_path_exists", lambda _path: True)

    entered_event = threading.Event()
    release_event = threading.Event()
    run_calls = {"count": 0}

    def _run_once(_operation, *, max_retries, retry_delay_seconds):
        run_calls["count"] += 1
        if run_calls["count"] == 1:
            entered_event.set()
            assert release_event.wait(timeout=2.0)
        return None

    monkeypatch.setattr(usage_tracker_module, "run_sqlite_with_retry", _run_once)

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


def test_usage_tracker_init_db_waiter_retries_after_initializer_failure(monkeypatch, tmp_path):
    tracker = _build_tracker(tmp_path, limit=3)

    with tracker._db_init_condition:
        tracker._db_ready = False
        tracker._db_init_in_progress = False

    monkeypatch.setattr(usage_tracker_module, "sqlite_db_path_exists", lambda _path: True)

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

    monkeypatch.setattr(usage_tracker_module, "run_sqlite_with_retry", _fail_then_succeed)

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
