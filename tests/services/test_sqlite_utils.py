#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SQLite 공통 유틸 회귀 테스트
"""

from __future__ import annotations

import os
import sqlite3
import shutil
from pathlib import Path
from urllib.parse import parse_qsl, urlparse

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


def test_build_sqlite_in_placeholders_returns_expected_sequence():
    placeholders = sqlite_utils.build_sqlite_in_placeholders(("a", "b", "c"))
    assert placeholders == "?,?,?"


def test_build_sqlite_in_placeholders_raises_for_empty_input():
    with pytest.raises(ValueError):
        sqlite_utils.build_sqlite_in_placeholders(())


def test_build_sqlite_order_case_sql_returns_expected_clause():
    order_case_sql = sqlite_utils.build_sqlite_order_case_sql(
        column_name="cache_key",
        lookup_keys=("first", "second"),
    )
    assert order_case_sql == "CASE cache_key WHEN ? THEN 0 WHEN ? THEN 1 ELSE 2 END"


def test_build_sqlite_order_case_sql_raises_for_invalid_column_name():
    with pytest.raises(ValueError):
        sqlite_utils.build_sqlite_order_case_sql(
            column_name="cache key",
            lookup_keys=("first",),
        )


def test_build_sqlite_order_case_sql_raises_for_empty_lookup_keys():
    with pytest.raises(ValueError):
        sqlite_utils.build_sqlite_order_case_sql(
            column_name="cache_key",
            lookup_keys=(),
        )


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


def test_connect_sqlite_retries_transient_connect_error(monkeypatch):
    calls = {"count": 0}
    sleep_calls: list[float] = []

    class _FakeConnection:
        def execute(self, _sql):
            return None

        def close(self):
            return None

    def _fake_connect(*_args, **_kwargs):
        calls["count"] += 1
        if calls["count"] == 1:
            raise sqlite3.OperationalError("database is locked")
        return _FakeConnection()

    monkeypatch.setattr(sqlite_utils.sqlite3, "connect", _fake_connect)
    monkeypatch.setattr(sqlite_utils.time, "sleep", lambda delay: sleep_calls.append(float(delay)))

    conn = sqlite_utils.connect_sqlite("/tmp/retry_connect.db")
    conn.close()

    assert calls["count"] == 2
    assert sleep_calls == [0.03]


def test_connect_sqlite_retries_transient_pragma_error_and_closes_failed_connection(monkeypatch):
    calls = {"count": 0}
    closed_counts: list[int] = []

    class _FakeConnection:
        def __init__(self, call_index: int):
            self.call_index = call_index
            self.closed = 0

        def execute(self, _sql):
            if self.call_index == 1:
                raise sqlite3.OperationalError("database is locked")
            return None

        def close(self):
            self.closed += 1
            closed_counts.append(self.call_index)

    def _fake_connect(*_args, **_kwargs):
        calls["count"] += 1
        return _FakeConnection(calls["count"])

    monkeypatch.setattr(sqlite_utils.sqlite3, "connect", _fake_connect)

    conn = sqlite_utils.connect_sqlite(
        "/tmp/retry_pragma.db",
        pragmas=("PRAGMA busy_timeout=1000",),
    )
    conn.close()

    assert calls["count"] == 2
    assert closed_counts.count(1) == 1


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


def test_connect_sqlite_enables_read_only_uri_mode_for_regular_path(monkeypatch):
    captured: dict[str, object] = {}

    class _FakeConnection:
        def execute(self, _sql):
            return None

        def close(self):
            return None

    def _fake_connect(path, *_args, **kwargs):
        captured["path"] = str(path)
        captured["uri"] = bool(kwargs.get("uri"))
        return _FakeConnection()

    monkeypatch.setattr(sqlite_utils.sqlite3, "connect", _fake_connect)

    conn = sqlite_utils.connect_sqlite(
        "/tmp/sqlite_utils_read_only.db",
        ensure_parent_dir=False,
        read_only=True,
        pragmas=("PRAGMA busy_timeout=900",),
    )
    conn.close()

    assert captured["uri"] is True
    assert str(captured["path"]).startswith("file:")
    assert "mode=ro" in str(captured["path"])


def test_connect_sqlite_read_only_preserves_relative_file_uri_path(monkeypatch):
    captured: dict[str, object] = {}

    class _FakeConnection:
        def execute(self, _sql):
            return None

        def close(self):
            return None

    def _fake_connect(path, *_args, **kwargs):
        captured["path"] = str(path)
        captured["uri"] = bool(kwargs.get("uri"))
        return _FakeConnection()

    monkeypatch.setattr(sqlite_utils.sqlite3, "connect", _fake_connect)

    conn = sqlite_utils.connect_sqlite(
        "file:runtime_cache.db?cache=shared",
        ensure_parent_dir=False,
        read_only=True,
    )
    conn.close()

    assert captured["uri"] is True
    assert str(captured["path"]).startswith("file:runtime_cache.db?")
    assert "mode=ro" in str(captured["path"])
    assert not str(captured["path"]).startswith("file:///runtime_cache.db")


def test_connect_sqlite_read_only_preserves_file_uri_fragment(monkeypatch):
    captured: dict[str, object] = {}

    class _FakeConnection:
        def execute(self, _sql):
            return None

        def close(self):
            return None

    def _fake_connect(path, *_args, **kwargs):
        captured["path"] = str(path)
        captured["uri"] = bool(kwargs.get("uri"))
        return _FakeConnection()

    monkeypatch.setattr(sqlite_utils.sqlite3, "connect", _fake_connect)

    conn = sqlite_utils.connect_sqlite(
        "file:runtime_cache.db?cache=shared#readonly-anchor",
        ensure_parent_dir=False,
        read_only=True,
    )
    conn.close()

    assert captured["uri"] is True
    assert str(captured["path"]).startswith("file:runtime_cache.db?")
    assert "mode=ro" in str(captured["path"])
    assert str(captured["path"]).endswith("#readonly-anchor")


def test_connect_sqlite_read_only_preserves_duplicate_query_pairs(monkeypatch):
    captured: dict[str, object] = {}

    class _FakeConnection:
        def execute(self, _sql):
            return None

        def close(self):
            return None

    def _fake_connect(path, *_args, **kwargs):
        captured["path"] = str(path)
        captured["uri"] = bool(kwargs.get("uri"))
        return _FakeConnection()

    monkeypatch.setattr(sqlite_utils.sqlite3, "connect", _fake_connect)

    conn = sqlite_utils.connect_sqlite(
        "file:runtime_cache.db?cache=shared&cache=private&x=1",
        ensure_parent_dir=False,
        read_only=True,
    )
    conn.close()

    parsed = urlparse(str(captured["path"]))
    query_pairs = parse_qsl(parsed.query, keep_blank_values=True)

    assert captured["uri"] is True
    assert query_pairs == [
        ("cache", "shared"),
        ("cache", "private"),
        ("x", "1"),
        ("mode", "ro"),
    ]


def test_connect_sqlite_read_only_replaces_existing_mode_parameter_once(monkeypatch):
    captured: dict[str, object] = {}

    class _FakeConnection:
        def execute(self, _sql):
            return None

        def close(self):
            return None

    def _fake_connect(path, *_args, **kwargs):
        captured["path"] = str(path)
        captured["uri"] = bool(kwargs.get("uri"))
        return _FakeConnection()

    monkeypatch.setattr(sqlite_utils.sqlite3, "connect", _fake_connect)

    conn = sqlite_utils.connect_sqlite(
        "file:runtime_cache.db?mode=rwc&cache=shared&mode=rw",
        ensure_parent_dir=False,
        read_only=True,
    )
    conn.close()

    parsed = urlparse(str(captured["path"]))
    query_pairs = parse_qsl(parsed.query, keep_blank_values=True)
    mode_values = [value for key, value in query_pairs if key == "mode"]

    assert captured["uri"] is True
    assert mode_values == ["ro"]
    assert ("cache", "shared") in query_pairs


def test_extract_sqlite_filesystem_path_from_uri_treats_any_memory_mode_as_memory():
    db_uri = "file:runtime_cache.db?mode=ro&cache=shared&mode=memory"

    assert sqlite_utils._extract_sqlite_filesystem_path_from_uri(db_uri) is None
    assert sqlite_utils._resolve_sqlite_filesystem_path(db_uri) is None


def test_connect_sqlite_read_only_filters_write_pragmas(monkeypatch):
    executed_sqls: list[str] = []

    class _FakeConnection:
        def execute(self, sql):
            executed_sqls.append(str(sql).strip())
            return None

        def close(self):
            return None

    monkeypatch.setattr(
        sqlite_utils.sqlite3,
        "connect",
        lambda *_args, **_kwargs: _FakeConnection(),
    )

    conn = sqlite_utils.connect_sqlite(
        "/tmp/sqlite_utils_read_only_pragmas.db",
        ensure_parent_dir=False,
        read_only=True,
        pragmas=(
            "PRAGMA journal_mode=WAL",
            "PRAGMA synchronous=NORMAL",
            "PRAGMA busy_timeout=777",
        ),
    )
    conn.close()

    assert executed_sqls == ["PRAGMA query_only=ON", "PRAGMA busy_timeout=777"]


def test_connect_sqlite_read_only_keeps_single_query_only_pragma(monkeypatch):
    executed_sqls: list[str] = []

    class _FakeConnection:
        def execute(self, sql):
            executed_sqls.append(str(sql).strip())
            return None

        def close(self):
            return None

    monkeypatch.setattr(
        sqlite_utils.sqlite3,
        "connect",
        lambda *_args, **_kwargs: _FakeConnection(),
    )

    conn = sqlite_utils.connect_sqlite(
        "/tmp/sqlite_utils_read_only_query_only.db",
        ensure_parent_dir=False,
        read_only=True,
        pragmas=(
            "PRAGMA query_only=ON",
            "PRAGMA busy_timeout=444",
        ),
    )
    conn.close()

    assert executed_sqls == ["PRAGMA query_only=ON", "PRAGMA busy_timeout=444"]


def test_connect_sqlite_read_only_memory_uri_enforces_query_only():
    db_uri = "file:sqlite_utils_read_only_memory?mode=memory&cache=shared"

    with sqlite_utils.connect_sqlite(
        db_uri,
        ensure_parent_dir=False,
        read_only=True,
    ) as conn:
        cursor = conn.cursor()
        cursor.execute("PRAGMA query_only")
        query_only_value = int(cursor.fetchone()[0])

        with pytest.raises(sqlite3.OperationalError):
            cursor.execute("CREATE TABLE sample (id INTEGER PRIMARY KEY)")

    assert query_only_value == 1


def test_connect_sqlite_read_only_file_path_blocks_write(tmp_path: Path):
    db_path = tmp_path / "sqlite_utils_read_only_write_block.db"
    with sqlite_utils.connect_sqlite(str(db_path)) as conn:
        conn.execute("CREATE TABLE sample (id INTEGER PRIMARY KEY, value TEXT)")
        conn.execute("INSERT INTO sample (value) VALUES (?)", ("seed",))
        conn.commit()

    with sqlite_utils.connect_sqlite(
        str(db_path),
        read_only=True,
    ) as conn:
        cursor = conn.cursor()
        cursor.execute("PRAGMA query_only")
        query_only_value = int(cursor.fetchone()[0])
        with pytest.raises(sqlite3.OperationalError):
            cursor.execute("INSERT INTO sample (value) VALUES (?)", ("blocked",))

    assert query_only_value == 1


def test_connect_sqlite_skips_persistent_signature_lookup_for_read_only_connections(
    monkeypatch,
):
    class _FakeConnection:
        def execute(self, _sql):
            return None

        def close(self):
            return None

    monkeypatch.setattr(
        sqlite_utils.sqlite3,
        "connect",
        lambda *_args, **_kwargs: _FakeConnection(),
    )
    monkeypatch.setattr(
        sqlite_utils,
        "_load_sqlite_file_signature",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("persistent signature lookup should be skipped for read-only connection"),
        ),
    )

    conn = sqlite_utils.connect_sqlite(
        "/tmp/sqlite_utils_read_only_no_signature.db",
        ensure_parent_dir=False,
        read_only=True,
    )
    conn.close()


def test_connect_sqlite_skips_persistent_signature_lookup_when_no_persistent_pragmas(
    monkeypatch,
):
    class _FakeConnection:
        def execute(self, _sql):
            return None

        def close(self):
            return None

    monkeypatch.setattr(
        sqlite_utils.sqlite3,
        "connect",
        lambda *_args, **_kwargs: _FakeConnection(),
    )
    monkeypatch.setattr(
        sqlite_utils,
        "_load_sqlite_file_signature",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("persistent signature lookup should be skipped without persistent pragmas"),
        ),
    )

    conn = sqlite_utils.connect_sqlite(
        "/tmp/sqlite_utils_no_persistent_pragma.db",
        ensure_parent_dir=False,
        pragmas=("PRAGMA busy_timeout=1000",),
    )
    conn.close()


def test_connect_sqlite_skips_reapplying_persistent_pragmas_for_same_file_db(
    monkeypatch,
    tmp_path: Path,
):
    db_path = tmp_path / "sqlite_utils_persistent_once.db"
    executed_sqls: list[list[str]] = []

    class _FakeConnection:
        def __init__(self):
            self.sqls: list[str] = []

        def execute(self, sql):
            self.sqls.append(str(sql).strip())
            return None

        def close(self):
            executed_sqls.append(list(self.sqls))

    with sqlite_utils._SQLITE_PERSISTENT_PRAGMAS_LOCK:
        sqlite_utils._SQLITE_PERSISTENT_PRAGMAS_READY.clear()

    signature = {"value": (11, 7)}
    monkeypatch.setattr(
        sqlite_utils,
        "_load_sqlite_file_signature",
        lambda _db_key: signature["value"],
    )
    monkeypatch.setattr(
        sqlite_utils.sqlite3,
        "connect",
        lambda *_args, **_kwargs: _FakeConnection(),
    )

    pragmas = (
        "PRAGMA journal_mode=WAL",
        "PRAGMA synchronous=NORMAL",
        "PRAGMA busy_timeout=1200",
    )

    first_conn = sqlite_utils.connect_sqlite(
        str(db_path),
        ensure_parent_dir=False,
        pragmas=pragmas,
    )
    first_conn.close()
    second_conn = sqlite_utils.connect_sqlite(
        str(db_path),
        ensure_parent_dir=False,
        pragmas=pragmas,
    )
    second_conn.close()

    assert executed_sqls[0] == [
        "PRAGMA journal_mode=WAL",
        "PRAGMA synchronous=NORMAL",
        "PRAGMA busy_timeout=1200",
    ]
    assert executed_sqls[1] == ["PRAGMA busy_timeout=1200"]


def test_connect_sqlite_reapplies_persistent_pragmas_when_file_signature_changes(
    monkeypatch,
    tmp_path: Path,
):
    db_path = tmp_path / "sqlite_utils_persistent_signature.db"
    executed_sqls: list[list[str]] = []

    class _FakeConnection:
        def __init__(self):
            self.sqls: list[str] = []

        def execute(self, sql):
            self.sqls.append(str(sql).strip())
            return None

        def close(self):
            executed_sqls.append(list(self.sqls))

    with sqlite_utils._SQLITE_PERSISTENT_PRAGMAS_LOCK:
        sqlite_utils._SQLITE_PERSISTENT_PRAGMAS_READY.clear()

    signature = {"value": (21, 3)}
    monkeypatch.setattr(
        sqlite_utils,
        "_load_sqlite_file_signature",
        lambda _db_key: signature["value"],
    )
    monkeypatch.setattr(
        sqlite_utils.sqlite3,
        "connect",
        lambda *_args, **_kwargs: _FakeConnection(),
    )

    pragmas = (
        "PRAGMA journal_mode=WAL",
        "PRAGMA synchronous=NORMAL",
    )

    first_conn = sqlite_utils.connect_sqlite(
        str(db_path),
        ensure_parent_dir=False,
        pragmas=pragmas,
    )
    first_conn.close()

    signature["value"] = (21, 4)
    second_conn = sqlite_utils.connect_sqlite(
        str(db_path),
        ensure_parent_dir=False,
        pragmas=pragmas,
    )
    second_conn.close()

    assert executed_sqls[0] == ["PRAGMA journal_mode=WAL", "PRAGMA synchronous=NORMAL"]
    assert executed_sqls[1] == ["PRAGMA journal_mode=WAL", "PRAGMA synchronous=NORMAL"]


def test_connect_sqlite_applies_persistent_pragmas_for_memory_db_on_every_connection(monkeypatch):
    executed_sqls: list[list[str]] = []

    class _FakeConnection:
        def __init__(self):
            self.sqls: list[str] = []

        def execute(self, sql):
            self.sqls.append(str(sql).strip())
            return None

        def close(self):
            executed_sqls.append(list(self.sqls))

    with sqlite_utils._SQLITE_PERSISTENT_PRAGMAS_LOCK:
        sqlite_utils._SQLITE_PERSISTENT_PRAGMAS_READY.clear()

    monkeypatch.setattr(
        sqlite_utils.sqlite3,
        "connect",
        lambda *_args, **_kwargs: _FakeConnection(),
    )

    pragmas = (
        "PRAGMA journal_mode=WAL",
        "PRAGMA synchronous=NORMAL",
        "PRAGMA busy_timeout=600",
    )

    first_conn = sqlite_utils.connect_sqlite(
        ":memory:",
        ensure_parent_dir=False,
        pragmas=pragmas,
    )
    first_conn.close()

    second_conn = sqlite_utils.connect_sqlite(
        ":memory:",
        ensure_parent_dir=False,
        pragmas=pragmas,
    )
    second_conn.close()

    assert executed_sqls[0] == [
        "PRAGMA journal_mode=WAL",
        "PRAGMA synchronous=NORMAL",
        "PRAGMA busy_timeout=600",
    ]
    assert executed_sqls[1] == [
        "PRAGMA journal_mode=WAL",
        "PRAGMA synchronous=NORMAL",
        "PRAGMA busy_timeout=600",
    ]
    with sqlite_utils._SQLITE_PERSISTENT_PRAGMAS_LOCK:
        assert sqlite_utils._SQLITE_PERSISTENT_PRAGMAS_READY == {}


def test_normalize_sqlite_db_key_normalizes_relative_path_and_file_uri(monkeypatch, tmp_path: Path):
    monkeypatch.chdir(tmp_path)
    relative_path = "nested/sqlite_utils_normalize.db"
    absolute_path = tmp_path / "nested" / "sqlite_utils_normalize.db"
    file_uri = f"file:{absolute_path}?mode=rwc"

    key_from_relative = sqlite_utils.normalize_sqlite_db_key(relative_path)
    key_from_uri = sqlite_utils.normalize_sqlite_db_key(file_uri)

    assert key_from_relative == key_from_uri


def test_connect_sqlite_creates_parent_directory_for_file_uri(tmp_path: Path):
    db_path = tmp_path / "nested" / "uri" / "sqlite_utils_uri_parent.db"
    db_uri = f"file:{db_path}?mode=rwc"
    assert not db_path.parent.exists()

    with sqlite_utils.connect_sqlite(db_uri, pragmas=("PRAGMA busy_timeout=222",)) as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS t (id INTEGER PRIMARY KEY)")
        conn.commit()

    assert db_path.parent.exists()
    assert db_path.exists()
    assert sqlite_utils.sqlite_db_path_exists(db_uri) is True


def test_sqlite_db_path_exists_returns_false_for_memory_path():
    assert sqlite_utils.sqlite_db_path_exists(":memory:") is False


def test_sqlite_db_path_exists_returns_false_for_memory_file_uri():
    assert sqlite_utils.sqlite_db_path_exists("file:test.db?mode=memory&cache=shared") is False
    assert sqlite_utils.sqlite_db_path_exists("file::memory:?cache=shared") is False


def test_sqlite_db_path_exists_returns_false_for_empty_file_uri():
    assert sqlite_utils.sqlite_db_path_exists("file:?cache=shared") is False


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


def test_parent_dir_ready_cache_is_bounded(monkeypatch, tmp_path: Path):
    with sqlite_utils._SQLITE_PARENT_DIRS_LOCK:
        sqlite_utils._SQLITE_PARENT_DIRS_READY.clear()

    monkeypatch.setattr(sqlite_utils, "_SQLITE_PARENT_DIRS_MAX_ENTRIES", 2)

    first_parent = os.path.realpath(str(tmp_path / "parent_0"))
    for idx in range(3):
        db_path = tmp_path / f"parent_{idx}" / "sqlite_utils_parent_bound.db"
        sqlite_utils._ensure_sqlite_parent_dir(str(db_path))

    with sqlite_utils._SQLITE_PARENT_DIRS_LOCK:
        parent_keys = list(sqlite_utils._SQLITE_PARENT_DIRS_READY.keys())

    assert len(parent_keys) == 2
    assert first_parent not in parent_keys


def test_persistent_pragmas_ready_cache_is_bounded(monkeypatch, tmp_path: Path):
    with sqlite_utils._SQLITE_PERSISTENT_PRAGMAS_LOCK:
        sqlite_utils._SQLITE_PERSISTENT_PRAGMAS_READY.clear()

    monkeypatch.setattr(sqlite_utils, "_SQLITE_PERSISTENT_PRAGMAS_MAX_ENTRIES", 2)

    first_db_key = sqlite_utils.normalize_sqlite_db_key(str(tmp_path / "persistent_0.db"))
    for idx in range(3):
        db_key = sqlite_utils.normalize_sqlite_db_key(str(tmp_path / f"persistent_{idx}.db"))
        pending = sqlite_utils._compute_pending_persistent_pragmas(
            db_key,
            ("PRAGMA journal_mode=WAL",),
        )
        assert pending == {"PRAGMA journal_mode=WAL"}
        sqlite_utils._mark_persistent_pragmas_applied(
            db_key,
            ("PRAGMA journal_mode=WAL",),
        )

    with sqlite_utils._SQLITE_PERSISTENT_PRAGMAS_LOCK:
        cached_keys = list(sqlite_utils._SQLITE_PERSISTENT_PRAGMAS_READY.keys())

    assert len(cached_keys) == 2
    assert first_db_key not in cached_keys


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


def test_run_sqlite_with_retry_retries_transient_lock_error(monkeypatch):
    calls = {"count": 0}
    sleep_calls: list[float] = []

    monkeypatch.setattr(sqlite_utils.time, "sleep", lambda delay: sleep_calls.append(float(delay)))

    def _flaky_operation() -> str:
        calls["count"] += 1
        if calls["count"] < 3:
            raise sqlite3.OperationalError("database is locked")
        return "ok"

    result = sqlite_utils.run_sqlite_with_retry(
        _flaky_operation,
        max_retries=3,
        retry_delay_seconds=0.01,
    )

    assert result == "ok"
    assert calls["count"] == 3
    assert sleep_calls == [0.01, 0.02]


def test_run_sqlite_with_retry_retries_on_schema_changed_error(monkeypatch):
    calls = {"count": 0}
    sleep_calls: list[float] = []

    monkeypatch.setattr(sqlite_utils.time, "sleep", lambda delay: sleep_calls.append(float(delay)))

    def _flaky_operation() -> str:
        calls["count"] += 1
        if calls["count"] < 3:
            raise sqlite3.OperationalError("database schema has changed")
        return "ok"

    result = sqlite_utils.run_sqlite_with_retry(
        _flaky_operation,
        max_retries=3,
        retry_delay_seconds=0.01,
    )

    assert result == "ok"
    assert calls["count"] == 3
    assert sleep_calls == [0.01, 0.02]


def test_run_sqlite_with_retry_does_not_retry_non_transient_error(monkeypatch):
    calls = {"count": 0}
    sleep_calls: list[float] = []

    monkeypatch.setattr(sqlite_utils.time, "sleep", lambda delay: sleep_calls.append(float(delay)))

    def _broken_operation() -> None:
        calls["count"] += 1
        raise sqlite3.OperationalError("no such table: missing_table")

    with pytest.raises(sqlite3.OperationalError):
        sqlite_utils.run_sqlite_with_retry(
            _broken_operation,
            max_retries=3,
            retry_delay_seconds=0.01,
        )

    assert calls["count"] == 1
    assert sleep_calls == []


def test_add_bounded_ready_key_prunes_when_capacity_exceeded():
    ready_keys: set[str] = {"a", "b"}

    sqlite_utils.add_bounded_ready_key(ready_keys, "c", max_entries=2)

    assert len(ready_keys) == 2
    assert "c" in ready_keys
    assert ready_keys.intersection({"a", "b"})


def test_add_bounded_ready_key_keeps_existing_key_without_reset():
    ready_keys: set[str] = {"a", "b"}

    sqlite_utils.add_bounded_ready_key(ready_keys, "b", max_entries=2)

    assert ready_keys == {"a", "b"}


def test_is_sqlite_missing_table_error_matches_single_table_name():
    error = sqlite3.OperationalError("no such table: update_status_snapshot")

    assert sqlite_utils.is_sqlite_missing_table_error(error, table_names="update_status_snapshot") is True
    assert sqlite_utils.is_sqlite_missing_table_error(error, table_names="another_table") is False


def test_is_sqlite_missing_table_error_handles_iterable_and_non_operational():
    missing_table_error = sqlite3.OperationalError("no such table: realtime_price_cache")
    non_missing_table_error = sqlite3.OperationalError("database is locked")
    type_error = RuntimeError("no such table: realtime_price_cache")

    assert (
        sqlite_utils.is_sqlite_missing_table_error(
            missing_table_error,
            table_names=("realtime_price_cache", "fallback_table"),
        )
        is True
    )
    assert (
        sqlite_utils.is_sqlite_missing_table_error(
            non_missing_table_error,
            table_names=("realtime_price_cache",),
        )
        is False
    )
    assert sqlite_utils.is_sqlite_missing_table_error(type_error, table_names=("realtime_price_cache",)) is False


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


def test_prune_rows_by_updated_at_if_needed_uses_rowid_tiebreaker_for_same_updated_at(
    tmp_path: Path,
):
    db_path = tmp_path / "sqlite_utils_prune_tiebreaker.db"

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
                ("k2", "2026-02-20T10:00:00"),
                ("k3", "2026-02-20T10:00:00"),
                ("k4", "2026-02-20T10:00:00"),
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
                ORDER BY rowid DESC
                """
            ).fetchall()
        ]

    assert did_prune is True
    assert remaining == ["k4", "k3"]


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
