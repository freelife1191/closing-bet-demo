#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Signal Tracker 분석용 CSV source cache helper.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import threading
from datetime import datetime
from io import StringIO
from typing import Any

import pandas as pd

from services.sqlite_utils import (
    build_sqlite_pragmas,
    connect_sqlite,
    prune_rows_by_updated_at_if_needed,
)


logger = logging.getLogger(__name__)

SUPPLY_SOURCE_CACHE: dict[str, tuple[tuple[int, int, int], pd.DataFrame]] = {}
PERFORMANCE_SOURCE_CACHE: dict[str, tuple[tuple[int, int, int], pd.DataFrame]] = {}
SIGNALS_LOG_SOURCE_CACHE: dict[str, tuple[tuple[int, int, int], pd.DataFrame]] = {}
CSV_SOURCE_SQLITE_READY_LOCK = threading.Lock()
CSV_SOURCE_SQLITE_READY: set[str] = set()
CSV_SOURCE_SQLITE_MAX_ROWS = 128
CSV_SOURCE_SQLITE_INIT_PRAGMAS = build_sqlite_pragmas(busy_timeout_ms=30_000)
CSV_SOURCE_SQLITE_SESSION_PRAGMAS = build_sqlite_pragmas(busy_timeout_ms=30_000)


def get_file_signature(path: str) -> tuple[int, int, int] | None:
    try:
        stat = os.stat(path)
        return (int(stat.st_ino), int(stat.st_mtime_ns), int(stat.st_size))
    except FileNotFoundError:
        return None
    except Exception:
        return None


def _source_cache_db_path(path: str) -> str:
    return os.path.join(os.path.dirname(path), "runtime_cache.db")


def _invalidate_csv_source_sqlite_ready(db_path: str) -> None:
    with CSV_SOURCE_SQLITE_READY_LOCK:
        CSV_SOURCE_SQLITE_READY.discard(db_path)


def _is_missing_table_error(error: Exception) -> bool:
    if not isinstance(error, sqlite3.OperationalError):
        return False
    message = str(error).lower()
    return "no such table" in message and "signal_tracker_csv_source_cache" in message


def _recover_csv_source_sqlite_schema(db_path: str) -> bool:
    _invalidate_csv_source_sqlite_ready(db_path)
    return _ensure_csv_source_sqlite_cache(db_path)


def _usecols_signature(usecols_filter: set[str] | None) -> str:
    if usecols_filter is None:
        return "__ALL_COLUMNS__"
    return json.dumps(
        sorted(str(column) for column in usecols_filter),
        ensure_ascii=False,
        separators=(",", ":"),
    )


def _ensure_csv_source_sqlite_cache(db_path: str) -> bool:
    with CSV_SOURCE_SQLITE_READY_LOCK:
        if db_path in CSV_SOURCE_SQLITE_READY:
            if os.path.exists(db_path):
                return True
            CSV_SOURCE_SQLITE_READY.discard(db_path)

        try:
            with connect_sqlite(
                db_path,
                timeout_seconds=30,
                pragmas=CSV_SOURCE_SQLITE_INIT_PRAGMAS,
            ) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS signal_tracker_csv_source_cache (
                        source_path TEXT NOT NULL,
                        cache_kind TEXT NOT NULL,
                        usecols_signature TEXT NOT NULL,
                        inode INTEGER NOT NULL,
                        mtime_ns INTEGER NOT NULL,
                        size INTEGER NOT NULL,
                        payload_json TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        PRIMARY KEY (source_path, cache_kind, usecols_signature)
                    )
                    """
                )
                cursor.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_signal_tracker_csv_source_cache_updated_at
                    ON signal_tracker_csv_source_cache(updated_at DESC)
                    """
                )
                conn.commit()
            CSV_SOURCE_SQLITE_READY.add(db_path)
            return True
        except Exception as error:
            logger.debug("Failed to initialize signal tracker sqlite cache: %s", error)
            return False


