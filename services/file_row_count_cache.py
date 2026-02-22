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
import sqlite3
import threading
from datetime import datetime
from typing import Any, Callable

from services.sqlite_utils import (
    build_sqlite_pragmas,
    connect_sqlite,
    is_sqlite_missing_table_error,
    normalize_sqlite_db_key,
    prune_rows_by_updated_at_if_needed,
    run_sqlite_with_retry,
    sqlite_db_path_exists,
)

_ROW_COUNT_CACHE: dict[str, tuple[tuple[int, int], int | None]] = {}
_ROW_COUNT_CACHE_LOCK = threading.Lock()
_ROW_COUNT_SQLITE_LOCK = threading.Lock()
_ROW_COUNT_SQLITE_READY: set[str] = set()
_ROW_COUNT_MEMORY_MAX_ENTRIES = 4_096

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_ROW_COUNT_CACHE_DB_PATH = os.path.join(_BASE_DIR, "data", "runtime_cache.db")
_ROW_COUNT_SQLITE_TIMEOUT_SECONDS = 5
_ROW_COUNT_SQLITE_MAX_ROWS = 8_192
_ROW_COUNT_SQLITE_RETRY_ATTEMPTS = 2
_ROW_COUNT_SQLITE_RETRY_DELAY_SECONDS = 0.03
_ROW_COUNT_INIT_PRAGMAS = build_sqlite_pragmas(
    busy_timeout_ms=_ROW_COUNT_SQLITE_TIMEOUT_SECONDS * 1000,
)
_ROW_COUNT_SESSION_PRAGMAS = build_sqlite_pragmas(
    busy_timeout_ms=_ROW_COUNT_SQLITE_TIMEOUT_SECONDS * 1000,
    base_pragmas=("PRAGMA temp_store=MEMORY", "PRAGMA cache_size=-4000"),
)


def _invalidate_row_count_sqlite_ready(db_path: str) -> None:
    db_key = normalize_sqlite_db_key(db_path)
    with _ROW_COUNT_SQLITE_LOCK:
        _ROW_COUNT_SQLITE_READY.discard(db_key)


def _is_missing_table_error(error: Exception) -> bool:
    return is_sqlite_missing_table_error(error, table_names="file_row_count_cache")


def _recover_row_count_sqlite_schema(logger: Any) -> bool:
    db_path = _ROW_COUNT_CACHE_DB_PATH
    _invalidate_row_count_sqlite_ready(db_path)
    return _ensure_row_count_sqlite_cache(logger)


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


def _save_row_count_memory_entry(path: str, signature: tuple[int, int], row_count: int | None) -> None:
    max_entries = max(1, int(_ROW_COUNT_MEMORY_MAX_ENTRIES))
    with _ROW_COUNT_CACHE_LOCK:
        if path in _ROW_COUNT_CACHE:
            _ROW_COUNT_CACHE.pop(path, None)
        elif len(_ROW_COUNT_CACHE) >= max_entries:
            oldest_key = next(iter(_ROW_COUNT_CACHE))
            _ROW_COUNT_CACHE.pop(oldest_key, None)
        _ROW_COUNT_CACHE[path] = (signature, row_count)


