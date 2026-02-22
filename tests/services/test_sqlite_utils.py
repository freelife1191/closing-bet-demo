#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SQLite 공통 유틸 회귀 테스트
"""

from __future__ import annotations

import sqlite3
import shutil
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


def test_build_sqlite_pragmas_includes_busy_timeout_and_foreign_keys():
    pragmas = sqlite_utils.build_sqlite_pragmas(
        busy_timeout_ms=3210,
        include_foreign_keys=True,
    )

    assert "PRAGMA journal_mode=WAL" in pragmas
    assert "PRAGMA synchronous=NORMAL" in pragmas
    assert "PRAGMA temp_store=MEMORY" in pragmas
    assert "PRAGMA cache_size=-8000" in pragmas
    assert "PRAGMA busy_timeout=3210" in pragmas
    assert "PRAGMA foreign_keys=ON" in pragmas


def test_connect_sqlite_forwards_cached_statements(monkeypatch):
    captured: dict[str, int] = {}

    class _FakeConnection:
        def execute(self, _sql):
            return None

        def close(self):
            return None

    def _fake_connect(*_args, **kwargs):
        captured["cached_statements"] = int(kwargs["cached_statements"])
        return _FakeConnection()

    monkeypatch.setattr(sqlite_utils.sqlite3, "connect", _fake_connect)
    conn = sqlite_utils.connect_sqlite("/tmp/irrelevant.db", cached_statements=512)
    conn.close()

    assert captured["cached_statements"] == 512


def test_connect_sqlite_enables_uri_mode_for_file_scheme(monkeypatch):
    captured: dict[str, bool] = {}

    class _FakeConnection:
        def execute(self, _sql):
            return None

        def close(self):
            return None

    def _fake_connect(*_args, **kwargs):
        captured["uri"] = bool(kwargs.get("uri"))
        return _FakeConnection()

    monkeypatch.setattr(sqlite_utils.sqlite3, "connect", _fake_connect)

    conn = sqlite_utils.connect_sqlite("file:test.db?mode=memory&cache=shared")
    conn.close()

    assert captured["uri"] is True


def test_connect_sqlite_disables_uri_mode_for_regular_path(monkeypatch):
    captured: dict[str, bool] = {}

    class _FakeConnection:
        def execute(self, _sql):
            return None

        def close(self):
            return None

    def _fake_connect(*_args, **kwargs):
        captured["uri"] = bool(kwargs.get("uri"))
        return _FakeConnection()

    monkeypatch.setattr(sqlite_utils.sqlite3, "connect", _fake_connect)

    conn = sqlite_utils.connect_sqlite("/tmp/normal.db")
    conn.close()

    assert captured["uri"] is False


def test_build_sqlite_pragmas_deduplicates_entries():
    pragmas = sqlite_utils.build_sqlite_pragmas(
        busy_timeout_ms=5000,
        include_foreign_keys=True,
        base_pragmas=("PRAGMA temp_store=MEMORY", "PRAGMA temp_store=MEMORY"),
        extra_pragmas=(
            "PRAGMA foreign_keys=ON",
            "PRAGMA cache_size=-4000",
            "PRAGMA cache_size=-4000",
        ),
    )

    assert pragmas.count("PRAGMA temp_store=MEMORY") == 1
    assert pragmas.count("PRAGMA foreign_keys=ON") == 1
    assert pragmas.count("PRAGMA cache_size=-4000") == 1
    assert "PRAGMA busy_timeout=5000" in pragmas


def test_connect_sqlite_creates_parent_directory_when_missing(tmp_path: Path):
    db_path = tmp_path / "nested" / "deep" / "sqlite_utils_create.db"
    assert not db_path.parent.exists()

    with sqlite_utils.connect_sqlite(str(db_path), pragmas=("PRAGMA busy_timeout=111",)) as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS t (id INTEGER PRIMARY KEY)")
        conn.commit()

    assert db_path.parent.exists()
    assert db_path.exists()


def test_connect_sqlite_parent_directory_creation_is_memoized(monkeypatch, tmp_path: Path):
    db_path = tmp_path / "nested" / "memoized" / "sqlite_utils_memo.db"

    with sqlite_utils._SQLITE_PARENT_DIRS_LOCK:
        sqlite_utils._SQLITE_PARENT_DIRS_READY.clear()

    original_makedirs = sqlite_utils.os.makedirs
    makedirs_calls = {"count": 0}

    def _counted_makedirs(path, exist_ok=True):
        makedirs_calls["count"] += 1
        return original_makedirs(path, exist_ok=exist_ok)

    monkeypatch.setattr(sqlite_utils.os, "makedirs", _counted_makedirs)

    sqlite_utils._ensure_sqlite_parent_dir(str(db_path))
    first_call_count = makedirs_calls["count"]
    sqlite_utils._ensure_sqlite_parent_dir(str(db_path))

    assert first_call_count >= 1
    assert makedirs_calls["count"] == first_call_count


def test_ensure_sqlite_parent_dir_recreates_directory_when_removed_after_memoization(tmp_path: Path):
    db_path = tmp_path / "nested" / "recreated" / "sqlite_utils_recreate.db"

    with sqlite_utils._SQLITE_PARENT_DIRS_LOCK:
        sqlite_utils._SQLITE_PARENT_DIRS_READY.clear()

    sqlite_utils._ensure_sqlite_parent_dir(str(db_path))
    assert db_path.parent.exists()

    shutil.rmtree(db_path.parent)
    assert not db_path.parent.exists()

    sqlite_utils._ensure_sqlite_parent_dir(str(db_path))
    assert db_path.parent.exists()


def test_prune_rows_by_updated_at_if_needed_skips_delete_when_within_limit(tmp_path: Path):
    db_path = tmp_path / "sqlite_utils_prune_skip.db"

    with sqlite_utils.connect_sqlite(str(db_path)) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS sample_cache (
                cache_key TEXT PRIMARY KEY,
                updated_at TEXT NOT NULL
            )
            """
        )
        cursor.executemany(
            """
            INSERT INTO sample_cache (cache_key, updated_at)
            VALUES (?, ?)
            """,
            [
                ("k1", "2026-02-20T10:00:00"),
                ("k2", "2026-02-20T11:00:00"),
            ],
        )
        did_prune = sqlite_utils.prune_rows_by_updated_at_if_needed(
            cursor,
            table_name="sample_cache",
            max_rows=2,
        )
        conn.commit()
        row_count = int(conn.execute("SELECT COUNT(*) FROM sample_cache").fetchone()[0])

    assert did_prune is False
    assert row_count == 2


