#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Signal Tracker CSV source cache helper.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import threading
from collections.abc import Callable
from datetime import datetime
from io import StringIO
from typing import Any

import pandas as pd

from services.sqlite_utils import (
    build_sqlite_pragmas,
    connect_sqlite,
    is_sqlite_missing_table_error,
    normalize_sqlite_db_key,
    prune_rows_by_updated_at_if_needed,
    run_sqlite_with_retry,
    sqlite_db_path_exists,
)


_SOURCE_CACHE: dict[tuple[str, str, str, str], tuple[tuple[int, int], pd.DataFrame]] = {}
_SOURCE_CACHE_LOCK = threading.Lock()
_SOURCE_SQLITE_READY: set[str] = set()
_SOURCE_SQLITE_READY_LOCK = threading.Lock()
_SOURCE_SQLITE_MAX_ROWS = 128
_SOURCE_SQLITE_INIT_PRAGMAS = build_sqlite_pragmas(busy_timeout_ms=30_000)
_SOURCE_SQLITE_SESSION_PRAGMAS = build_sqlite_pragmas(busy_timeout_ms=30_000)
_SOURCE_SQLITE_RETRY_ATTEMPTS = 2
_SOURCE_SQLITE_RETRY_DELAY_SECONDS = 0.03


def _file_signature(path: str) -> tuple[int, int] | None:
    try:
        stat = os.stat(path)
    except OSError:
        return None
    return int(stat.st_mtime_ns), int(stat.st_size)


def _normalize_path(path: str) -> str:
    return os.path.abspath(path)


def _resolve_db_path(path: str) -> str:
    return os.path.join(os.path.dirname(path), "runtime_cache.db")


def _invalidate_source_cache_sqlite_ready(db_path: str) -> None:
    db_key = normalize_sqlite_db_key(db_path)
    with _SOURCE_SQLITE_READY_LOCK:
        _SOURCE_SQLITE_READY.discard(db_key)


def _is_missing_table_error(error: Exception) -> bool:
    return is_sqlite_missing_table_error(error, table_names="signal_tracker_source_cache")


def _recover_source_cache_sqlite_schema(db_path: str, logger: logging.Logger | None) -> bool:
    _invalidate_source_cache_sqlite_ready(db_path)
    return _ensure_source_cache_sqlite(db_path, logger)


def _serialize_usecols(usecols: list[str] | tuple[str, ...] | None) -> str:
    if usecols is None:
        return "[]"
    return json.dumps([str(column) for column in usecols], ensure_ascii=False, separators=(",", ":"))


def _serialize_dtype(dtype: dict[str, Any] | None) -> str:
    if not dtype:
        return "{}"
    normalized = {str(key): str(value) for key, value in sorted(dtype.items(), key=lambda item: str(item[0]))}
    return json.dumps(normalized, ensure_ascii=False, separators=(",", ":"))


def clear_signal_tracker_source_cache(*, reset_sqlite_state: bool = False) -> None:
    with _SOURCE_CACHE_LOCK:
        _SOURCE_CACHE.clear()

    if reset_sqlite_state:
        with _SOURCE_SQLITE_READY_LOCK:
            _SOURCE_SQLITE_READY.clear()


def _ensure_source_cache_sqlite(db_path: str, logger: logging.Logger | None) -> bool:
    db_key = normalize_sqlite_db_key(db_path)
    with _SOURCE_SQLITE_READY_LOCK:
        if db_key in _SOURCE_SQLITE_READY:
            if sqlite_db_path_exists(db_path):
                return True
            _SOURCE_SQLITE_READY.discard(db_key)

        def _initialize_schema() -> None:
            with connect_sqlite(
                db_path,
                timeout_seconds=30,
                pragmas=_SOURCE_SQLITE_INIT_PRAGMAS,
            ) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS signal_tracker_source_cache (
                        source_path TEXT NOT NULL,
                        cache_kind TEXT NOT NULL,
                        usecols_signature TEXT NOT NULL,
                        dtype_signature TEXT NOT NULL,
                        mtime_ns INTEGER NOT NULL,
                        size INTEGER NOT NULL,
                        payload_json TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        PRIMARY KEY (source_path, cache_kind, usecols_signature, dtype_signature)
                    )
                    """
                )
                cursor.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_signal_tracker_source_cache_updated_at
                    ON signal_tracker_source_cache(updated_at DESC)
                    """
                )
                conn.commit()

        try:
            run_sqlite_with_retry(
                _initialize_schema,
                max_retries=_SOURCE_SQLITE_RETRY_ATTEMPTS,
                retry_delay_seconds=_SOURCE_SQLITE_RETRY_DELAY_SECONDS,
            )
            _SOURCE_SQLITE_READY.add(db_key)
            return True
        except Exception as error:
            if logger is not None:
                logger.debug("Failed to initialize signal tracker source sqlite cache: %s", error)
            return False


