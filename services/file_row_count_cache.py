#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
파일 row-count 캐시 유틸.

- 메모리 캐시 + SQLite(runtime_cache.db) 영속 캐시를 함께 사용
- 시그니처(mtime_ns, size_bytes) 기준으로 유효성 판별
"""

from __future__ import annotations

import json
import os
import threading
from datetime import datetime
from typing import Any, Callable

from services.sqlite_utils import connect_sqlite

_ROW_COUNT_CACHE: dict[str, tuple[tuple[int, int], int | None]] = {}
_ROW_COUNT_CACHE_LOCK = threading.Lock()
_ROW_COUNT_SQLITE_LOCK = threading.Lock()
_ROW_COUNT_SQLITE_READY: set[str] = set()

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_ROW_COUNT_CACHE_DB_PATH = os.path.join(_BASE_DIR, "data", "runtime_cache.db")


def clear_file_row_count_cache() -> None:
    with _ROW_COUNT_CACHE_LOCK:
        _ROW_COUNT_CACHE.clear()


def file_signature(path: str) -> tuple[int, int] | None:
    try:
        stat = os.stat(path)
    except OSError:
        return None
    return int(stat.st_mtime_ns), int(stat.st_size)


def _count_csv_rows(path: str, logger: Any) -> int | None:
    try:
        with open(path, "r", encoding="utf-8") as csv_file:
            return max(0, sum(1 for _ in csv_file) - 1)
    except Exception as error:
        logger.debug(f"Failed to count CSV rows ({path}): {error}")
        return None


def _count_json_rows(path: str, logger: Any) -> int | None:
    try:
        with open(path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except Exception as error:
        logger.debug(f"Failed to count JSON rows ({path}): {error}")
        return None

    if isinstance(payload, dict) and "signals" in payload:
        signals = payload.get("signals")
        return len(signals) if isinstance(signals, list) else 0
    if isinstance(payload, list):
        return len(payload)
    return None


def count_rows_for_path(path: str, logger: Any) -> int | None:
    if path.endswith(".csv"):
        return _count_csv_rows(path, logger)
    if path.endswith(".json"):
        return _count_json_rows(path, logger)
    return None


def _ensure_row_count_sqlite_cache(logger: Any) -> bool:
    db_path = _ROW_COUNT_CACHE_DB_PATH
    if db_path in _ROW_COUNT_SQLITE_READY:
        return True

    with _ROW_COUNT_SQLITE_LOCK:
        if db_path in _ROW_COUNT_SQLITE_READY:
            return True
        try:
            os.makedirs(os.path.dirname(db_path), exist_ok=True)
            with connect_sqlite(
                db_path,
                timeout_seconds=5,
                pragmas=(
                    "PRAGMA journal_mode=WAL",
                    "PRAGMA synchronous=NORMAL",
                    "PRAGMA temp_store=MEMORY",
                    "PRAGMA busy_timeout=5000",
                ),
            ) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS file_row_count_cache (
                        path TEXT PRIMARY KEY,
                        mtime_ns INTEGER NOT NULL,
                        size_bytes INTEGER NOT NULL,
                        row_count INTEGER,
                        updated_at TEXT NOT NULL
                    )
                    """
                )
                cursor.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_file_row_count_cache_updated_at
                    ON file_row_count_cache(updated_at DESC)
                    """
                )
                conn.commit()
            _ROW_COUNT_SQLITE_READY.add(db_path)
            return True
        except Exception as error:
            logger.debug(f"Failed to initialize row count sqlite cache: {error}")
            return False


def _load_row_count_from_sqlite(
    *,
    path: str,
    signature: tuple[int, int],
    logger: Any,
) -> tuple[bool, int | None]:
    if not _ensure_row_count_sqlite_cache(logger):
        return False, None

    try:
        with connect_sqlite(
            _ROW_COUNT_CACHE_DB_PATH,
            timeout_seconds=5,
            pragmas=("PRAGMA busy_timeout=5000",),
        ) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT row_count
                FROM file_row_count_cache
                WHERE path = ? AND mtime_ns = ? AND size_bytes = ?
                """,
                (path, int(signature[0]), int(signature[1])),
            )
            row = cursor.fetchone()
        if row is None:
            return False, None
        return True, row[0]
    except Exception as error:
        logger.debug(f"Failed to load row count cache from sqlite ({path}): {error}")
        return False, None


def _save_row_count_to_sqlite(
    *,
    path: str,
    signature: tuple[int, int],
    row_count: int | None,
    logger: Any,
) -> None:
    if not _ensure_row_count_sqlite_cache(logger):
        return

    try:
        with connect_sqlite(
            _ROW_COUNT_CACHE_DB_PATH,
            timeout_seconds=5,
            pragmas=("PRAGMA busy_timeout=5000",),
        ) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO file_row_count_cache (path, mtime_ns, size_bytes, row_count, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(path) DO UPDATE SET
                    mtime_ns = excluded.mtime_ns,
                    size_bytes = excluded.size_bytes,
                    row_count = excluded.row_count,
                    updated_at = excluded.updated_at
                """,
                (
                    path,
                    int(signature[0]),
                    int(signature[1]),
                    row_count,
                    datetime.now().isoformat(),
                ),
            )
            conn.commit()
    except Exception as error:
        logger.debug(f"Failed to persist row count cache into sqlite ({path}): {error}")


def get_cached_file_row_count(
    *,
    path: str,
    signature: tuple[int, int] | None,
    logger: Any,
    count_rows_fn: Callable[[str, Any], int | None] | None = None,
) -> int | None:
    """파일 시그니처 기준 row-count를 반환한다."""
    if signature is None:
        return None

    with _ROW_COUNT_CACHE_LOCK:
        cached = _ROW_COUNT_CACHE.get(path)
        if cached is not None and cached[0] == signature:
            return cached[1]

    found_in_sqlite, sqlite_cached = _load_row_count_from_sqlite(
        path=path,
        signature=signature,
        logger=logger,
    )
    if found_in_sqlite:
        with _ROW_COUNT_CACHE_LOCK:
            _ROW_COUNT_CACHE[path] = (signature, sqlite_cached)
        return sqlite_cached

    resolver = count_rows_fn or count_rows_for_path
    row_count = resolver(path, logger)

    with _ROW_COUNT_CACHE_LOCK:
        _ROW_COUNT_CACHE[path] = (signature, row_count)
    _save_row_count_to_sqlite(
        path=path,
        signature=signature,
        row_count=row_count,
        logger=logger,
    )
    return row_count

