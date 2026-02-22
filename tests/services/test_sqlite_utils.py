#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SQLite 공통 유틸 회귀 테스트
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

import services.sqlite_utils as sqlite_utils


def test_connect_sqlite_applies_pragmas_and_allows_query(tmp_path: Path):
    db_path = tmp_path / "sqlite_utils_ok.db"

    with sqlite_utils.connect_sqlite(
        str(db_path),
        timeout_seconds=2,
        pragmas=("PRAGMA busy_timeout=1234",),
    ) as conn:
        cursor = conn.cursor()
        cursor.execute("PRAGMA busy_timeout")
        timeout_ms = int(cursor.fetchone()[0])

    assert timeout_ms == 1234


def test_connect_sqlite_closes_connection_when_pragma_fails(monkeypatch):
    class _FakeConnection:
        def __init__(self):
            self.closed = 0

        def execute(self, _sql):
            raise sqlite3.OperationalError("bad pragma")

        def close(self):
            self.closed += 1

    fake_conn = _FakeConnection()

    monkeypatch.setattr(sqlite_utils.sqlite3, "connect", lambda *_a, **_k: fake_conn)

    with pytest.raises(sqlite3.OperationalError):
        sqlite_utils.connect_sqlite(
            "/tmp/irrelevant.db",
            pragmas=("PRAGMA invalid_sql",),
        )

    assert fake_conn.closed == 1