def _load_from_sqlite(
    *,
    path: str,
    cache_kind: str,
    usecols_signature: str,
    dtype_signature: str,
    signature: tuple[int, int],
    logger: logging.Logger | None,
) -> pd.DataFrame | None:
    db_path = _resolve_db_path(path)
    if not _ensure_source_cache_sqlite(db_path, logger):
        return None
    normalized_path = str(path)

    def _query_row() -> tuple[Any, ...] | None:
        with connect_sqlite(
            db_path,
            timeout_seconds=30,
            pragmas=_SOURCE_SQLITE_SESSION_PRAGMAS,
        ) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT payload_json
                FROM signal_tracker_source_cache
                WHERE source_path = ?
                  AND cache_kind = ?
                  AND usecols_signature = ?
                  AND dtype_signature = ?
                  AND mtime_ns = ?
                  AND size = ?
                LIMIT 1
                """,
                (
                    normalized_path,
                    cache_kind,
                    usecols_signature,
                    dtype_signature,
                    int(signature[0]),
                    int(signature[1]),
                ),
            )
            return cursor.fetchone()

    try:
        row = run_sqlite_with_retry(
            _query_row,
            max_retries=_SOURCE_SQLITE_RETRY_ATTEMPTS,
            retry_delay_seconds=_SOURCE_SQLITE_RETRY_DELAY_SECONDS,
        )
    except Exception as error:
        if _is_missing_table_error(error) and _recover_source_cache_sqlite_schema(db_path, logger):
            try:
                row = run_sqlite_with_retry(
                    _query_row,
                    max_retries=_SOURCE_SQLITE_RETRY_ATTEMPTS,
                    retry_delay_seconds=_SOURCE_SQLITE_RETRY_DELAY_SECONDS,
                )
            except Exception as retry_error:
                if logger is not None:
                    logger.debug(
                        "Failed to load signal tracker source cache from sqlite after schema recovery: %s",
                        retry_error,
                    )
                return None
        else:
            if logger is not None:
                logger.debug("Failed to load signal tracker source cache from sqlite: %s", error)
            return None

    try:
        if not row:
            return None
        payload_json = row[0]
        if not isinstance(payload_json, str) or not payload_json:
            return None
        loaded = pd.read_json(StringIO(payload_json), orient="split")
        if not isinstance(loaded, pd.DataFrame):
            return None
        return loaded
    except Exception as error:
        if logger is not None:
            logger.debug("Failed to load signal tracker source cache from sqlite: %s", error)
        return None


def _save_to_sqlite(
    *,
    path: str,
    cache_kind: str,
    usecols_signature: str,
    dtype_signature: str,
    signature: tuple[int, int],
    payload: pd.DataFrame,
    logger: logging.Logger | None,
) -> None:
    db_path = _resolve_db_path(path)
    if not _ensure_source_cache_sqlite(db_path, logger):
        return
    normalized_path = str(path)

    try:
        payload_json = payload.to_json(orient="split", force_ascii=False, date_format="iso")
    except Exception as error:
        if logger is not None:
            logger.debug("Failed to serialize signal tracker source cache payload: %s", error)
        return

    normalized_max_rows = max(1, int(_SOURCE_SQLITE_MAX_ROWS))

    def _prune_rows_if_needed(cursor: sqlite3.Cursor) -> None:
        prune_rows_by_updated_at_if_needed(
            cursor,
            table_name="signal_tracker_source_cache",
            max_rows=normalized_max_rows,
        )

    def _upsert_payload() -> None:
        with connect_sqlite(
            db_path,
            timeout_seconds=30,
            pragmas=_SOURCE_SQLITE_SESSION_PRAGMAS,
        ) as conn:
            now_iso = datetime.now().isoformat()
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO signal_tracker_source_cache (
                    source_path,
                    cache_kind,
                    usecols_signature,
                    dtype_signature,
                    mtime_ns,
                    size,
                    payload_json,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(source_path, cache_kind, usecols_signature, dtype_signature) DO UPDATE SET
                    mtime_ns = excluded.mtime_ns,
                    size = excluded.size,
                    payload_json = excluded.payload_json,
                    updated_at = excluded.updated_at
                """,
                (
                    normalized_path,
                    cache_kind,
                    usecols_signature,
                    dtype_signature,
                    int(signature[0]),
                    int(signature[1]),
                    payload_json,
                    now_iso,
                ),
            )
            _prune_rows_if_needed(cursor)
            conn.commit()

    try:
        run_sqlite_with_retry(
            _upsert_payload,
            max_retries=_SOURCE_SQLITE_RETRY_ATTEMPTS,
            retry_delay_seconds=_SOURCE_SQLITE_RETRY_DELAY_SECONDS,
        )
    except Exception as error:
        if _is_missing_table_error(error) and _recover_source_cache_sqlite_schema(db_path, logger):
            try:
                run_sqlite_with_retry(
                    _upsert_payload,
                    max_retries=_SOURCE_SQLITE_RETRY_ATTEMPTS,
                    retry_delay_seconds=_SOURCE_SQLITE_RETRY_DELAY_SECONDS,
                )
            except Exception as retry_error:
                if logger is not None:
                    logger.debug(
                        "Failed to save signal tracker source cache to sqlite after schema recovery: %s",
                        retry_error,
                    )
        else:
            if logger is not None:
                logger.debug("Failed to save signal tracker source cache to sqlite: %s", error)