def _ensure_row_count_sqlite_cache(logger: Any) -> bool:
    db_path = _ROW_COUNT_CACHE_DB_PATH
    db_key = normalize_sqlite_db_key(db_path)
    with _ROW_COUNT_SQLITE_LOCK:
        if db_key in _ROW_COUNT_SQLITE_READY:
            if sqlite_db_path_exists(db_path):
                return True
            _ROW_COUNT_SQLITE_READY.discard(db_key)

        def _initialize_schema() -> None:
            with connect_sqlite(
                db_path,
                timeout_seconds=_ROW_COUNT_SQLITE_TIMEOUT_SECONDS,
                pragmas=_ROW_COUNT_INIT_PRAGMAS,
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
        try:
            run_sqlite_with_retry(
                _initialize_schema,
                max_retries=_ROW_COUNT_SQLITE_RETRY_ATTEMPTS,
                retry_delay_seconds=_ROW_COUNT_SQLITE_RETRY_DELAY_SECONDS,
            )
            _ROW_COUNT_SQLITE_READY.add(db_key)
            return True
        except Exception as error:
            logger.debug("Failed to initialize row count sqlite cache: %s", error)
            return False


def _load_row_count_from_sqlite(
    *,
    path: str,
    signature: tuple[int, int],
    logger: Any,
) -> tuple[bool, int | None]:
    if not _ensure_row_count_sqlite_cache(logger):
        return False, None

    def _query_row() -> tuple[Any, ...] | None:
        with connect_sqlite(
            _ROW_COUNT_CACHE_DB_PATH,
            timeout_seconds=_ROW_COUNT_SQLITE_TIMEOUT_SECONDS,
            pragmas=_ROW_COUNT_SESSION_PRAGMAS,
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
            return cursor.fetchone()

    try:
        row = run_sqlite_with_retry(
            _query_row,
            max_retries=_ROW_COUNT_SQLITE_RETRY_ATTEMPTS,
            retry_delay_seconds=_ROW_COUNT_SQLITE_RETRY_DELAY_SECONDS,
        )
    except Exception as error:
        if _is_missing_table_error(error) and _recover_row_count_sqlite_schema(logger):
            try:
                row = run_sqlite_with_retry(
                    _query_row,
                    max_retries=_ROW_COUNT_SQLITE_RETRY_ATTEMPTS,
                    retry_delay_seconds=_ROW_COUNT_SQLITE_RETRY_DELAY_SECONDS,
                )
            except Exception as retry_error:
                logger.debug(
                    "Failed to load row count cache from sqlite after schema recovery (%s): %s",
                    path,
                    retry_error,
                )
                return False, None
        else:
            logger.debug("Failed to load row count cache from sqlite (%s): %s", path, error)
            return False, None

    try:
        if row is None:
            return False, None
        return True, row[0]
    except Exception as error:
        logger.debug("Failed to parse row count cache row from sqlite (%s): %s", path, error)
        return False, None


def _prune_row_count_cache_if_needed(
    cursor: sqlite3.Cursor,
    *,
    max_rows: int,
) -> None:
    normalized_max_rows = max(1, int(max_rows))
    prune_rows_by_updated_at_if_needed(
        cursor,
        table_name="file_row_count_cache",
        max_rows=normalized_max_rows,
    )


def _save_row_count_to_sqlite(
    *,
    path: str,
    signature: tuple[int, int],
    row_count: int | None,
    logger: Any,
) -> None:
    if not _ensure_row_count_sqlite_cache(logger):
        return

    normalized_max_rows = max(1, int(_ROW_COUNT_SQLITE_MAX_ROWS))
    def _upsert_row_count() -> None:
        with connect_sqlite(
            _ROW_COUNT_CACHE_DB_PATH,
            timeout_seconds=_ROW_COUNT_SQLITE_TIMEOUT_SECONDS,
            pragmas=_ROW_COUNT_SESSION_PRAGMAS,
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
            _prune_row_count_cache_if_needed(
                cursor,
                max_rows=normalized_max_rows,
            )
            conn.commit()

    try:
        run_sqlite_with_retry(
            _upsert_row_count,
            max_retries=_ROW_COUNT_SQLITE_RETRY_ATTEMPTS,
            retry_delay_seconds=_ROW_COUNT_SQLITE_RETRY_DELAY_SECONDS,
        )
    except Exception as error:
        if _is_missing_table_error(error) and _recover_row_count_sqlite_schema(logger):
            try:
                run_sqlite_with_retry(
                    _upsert_row_count,
                    max_retries=_ROW_COUNT_SQLITE_RETRY_ATTEMPTS,
                    retry_delay_seconds=_ROW_COUNT_SQLITE_RETRY_DELAY_SECONDS,
                )
            except Exception as retry_error:
                logger.debug(
                    "Failed to persist row count cache into sqlite after schema recovery (%s): %s",
                    path,
                    retry_error,
                )
        else:
            logger.debug("Failed to persist row count cache into sqlite (%s): %s", path, error)


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
        _save_row_count_memory_entry(path, signature, sqlite_cached)
        return sqlite_cached

    resolver = count_rows_fn or count_rows_for_path
    row_count = resolver(path, logger)

    _save_row_count_memory_entry(path, signature, row_count)
    _save_row_count_to_sqlite(
        path=path,
        signature=signature,
        row_count=row_count,
        logger=logger,
    )
    return row_count
