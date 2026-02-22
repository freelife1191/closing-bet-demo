#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
파일 row-count 캐시 유틸 테스트
"""

from __future__ import annotations

import os
from pathlib import Path
import sqlite3
import threading
import time

import services.file_row_count_cache as file_row_count_cache


def test_get_cached_file_row_count_reuses_memory_cache(tmp_path: Path):
    file_row_count_cache.clear_file_row_count_cache()
    csv_path = tmp_path / "rows.csv"
    csv_path.write_text("a\n1\n2\n", encoding="utf-8")
    signature = file_row_count_cache.file_signature(str(csv_path))
    assert signature is not None

    calls = {"count": 0}

    def _counter(path: str, _logger):
        calls["count"] += 1
        return file_row_count_cache.count_rows_for_path(path, _logger)

    logger = type("L", (), {"debug": lambda *_a, **_k: None})()
    first = file_row_count_cache.get_cached_file_row_count(
        path=str(csv_path),
        signature=signature,
        logger=logger,
        count_rows_fn=_counter,
    )
    second = file_row_count_cache.get_cached_file_row_count(
        path=str(csv_path),
        signature=signature,
        logger=logger,
        count_rows_fn=_counter,
    )

    assert first == 2
    assert second == 2
    assert calls["count"] == 1


def test_get_cached_file_row_count_reuses_sqlite_cache_after_memory_clear(tmp_path: Path, monkeypatch):
    cache_db = tmp_path / "runtime_cache.db"
    monkeypatch.setattr(file_row_count_cache, "_ROW_COUNT_CACHE_DB_PATH", str(cache_db))
    file_row_count_cache._ROW_COUNT_SQLITE_READY.clear()
    file_row_count_cache.clear_file_row_count_cache()

    csv_path = tmp_path / "rows.csv"
    csv_path.write_text("a\n1\n", encoding="utf-8")
    signature = file_row_count_cache.file_signature(str(csv_path))
    assert signature is not None

    logger = type("L", (), {"debug": lambda *_a, **_k: None})()
    first = file_row_count_cache.get_cached_file_row_count(
        path=str(csv_path),
        signature=signature,
        logger=logger,
    )
    assert first == 1

    file_row_count_cache.clear_file_row_count_cache()
    second = file_row_count_cache.get_cached_file_row_count(
        path=str(csv_path),
        signature=signature,
        logger=logger,
        count_rows_fn=lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("should use sqlite cache")),
    )
    assert second == 1


def test_get_cached_file_row_count_dedupes_relative_and_absolute_paths(
    tmp_path: Path,
    monkeypatch,
):
    cache_db = tmp_path / "runtime_cache.db"
    monkeypatch.setattr(file_row_count_cache, "_ROW_COUNT_CACHE_DB_PATH", str(cache_db))
    file_row_count_cache._ROW_COUNT_SQLITE_READY.clear()
    file_row_count_cache.clear_file_row_count_cache()
    monkeypatch.chdir(tmp_path)

    csv_path = tmp_path / "rows_alias.csv"
    csv_path.write_text("a\n1\n2\n", encoding="utf-8")

    absolute_path = str(csv_path.resolve())
    relative_path = os.path.basename(absolute_path)
    signature = file_row_count_cache.file_signature(absolute_path)
    assert signature is not None

    calls = {"count": 0}
    logger = type("L", (), {"debug": lambda *_a, **_k: None})()

    def _counter(path: str, _logger):
        calls["count"] += 1
        return file_row_count_cache.count_rows_for_path(path, _logger)

    first = file_row_count_cache.get_cached_file_row_count(
        path=absolute_path,
        signature=signature,
        logger=logger,
        count_rows_fn=_counter,
    )
    second = file_row_count_cache.get_cached_file_row_count(
        path=relative_path,
        signature=signature,
        logger=logger,
        count_rows_fn=lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("should reuse normalized cache key")),
    )

    assert first == 2
    assert second == 2
    assert calls["count"] == 1

    with sqlite3.connect(cache_db) as conn:
        row_count = int(conn.execute("SELECT COUNT(*) FROM file_row_count_cache").fetchone()[0])
    assert row_count == 1


def test_get_cached_file_row_count_reads_legacy_sqlite_path_key(
    tmp_path: Path,
    monkeypatch,
):
    cache_db = tmp_path / "runtime_cache.db"
    monkeypatch.setattr(file_row_count_cache, "_ROW_COUNT_CACHE_DB_PATH", str(cache_db))
    file_row_count_cache._ROW_COUNT_SQLITE_READY.clear()
    file_row_count_cache.clear_file_row_count_cache()
    monkeypatch.chdir(tmp_path)

    csv_path = tmp_path / "rows_legacy.csv"
    csv_path.write_text("a\n1\n2\n3\n", encoding="utf-8")
    absolute_path = str(csv_path.resolve())
    legacy_relative_path = os.path.basename(absolute_path)
    signature = file_row_count_cache.file_signature(absolute_path)
    assert signature is not None
    logger = type("L", (), {"debug": lambda *_a, **_k: None})()

    assert file_row_count_cache._ensure_row_count_sqlite_cache(logger) is True
    with sqlite3.connect(cache_db) as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO file_row_count_cache (
                path, mtime_ns, size_bytes, row_count, updated_at
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (
                legacy_relative_path,
                int(signature[0]),
                int(signature[1]),
                3,
                "2026-02-22T00:00:00",
            ),
        )
        conn.commit()

    loaded = file_row_count_cache.get_cached_file_row_count(
        path=absolute_path,
        signature=signature,
        logger=logger,
        count_rows_fn=lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("should read legacy sqlite key")),
    )
    assert loaded == 3


def test_get_cached_file_row_count_legacy_lookup_uses_single_sqlite_connection(
    tmp_path: Path,
    monkeypatch,
):
    cache_db = tmp_path / "runtime_cache.db"
    monkeypatch.setattr(file_row_count_cache, "_ROW_COUNT_CACHE_DB_PATH", str(cache_db))
    file_row_count_cache._ROW_COUNT_SQLITE_READY.clear()
    file_row_count_cache.clear_file_row_count_cache()
    monkeypatch.chdir(tmp_path)

    csv_path = tmp_path / "rows_legacy_single_conn.csv"
    csv_path.write_text("a\n1\n2\n3\n", encoding="utf-8")
    absolute_path = str(csv_path.resolve())
    legacy_relative_path = os.path.basename(absolute_path)
    signature = file_row_count_cache.file_signature(absolute_path)
    assert signature is not None
    logger = type("L", (), {"debug": lambda *_a, **_k: None})()

    assert file_row_count_cache._ensure_row_count_sqlite_cache(logger) is True
    with sqlite3.connect(cache_db) as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO file_row_count_cache (
                path, mtime_ns, size_bytes, row_count, updated_at
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (
                legacy_relative_path,
                int(signature[0]),
                int(signature[1]),
                3,
                "2026-02-22T00:01:00",
            ),
        )
        conn.commit()

    file_row_count_cache.clear_file_row_count_cache()

    connect_calls = {"count": 0}
    original_connect = file_row_count_cache.connect_sqlite

    def _counted_connect(*args, **kwargs):
        if bool(kwargs.get("read_only", False)):
            connect_calls["count"] += 1
        return original_connect(*args, **kwargs)

    monkeypatch.setattr(file_row_count_cache, "connect_sqlite", _counted_connect)

    loaded = file_row_count_cache.get_cached_file_row_count(
        path=absolute_path,
        signature=signature,
        logger=logger,
        count_rows_fn=lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("should read legacy sqlite key")),
    )

    assert loaded == 3
    assert connect_calls["count"] == 1


def test_get_cached_file_row_count_supports_sqlite_db_path_without_parent_dir(
    tmp_path: Path,
    monkeypatch,
):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(file_row_count_cache, "_ROW_COUNT_CACHE_DB_PATH", "runtime_cache.db")
    file_row_count_cache._ROW_COUNT_SQLITE_READY.clear()
    file_row_count_cache.clear_file_row_count_cache()

    csv_path = tmp_path / "rows.csv"
    csv_path.write_text("a\n1\n2\n3\n", encoding="utf-8")
    signature = file_row_count_cache.file_signature(str(csv_path))
    assert signature is not None

    logger = type("L", (), {"debug": lambda *_a, **_k: None})()
    row_count = file_row_count_cache.get_cached_file_row_count(
        path=str(csv_path),
        signature=signature,
        logger=logger,
    )
    assert row_count == 3


def test_get_cached_file_row_count_evicts_oldest_memory_entry(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(file_row_count_cache, "_ROW_COUNT_MEMORY_MAX_ENTRIES", 2)
    file_row_count_cache.clear_file_row_count_cache()

    logger = type("L", (), {"debug": lambda *_a, **_k: None})()
    for idx in range(3):
        csv_path = tmp_path / f"rows_{idx}.csv"
        csv_path.write_text("a\n1\n", encoding="utf-8")
        signature = file_row_count_cache.file_signature(str(csv_path))
        assert signature is not None
        file_row_count_cache.get_cached_file_row_count(
            path=str(csv_path),
            signature=signature,
            logger=logger,
        )

    cache_keys = list(file_row_count_cache._ROW_COUNT_CACHE.keys())
    assert len(cache_keys) == 2
    assert str(tmp_path / "rows_0.csv") not in cache_keys
    assert str(tmp_path / "rows_1.csv") in cache_keys
    assert str(tmp_path / "rows_2.csv") in cache_keys


def test_get_cached_file_row_count_keeps_recently_used_entry_on_eviction(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(file_row_count_cache, "_ROW_COUNT_MEMORY_MAX_ENTRIES", 2)
    file_row_count_cache.clear_file_row_count_cache()

    logger = type("L", (), {"debug": lambda *_a, **_k: None})()
    path_0 = tmp_path / "rows_hot.csv"
    path_1 = tmp_path / "rows_cold.csv"
    path_2 = tmp_path / "rows_new.csv"
    path_0.write_text("a\n1\n", encoding="utf-8")
    path_1.write_text("a\n1\n2\n", encoding="utf-8")
    path_2.write_text("a\n1\n2\n3\n", encoding="utf-8")

    sig_0 = file_row_count_cache.file_signature(str(path_0))
    sig_1 = file_row_count_cache.file_signature(str(path_1))
    sig_2 = file_row_count_cache.file_signature(str(path_2))
    assert sig_0 is not None
    assert sig_1 is not None
    assert sig_2 is not None

    file_row_count_cache.get_cached_file_row_count(path=str(path_0), signature=sig_0, logger=logger)
    file_row_count_cache.get_cached_file_row_count(path=str(path_1), signature=sig_1, logger=logger)
    file_row_count_cache.get_cached_file_row_count(path=str(path_0), signature=sig_0, logger=logger)
    file_row_count_cache.get_cached_file_row_count(path=str(path_2), signature=sig_2, logger=logger)

    cache_keys = list(file_row_count_cache._ROW_COUNT_CACHE.keys())
    assert len(cache_keys) == 2
    assert str(path_0) in cache_keys
    assert str(path_2) in cache_keys
    assert str(path_1) not in cache_keys


def test_get_cached_file_row_count_non_positive_memory_limit_keeps_latest_only(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(file_row_count_cache, "_ROW_COUNT_MEMORY_MAX_ENTRIES", 0)
    file_row_count_cache.clear_file_row_count_cache()

    logger = type("L", (), {"debug": lambda *_a, **_k: None})()
    first = tmp_path / "rows_first.csv"
    second = tmp_path / "rows_second.csv"
    first.write_text("a\n1\n", encoding="utf-8")
    second.write_text("a\n1\n2\n", encoding="utf-8")

    first_sig = file_row_count_cache.file_signature(str(first))
    second_sig = file_row_count_cache.file_signature(str(second))
    assert first_sig is not None
    assert second_sig is not None

    file_row_count_cache.get_cached_file_row_count(path=str(first), signature=first_sig, logger=logger)
    file_row_count_cache.get_cached_file_row_count(path=str(second), signature=second_sig, logger=logger)

    cache_keys = list(file_row_count_cache._ROW_COUNT_CACHE.keys())
    assert len(cache_keys) == 1
    assert cache_keys[0] == str(second)


def test_get_cached_file_row_count_prunes_sqlite_rows(monkeypatch, tmp_path: Path):
    cache_db = tmp_path / "runtime_cache.db"
    monkeypatch.setattr(file_row_count_cache, "_ROW_COUNT_CACHE_DB_PATH", str(cache_db))
    monkeypatch.setattr(file_row_count_cache, "_ROW_COUNT_SQLITE_MAX_ROWS", 2)
    file_row_count_cache._ROW_COUNT_SQLITE_READY.clear()
    file_row_count_cache.clear_file_row_count_cache()

    logger = type("L", (), {"debug": lambda *_a, **_k: None})()
    for idx in range(4):
        csv_path = tmp_path / f"rows_sqlite_{idx}.csv"
        csv_path.write_text("a\n1\n", encoding="utf-8")
        signature = file_row_count_cache.file_signature(str(csv_path))
        assert signature is not None
        file_row_count_cache.get_cached_file_row_count(
            path=str(csv_path),
            signature=signature,
            logger=logger,
        )

    with sqlite3.connect(cache_db) as conn:
        row_count = int(conn.execute("SELECT COUNT(*) FROM file_row_count_cache").fetchone()[0])
    assert row_count == 2


def test_get_cached_file_row_count_recovers_when_sqlite_table_missing(monkeypatch, tmp_path: Path):
    cache_db = tmp_path / "runtime_cache.db"
    monkeypatch.setattr(file_row_count_cache, "_ROW_COUNT_CACHE_DB_PATH", str(cache_db))
    file_row_count_cache._ROW_COUNT_SQLITE_READY.clear()
    file_row_count_cache.clear_file_row_count_cache()

    logger = type("L", (), {"debug": lambda *_a, **_k: None})()

    first_csv = tmp_path / "rows_first.csv"
    first_csv.write_text("a\n1\n", encoding="utf-8")
    first_sig = file_row_count_cache.file_signature(str(first_csv))
    assert first_sig is not None
    first_count = file_row_count_cache.get_cached_file_row_count(
        path=str(first_csv),
        signature=first_sig,
        logger=logger,
    )
    assert first_count == 1

    with sqlite3.connect(cache_db) as conn:
        conn.execute("DROP TABLE file_row_count_cache")
        conn.commit()

    second_csv = tmp_path / "rows_second.csv"
    second_csv.write_text("a\n1\n2\n", encoding="utf-8")
    second_sig = file_row_count_cache.file_signature(str(second_csv))
    assert second_sig is not None

    second_count = file_row_count_cache.get_cached_file_row_count(
        path=str(second_csv),
        signature=second_sig,
        logger=logger,
    )
    assert second_count == 2

    file_row_count_cache.clear_file_row_count_cache()
    from_sqlite = file_row_count_cache.get_cached_file_row_count(
        path=str(second_csv),
        signature=second_sig,
        logger=logger,
        count_rows_fn=lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("should use sqlite cache")),
    )
    assert from_sqlite == 2

    with sqlite3.connect(cache_db) as conn:
        row_count = int(conn.execute("SELECT COUNT(*) FROM file_row_count_cache").fetchone()[0])
    assert row_count >= 1


def test_get_cached_file_row_count_skips_delete_when_within_limit(monkeypatch, tmp_path: Path):
    cache_db = tmp_path / "runtime_cache.db"
    monkeypatch.setattr(file_row_count_cache, "_ROW_COUNT_CACHE_DB_PATH", str(cache_db))
    monkeypatch.setattr(file_row_count_cache, "_ROW_COUNT_SQLITE_MAX_ROWS", 16)
    file_row_count_cache._ROW_COUNT_SQLITE_READY.clear()
    file_row_count_cache.clear_file_row_count_cache()

    traced_sql: list[str] = []
    original_connect = file_row_count_cache.connect_sqlite

    def _traced_connect(*args, **kwargs):
        conn = original_connect(*args, **kwargs)
        conn.set_trace_callback(traced_sql.append)
        return conn

    monkeypatch.setattr(file_row_count_cache, "connect_sqlite", _traced_connect)

    csv_path = tmp_path / "rows_once.csv"
    csv_path.write_text("a\n1\n", encoding="utf-8")
    signature = file_row_count_cache.file_signature(str(csv_path))
    assert signature is not None

    logger = type("L", (), {"debug": lambda *_a, **_k: None})()
    row_count = file_row_count_cache.get_cached_file_row_count(
        path=str(csv_path),
        signature=signature,
        logger=logger,
    )

    assert row_count == 1
    assert not any("DELETE FROM file_row_count_cache" in sql for sql in traced_sql)


def test_get_cached_file_row_count_runs_prune_once_for_repeated_same_path(monkeypatch, tmp_path: Path):
    cache_db = tmp_path / "runtime_cache.db"
    monkeypatch.setattr(file_row_count_cache, "_ROW_COUNT_CACHE_DB_PATH", str(cache_db))
    file_row_count_cache._ROW_COUNT_SQLITE_READY.clear()
    file_row_count_cache.clear_file_row_count_cache()

    prune_calls = {"count": 0}
    original_prune = file_row_count_cache.prune_rows_by_updated_at_if_needed

    def _traced_prune(*args, **kwargs):
        prune_calls["count"] += 1
        return original_prune(*args, **kwargs)

    monkeypatch.setattr(file_row_count_cache, "prune_rows_by_updated_at_if_needed", _traced_prune)

    logger = type("L", (), {"debug": lambda *_a, **_k: None})()
    csv_path = tmp_path / "rows_repeat.csv"
    csv_path.write_text("a\n1\n", encoding="utf-8")
    first_signature = file_row_count_cache.file_signature(str(csv_path))
    assert first_signature is not None

    first_count = file_row_count_cache.get_cached_file_row_count(
        path=str(csv_path),
        signature=first_signature,
        logger=logger,
    )
    assert first_count == 1

    time.sleep(0.01)
    csv_path.write_text("a\n1\n2\n", encoding="utf-8")
    second_signature = file_row_count_cache.file_signature(str(csv_path))
    assert second_signature is not None
    assert second_signature != first_signature

    second_count = file_row_count_cache.get_cached_file_row_count(
        path=str(csv_path),
        signature=second_signature,
        logger=logger,
    )
    assert second_count == 2
    assert prune_calls["count"] == 1


def test_get_cached_file_row_count_runs_prune_for_each_new_path(monkeypatch, tmp_path: Path):
    cache_db = tmp_path / "runtime_cache.db"
    monkeypatch.setattr(file_row_count_cache, "_ROW_COUNT_CACHE_DB_PATH", str(cache_db))
    file_row_count_cache._ROW_COUNT_SQLITE_READY.clear()
    file_row_count_cache.clear_file_row_count_cache()

    prune_calls = {"count": 0}
    original_prune = file_row_count_cache.prune_rows_by_updated_at_if_needed

    def _traced_prune(*args, **kwargs):
        prune_calls["count"] += 1
        return original_prune(*args, **kwargs)

    monkeypatch.setattr(file_row_count_cache, "prune_rows_by_updated_at_if_needed", _traced_prune)

    logger = type("L", (), {"debug": lambda *_a, **_k: None})()
    first_csv_path = tmp_path / "rows_new_1.csv"
    second_csv_path = tmp_path / "rows_new_2.csv"

    first_csv_path.write_text("a\n1\n", encoding="utf-8")
    first_signature = file_row_count_cache.file_signature(str(first_csv_path))
    assert first_signature is not None
    file_row_count_cache.get_cached_file_row_count(
        path=str(first_csv_path),
        signature=first_signature,
        logger=logger,
    )

    time.sleep(0.01)
    first_csv_path.write_text("a\n1\n2\n", encoding="utf-8")
    first_updated_signature = file_row_count_cache.file_signature(str(first_csv_path))
    assert first_updated_signature is not None
    file_row_count_cache.get_cached_file_row_count(
        path=str(first_csv_path),
        signature=first_updated_signature,
        logger=logger,
    )

    second_csv_path.write_text("a\n1\n", encoding="utf-8")
    second_signature = file_row_count_cache.file_signature(str(second_csv_path))
    assert second_signature is not None
    file_row_count_cache.get_cached_file_row_count(
        path=str(second_csv_path),
        signature=second_signature,
        logger=logger,
    )

    assert prune_calls["count"] == 2


def test_get_cached_file_row_count_forces_periodic_prune_for_same_path(monkeypatch, tmp_path: Path):
    cache_db = tmp_path / "runtime_cache.db"
    monkeypatch.setattr(file_row_count_cache, "_ROW_COUNT_CACHE_DB_PATH", str(cache_db))
    monkeypatch.setattr(file_row_count_cache, "_ROW_COUNT_SQLITE_PRUNE_FORCE_INTERVAL", 2)
    file_row_count_cache._ROW_COUNT_SQLITE_READY.clear()
    file_row_count_cache.clear_file_row_count_cache()

    prune_calls = {"count": 0}
    original_prune = file_row_count_cache.prune_rows_by_updated_at_if_needed

    def _traced_prune(*args, **kwargs):
        prune_calls["count"] += 1
        return original_prune(*args, **kwargs)

    monkeypatch.setattr(file_row_count_cache, "prune_rows_by_updated_at_if_needed", _traced_prune)

    logger = type("L", (), {"debug": lambda *_a, **_k: None})()
    csv_path = tmp_path / "rows_force.csv"
    csv_path.write_text("a\n1\n", encoding="utf-8")
    first_signature = file_row_count_cache.file_signature(str(csv_path))
    assert first_signature is not None
    file_row_count_cache.get_cached_file_row_count(
        path=str(csv_path),
        signature=first_signature,
        logger=logger,
    )

    time.sleep(0.01)
    csv_path.write_text("a\n1\n2\n", encoding="utf-8")
    second_signature = file_row_count_cache.file_signature(str(csv_path))
    assert second_signature is not None
    assert second_signature != first_signature
    file_row_count_cache.get_cached_file_row_count(
        path=str(csv_path),
        signature=second_signature,
        logger=logger,
    )

    assert prune_calls["count"] == 2


def test_get_cached_file_row_count_uses_read_only_connection_for_sqlite_reads(
    monkeypatch,
    tmp_path: Path,
):
    cache_db = tmp_path / "runtime_cache.db"
    monkeypatch.setattr(file_row_count_cache, "_ROW_COUNT_CACHE_DB_PATH", str(cache_db))
    file_row_count_cache._ROW_COUNT_SQLITE_READY.clear()
    file_row_count_cache.clear_file_row_count_cache()

    logger = type("L", (), {"debug": lambda *_a, **_k: None})()
    csv_path = tmp_path / "rows_read_only.csv"
    csv_path.write_text("a\n1\n", encoding="utf-8")
    signature = file_row_count_cache.file_signature(str(csv_path))
    assert signature is not None

    # first call warms sqlite cache
    first_count = file_row_count_cache.get_cached_file_row_count(
        path=str(csv_path),
        signature=signature,
        logger=logger,
    )
    assert first_count == 1
    file_row_count_cache.clear_file_row_count_cache()

    read_only_flags: list[bool] = []
    original_connect = file_row_count_cache.connect_sqlite

    def _traced_connect(*args, **kwargs):
        if "read_only" in kwargs:
            read_only_flags.append(bool(kwargs["read_only"]))
        return original_connect(*args, **kwargs)

    monkeypatch.setattr(file_row_count_cache, "connect_sqlite", _traced_connect)

    second_count = file_row_count_cache.get_cached_file_row_count(
        path=str(csv_path),
        signature=signature,
        logger=logger,
        count_rows_fn=lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("should use sqlite cache")),
    )
    assert second_count == 1
    assert True in read_only_flags


def test_row_count_sqlite_ready_uses_normalized_db_key(monkeypatch, tmp_path: Path):
    file_row_count_cache.clear_file_row_count_cache()
    file_row_count_cache._ROW_COUNT_SQLITE_READY.clear()
    monkeypatch.chdir(tmp_path)

    connect_calls = {"count": 0}
    original_connect = file_row_count_cache.connect_sqlite
    logger = type("L", (), {"debug": lambda *_a, **_k: None})()

    def _counted_connect(*args, **kwargs):
        connect_calls["count"] += 1
        return original_connect(*args, **kwargs)

    monkeypatch.setattr(file_row_count_cache, "connect_sqlite", _counted_connect)

    relative_db_path = "./runtime_cache.db"
    absolute_db_path = str((tmp_path / "runtime_cache.db").resolve())

    monkeypatch.setattr(file_row_count_cache, "_ROW_COUNT_CACHE_DB_PATH", relative_db_path)
    assert file_row_count_cache._ensure_row_count_sqlite_cache(logger) is True

    monkeypatch.setattr(file_row_count_cache, "_ROW_COUNT_CACHE_DB_PATH", absolute_db_path)
    assert file_row_count_cache._ensure_row_count_sqlite_cache(logger) is True

    assert connect_calls["count"] == 1
    assert os.path.exists(absolute_db_path)


def test_row_count_sqlite_init_is_single_flight_under_concurrency(monkeypatch, tmp_path: Path):
    file_row_count_cache.clear_file_row_count_cache()
    logger = type("L", (), {"debug": lambda *_a, **_k: None})()
    db_path = str(tmp_path / "runtime_cache.db")
    monkeypatch.setattr(file_row_count_cache, "_ROW_COUNT_CACHE_DB_PATH", db_path)

    with file_row_count_cache._ROW_COUNT_SQLITE_CONDITION:
        file_row_count_cache._ROW_COUNT_SQLITE_READY.clear()
        file_row_count_cache._ROW_COUNT_SQLITE_INIT_IN_PROGRESS.clear()

    monkeypatch.setattr(file_row_count_cache, "sqlite_db_path_exists", lambda _path: True)

    entered_event = threading.Event()
    release_event = threading.Event()
    run_calls = {"count": 0}

    def _run_once(_operation, *, max_retries, retry_delay_seconds):
        run_calls["count"] += 1
        if run_calls["count"] == 1:
            entered_event.set()
            assert release_event.wait(timeout=2.0)
        return None

    monkeypatch.setattr(file_row_count_cache, "run_sqlite_with_retry", _run_once)

    results: dict[str, bool] = {}

    def _worker(name: str) -> None:
        results[name] = bool(file_row_count_cache._ensure_row_count_sqlite_cache(logger))

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


def test_row_count_sqlite_waiter_retries_after_initializer_failure(monkeypatch, tmp_path: Path):
    file_row_count_cache.clear_file_row_count_cache()
    logger = type("L", (), {"debug": lambda *_a, **_k: None})()
    db_path = str(tmp_path / "runtime_cache.db")
    monkeypatch.setattr(file_row_count_cache, "_ROW_COUNT_CACHE_DB_PATH", db_path)

    with file_row_count_cache._ROW_COUNT_SQLITE_CONDITION:
        file_row_count_cache._ROW_COUNT_SQLITE_READY.clear()
        file_row_count_cache._ROW_COUNT_SQLITE_INIT_IN_PROGRESS.clear()

    monkeypatch.setattr(file_row_count_cache, "sqlite_db_path_exists", lambda _path: True)

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

    monkeypatch.setattr(file_row_count_cache, "run_sqlite_with_retry", _fail_then_succeed)

    results: dict[str, bool] = {}

    def _worker(name: str) -> None:
        results[name] = bool(file_row_count_cache._ensure_row_count_sqlite_cache(logger))

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


def test_row_count_sqlite_schema_init_retries_on_transient_lock(monkeypatch, tmp_path: Path):
    file_row_count_cache.clear_file_row_count_cache()
    file_row_count_cache._ROW_COUNT_SQLITE_READY.clear()
    logger = type("L", (), {"debug": lambda *_a, **_k: None})()

    sqlite_cache_path = tmp_path / "runtime_cache.db"
    monkeypatch.setattr(file_row_count_cache, "_ROW_COUNT_CACHE_DB_PATH", str(sqlite_cache_path))

    original_connect = file_row_count_cache.connect_sqlite
    failure_state = {"count": 0}

    def _flaky_connect(*args, **kwargs):
        if failure_state["count"] == 0:
            failure_state["count"] += 1
            raise sqlite3.OperationalError("database is locked")
        return original_connect(*args, **kwargs)

    monkeypatch.setattr(file_row_count_cache, "connect_sqlite", _flaky_connect)

    assert file_row_count_cache._ensure_row_count_sqlite_cache(logger) is True
    assert failure_state["count"] == 1