def test_prune_rows_by_updated_at_if_needed_deletes_excess_rows(tmp_path: Path):
    db_path = tmp_path / "sqlite_utils_prune_delete.db"

    with sqlite_utils.connect_sqlite(str(db_path)) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS sample_cache (
                cache_key TEXT PRIMARY KEY,
                updated_at TEXT NOT NULL
            )
            """
        )
        cursor.executemany(
            """
            INSERT INTO sample_cache (cache_key, updated_at)
            VALUES (?, ?)
            """,
            [
                ("k1", "2026-02-20T10:00:00"),
                ("k2", "2026-02-20T11:00:00"),
                ("k3", "2026-02-20T12:00:00"),
                ("k4", "2026-02-20T13:00:00"),
                ("k5", "2026-02-20T14:00:00"),
            ],
        )
        did_prune = sqlite_utils.prune_rows_by_updated_at_if_needed(
            cursor,
            table_name="sample_cache",
            max_rows=2,
        )
        conn.commit()
        remaining = [
            row[0]
            for row in conn.execute(
                """
                SELECT cache_key
                FROM sample_cache
                ORDER BY updated_at DESC
                """
            ).fetchall()
        ]

    assert did_prune is True
    assert remaining == ["k5", "k4"]


def test_prune_rows_by_updated_at_if_needed_rejects_invalid_identifier(tmp_path: Path):
    db_path = tmp_path / "sqlite_utils_prune_identifier.db"

    with sqlite_utils.connect_sqlite(str(db_path)) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS sample_cache (
                cache_key TEXT PRIMARY KEY,
                updated_at TEXT NOT NULL
            )
            """
        )
        cursor.execute(
            """
            INSERT INTO sample_cache (cache_key, updated_at)
            VALUES (?, ?)
            """,
            ("k1", "2026-02-20T10:00:00"),
        )

        with pytest.raises(ValueError):
            sqlite_utils.prune_rows_by_updated_at_if_needed(
                cursor,
                table_name="sample_cache;",
                max_rows=1,
            )
