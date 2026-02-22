#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
UsageTracker SQLite 최적화 회귀 테스트
"""

from __future__ import annotations

import sqlite3
import uuid
from pathlib import Path

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


def test_usage_tracker_normalizes_email_key(tmp_path):
    tracker = _build_tracker(tmp_path, limit=3)

    assert tracker.check_and_increment(" User@Example.com ") is True
    assert tracker.check_and_increment("user@example.com") is True
    assert tracker.get_usage("USER@EXAMPLE.COM") == 2
