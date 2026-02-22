#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
파일 row-count 캐시 유틸 테스트
"""

from __future__ import annotations

from pathlib import Path

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