def load_signal_tracker_csv_cached(
    *,
    path: str,
    cache_kind: str,
    usecols: list[str] | tuple[str, ...] | None = None,
    dtype: dict[str, Any] | None = None,
    read_csv: Callable[..., pd.DataFrame] = pd.read_csv,
    logger: logging.Logger | None = None,
    low_memory: bool = False,
    fallback_without_usecols: bool = True,
    deep_copy: bool = True,
) -> pd.DataFrame:
    path_abs = _normalize_path(path)
    signature = _file_signature(path_abs)
    if signature is None:
        return pd.DataFrame()

    usecols_signature = _serialize_usecols(usecols)
    dtype_signature = _serialize_dtype(dtype)
    cache_key = (path_abs, cache_kind, usecols_signature, dtype_signature)

    with _SOURCE_CACHE_LOCK:
        cached = _SOURCE_CACHE.get(cache_key)
        if cached and cached[0] == signature:
            return cached[1].copy(deep=deep_copy)

    sqlite_cached = _load_from_sqlite(
        path=path_abs,
        cache_kind=cache_kind,
        usecols_signature=usecols_signature,
        dtype_signature=dtype_signature,
        signature=signature,
        logger=logger,
    )
    if sqlite_cached is not None:
        with _SOURCE_CACHE_LOCK:
            _SOURCE_CACHE[cache_key] = (signature, sqlite_cached)
        return sqlite_cached.copy(deep=deep_copy)

    read_kwargs: dict[str, Any] = {"low_memory": low_memory}
    if usecols is not None:
        read_kwargs["usecols"] = [str(column) for column in usecols]
    if dtype is not None:
        read_kwargs["dtype"] = dtype

    try:
        loaded = read_csv(path_abs, **read_kwargs)
    except ValueError:
        if not fallback_without_usecols or usecols is None:
            raise
        fallback_kwargs = dict(read_kwargs)
        fallback_kwargs.pop("usecols", None)
        loaded = read_csv(path_abs, **fallback_kwargs)

    refreshed_signature = _file_signature(path_abs)
    if refreshed_signature is None:
        return loaded.copy(deep=deep_copy)

    with _SOURCE_CACHE_LOCK:
        _SOURCE_CACHE[cache_key] = (refreshed_signature, loaded)
    _save_to_sqlite(
        path=path_abs,
        cache_kind=cache_kind,
        usecols_signature=usecols_signature,
        dtype_signature=dtype_signature,
        signature=refreshed_signature,
        payload=loaded,
        logger=logger,
    )
    return loaded.copy(deep=deep_copy)
