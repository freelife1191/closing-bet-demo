#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
파일 row-count 캐시 유틸 테스트
"""

from __future__ import annotations

from pathlib import Path
import sqlite3

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