def _load_csv_source_from_sqlite(
    *,
    path: str,
    signature: tuple[int, int, int],
    usecols_filter: set[str] | None,
    cache_kind: str,
) -> pd.DataFrame | None:
    db_path = _source_cache_db_path(path)
    if not _ensure_csv_source_sqlite_cache(db_path):
        return None

    def _query_row() -> tuple[Any, ...] | None:
        with connect_sqlite(
            db_path,
            timeout_seconds=30,
            pragmas=CSV_SOURCE_SQLITE_SESSION_PRAGMAS,
        ) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT payload_json
                FROM signal_tracker_csv_source_cache
                WHERE source_path = ?
                  AND cache_kind = ?
                  AND usecols_signature = ?
                  AND inode = ?
                  AND mtime_ns = ?
                  AND size = ?
                LIMIT 1
                """,
                (
                    os.path.abspath(path),
                    cache_kind,
                    _usecols_signature(usecols_filter),
                    int(signature[0]),
                    int(signature[1]),
                    int(signature[2]),
                ),
            )
            return cursor.fetchone()

    try:
        row = _query_row()
    except Exception as error:
        if _is_missing_table_error(error) and _recover_csv_source_sqlite_schema(db_path):
            try:
                row = _query_row()
            except Exception as retry_error:
                logger.debug(
                    "Failed to load signal tracker sqlite cache after schema recovery: %s",
                    retry_error,
                )
                return None
        else:
            logger.debug("Failed to load signal tracker sqlite cache: %s", error)
            return None

    try:
        if not row:
            return None
        payload_json = row[0]
        if not isinstance(payload_json, str) or not payload_json:
            return None
        return pd.read_json(StringIO(payload_json), orient="records")
    except Exception as error:
        logger.debug("Failed to load signal tracker sqlite cache: %s", error)
        return None


def _save_csv_source_to_sqlite(
    *,
    path: str,
    signature: tuple[int, int, int],
    usecols_filter: set[str] | None,
    cache_kind: str,
    payload: pd.DataFrame,
) -> None:
    db_path = _source_cache_db_path(path)
    if not _ensure_csv_source_sqlite_cache(db_path):
        return

    try:
        payload_json = payload.to_json(orient="records", force_ascii=False, date_format="iso")
    except Exception as error:
        logger.debug("Failed to serialize signal tracker cache payload: %s", error)
        return

    normalized_max_rows = max(1, int(CSV_SOURCE_SQLITE_MAX_ROWS))

    def _prune_rows_if_needed(cursor: sqlite3.Cursor) -> None:
        prune_rows_by_updated_at_if_needed(
            cursor,
            table_name="signal_tracker_csv_source_cache",
            max_rows=normalized_max_rows,
        )

    def _upsert_payload() -> None:
        with connect_sqlite(
            db_path,
            timeout_seconds=30,
            pragmas=CSV_SOURCE_SQLITE_SESSION_PRAGMAS,
        ) as conn:
            now_iso = datetime.now().isoformat()
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO signal_tracker_csv_source_cache (
                    source_path,
                    cache_kind,
                    usecols_signature,
                    inode,
                    mtime_ns,
                    size,
                    payload_json,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(source_path, cache_kind, usecols_signature) DO UPDATE SET
                    inode = excluded.inode,
                    mtime_ns = excluded.mtime_ns,
                    size = excluded.size,
                    payload_json = excluded.payload_json,
                    updated_at = excluded.updated_at
                """,
                (
                    os.path.abspath(path),
                    cache_kind,
                    _usecols_signature(usecols_filter),
                    int(signature[0]),
                    int(signature[1]),
                    int(signature[2]),
                    payload_json,
                    now_iso,
                ),
            )
            _prune_rows_if_needed(cursor)
            conn.commit()

    try:
        _upsert_payload()
    except Exception as error:
        if _is_missing_table_error(error) and _recover_csv_source_sqlite_schema(db_path):
            try:
                _upsert_payload()
            except Exception as retry_error:
                logger.debug(
                    "Failed to save signal tracker sqlite cache after schema recovery: %s",
                    retry_error,
                )
        else:
            logger.debug("Failed to save signal tracker sqlite cache: %s", error)


def load_csv_with_signature_cache(
    *,
    path: str,
    usecols_filter: set[str] | None,
    cache: dict[str, tuple[tuple[int, int, int], pd.DataFrame]],
    sqlite_cache_kind: str | None = None,
    dtype: dict[str, Any] | None = None,
) -> pd.DataFrame:
    normalized_path = os.path.abspath(path)
    signature = get_file_signature(normalized_path)
    if signature is not None:
        cached = cache.get(normalized_path)
        if cached and cached[0] == signature:
            return cached[1]

        if sqlite_cache_kind:
            sqlite_cached = _load_csv_source_from_sqlite(
                path=normalized_path,
                signature=signature,
                usecols_filter=usecols_filter,
                cache_kind=sqlite_cache_kind,
            )
            if sqlite_cached is not None:
                cache[normalized_path] = (signature, sqlite_cached)
                return sqlite_cached
    else:
        cache.pop(normalized_path, None)

    read_kwargs: dict[str, Any] = {
        "encoding": "utf-8-sig",
        "low_memory": False,
    }
    if usecols_filter is not None:
        read_kwargs["usecols"] = lambda column: column in usecols_filter
    if dtype is not None:
        read_kwargs["dtype"] = dtype

    loaded = pd.read_csv(normalized_path, **read_kwargs)
    refreshed_signature = get_file_signature(normalized_path)
    if refreshed_signature is not None:
        cache[normalized_path] = (refreshed_signature, loaded)
        if sqlite_cache_kind:
            _save_csv_source_to_sqlite(
                path=normalized_path,
                signature=refreshed_signature,
                usecols_filter=usecols_filter,
                cache_kind=sqlite_cache_kind,
                payload=loaded,
            )
    else:
        cache.pop(normalized_path, None)
    return loaded
