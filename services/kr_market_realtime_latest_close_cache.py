#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KR Market realtime latest-close cache helpers.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import threading
from collections.abc import Callable
from datetime import datetime
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


_LATEST_CLOSE_MAP_CACHE_LOCK = threading.Lock()
_LATEST_CLOSE_MAP_CACHE: dict[tuple[str, int, int], dict[str, float]] = {}
_LATEST_CLOSE_MAP_SQLITE_READY: set[str] = set()
_LATEST_CLOSE_MAP_SQLITE_LOCK = threading.Lock()
_LATEST_CLOSE_MAP_SQLITE_MAX_ROWS = 200
_LATEST_CLOSE_MAP_SQLITE_INIT_PRAGMAS = build_sqlite_pragmas(busy_timeout_ms=5_000)
_LATEST_CLOSE_MAP_SQLITE_SESSION_PRAGMAS = build_sqlite_pragmas(busy_timeout_ms=5_000)
_LATEST_CLOSE_MAP_SQLITE_RETRY_ATTEMPTS = 2
_LATEST_CLOSE_MAP_SQLITE_RETRY_DELAY_SECONDS = 0.03


def _file_signature(path: str) -> tuple[int, int] | None:
    try:
        stat = os.stat(path)
    except OSError:
        return None
    return int(stat.st_mtime_ns), int(stat.st_size)


def _resolve_daily_prices_source_path(get_data_path: Callable[[str], str] | None) -> str | None:
    if get_data_path is None:
        return None
    try:
        return str(get_data_path("daily_prices.csv"))
    except Exception:
        return None


def _resolve_latest_close_map_cache_db_path(source_path: str) -> str:
    source_dir = os.path.dirname(source_path) or "."
    return os.path.join(source_dir, "runtime_cache.db")


def _invalidate_latest_close_map_sqlite_ready(db_path: str) -> None:
    db_key = normalize_sqlite_db_key(db_path)
    with _LATEST_CLOSE_MAP_SQLITE_LOCK:
        _LATEST_CLOSE_MAP_SQLITE_READY.discard(db_key)


def _is_missing_table_error(error: Exception) -> bool:
    return is_sqlite_missing_table_error(error, table_names="realtime_latest_close_map_cache")


def _recover_latest_close_map_sqlite_schema(db_path: str, logger: logging.Logger | None) -> bool:
    _invalidate_latest_close_map_sqlite_ready(db_path)
    return _ensure_latest_close_map_sqlite(db_path, logger)


def _ensure_latest_close_map_sqlite(db_path: str, logger: logging.Logger | None) -> bool:
    db_key = normalize_sqlite_db_key(db_path)
    with _LATEST_CLOSE_MAP_SQLITE_LOCK:
        if db_key in _LATEST_CLOSE_MAP_SQLITE_READY:
            if sqlite_db_path_exists(db_path):
                return True
            _LATEST_CLOSE_MAP_SQLITE_READY.discard(db_key)

        def _initialize_schema() -> None:
            with connect_sqlite(
                db_path,
                timeout_seconds=5,
                pragmas=_LATEST_CLOSE_MAP_SQLITE_INIT_PRAGMAS,
            ) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS realtime_latest_close_map_cache (
                        source_path TEXT PRIMARY KEY,
                        mtime_ns INTEGER NOT NULL,
                        size_bytes INTEGER NOT NULL,
                        payload_json TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    )
                    """
                )
                cursor.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_realtime_latest_close_map_cache_updated_at
                    ON realtime_latest_close_map_cache(updated_at DESC)
                    """
                )
                conn.commit()
        try:
            run_sqlite_with_retry(
                _initialize_schema,
                max_retries=_LATEST_CLOSE_MAP_SQLITE_RETRY_ATTEMPTS,
                retry_delay_seconds=_LATEST_CLOSE_MAP_SQLITE_RETRY_DELAY_SECONDS,
            )
            _LATEST_CLOSE_MAP_SQLITE_READY.add(db_key)
            return True
        except Exception as error:
            if logger is not None:
                logger.debug(f"Failed to initialize latest-close sqlite cache: {error}")
            return False


def _load_latest_close_map_from_sqlite(
    *,
    source_path: str,
    signature: tuple[int, int],
    logger: logging.Logger | None,
) -> dict[str, float] | None:
    db_path = _resolve_latest_close_map_cache_db_path(source_path)
    if not _ensure_latest_close_map_sqlite(db_path, logger):
        return None

    def _query_payload() -> tuple[Any, ...] | None:
        with connect_sqlite(
            db_path,
            timeout_seconds=5,
            pragmas=_LATEST_CLOSE_MAP_SQLITE_SESSION_PRAGMAS,
        ) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT payload_json
                FROM realtime_latest_close_map_cache
                WHERE source_path = ?
                  AND mtime_ns = ?
                  AND size_bytes = ?
                LIMIT 1
                """,
                (source_path, int(signature[0]), int(signature[1])),
            )
            return cursor.fetchone()

    try:
        row = run_sqlite_with_retry(
            _query_payload,
            max_retries=_LATEST_CLOSE_MAP_SQLITE_RETRY_ATTEMPTS,
            retry_delay_seconds=_LATEST_CLOSE_MAP_SQLITE_RETRY_DELAY_SECONDS,
        )
    except Exception as error:
        if _is_missing_table_error(error) and _recover_latest_close_map_sqlite_schema(db_path, logger):
            try:
                row = run_sqlite_with_retry(
                    _query_payload,
                    max_retries=_LATEST_CLOSE_MAP_SQLITE_RETRY_ATTEMPTS,
                    retry_delay_seconds=_LATEST_CLOSE_MAP_SQLITE_RETRY_DELAY_SECONDS,
                )
            except Exception as retry_error:
                if logger is not None:
                    logger.debug("Failed to load latest-close sqlite cache after schema recovery: %s", retry_error)
                return None
        else:
            if logger is not None:
                logger.debug("Failed to load latest-close sqlite cache: %s", error)
            return None

    try:
        if row is None:
            return None
        loaded = json.loads(str(row[0]))
        if not isinstance(loaded, dict):
            return None
        normalized: dict[str, float] = {}
        for key, value in loaded.items():
            try:
                normalized[str(key)] = float(value or 0)
            except (TypeError, ValueError):
                normalized[str(key)] = 0.0
        return normalized
    except Exception as error:
        if logger is not None:
            logger.debug("Failed to load latest-close sqlite cache: %s", error)
        return None


def _prune_latest_close_cache_if_needed(
    cursor: sqlite3.Cursor,
    *,
    max_rows: int,
) -> None:
    normalized_max_rows = max(1, int(max_rows))
    prune_rows_by_updated_at_if_needed(
        cursor,
        table_name="realtime_latest_close_map_cache",
        max_rows=normalized_max_rows,
    )


def _save_latest_close_map_to_sqlite(
    *,
    source_path: str,
    signature: tuple[int, int],
    latest_close_map: dict[str, float],
    logger: logging.Logger | None,
) -> None:
    db_path = _resolve_latest_close_map_cache_db_path(source_path)
    if not _ensure_latest_close_map_sqlite(db_path, logger):
        return

    normalized_max_rows = max(1, int(_LATEST_CLOSE_MAP_SQLITE_MAX_ROWS))
    try:
        payload_json = json.dumps(latest_close_map, ensure_ascii=False, separators=(",", ":"))
    except Exception as error:
        if logger is not None:
            logger.debug("Failed to serialize latest-close sqlite cache payload: %s", error)
        return

    def _upsert_payload() -> None:
        with connect_sqlite(
            db_path,
            timeout_seconds=5,
            pragmas=_LATEST_CLOSE_MAP_SQLITE_SESSION_PRAGMAS,
        ) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO realtime_latest_close_map_cache (
                    source_path, mtime_ns, size_bytes, payload_json, updated_at
                )
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(source_path) DO UPDATE SET
                    mtime_ns = excluded.mtime_ns,
                    size_bytes = excluded.size_bytes,
                    payload_json = excluded.payload_json,
                    updated_at = excluded.updated_at
                """,
                (
                    source_path,
                    int(signature[0]),
                    int(signature[1]),
                    payload_json,
                    datetime.now().isoformat(),
                ),
            )
            _prune_latest_close_cache_if_needed(
                cursor,
                max_rows=normalized_max_rows,
            )
            conn.commit()

    try:
        run_sqlite_with_retry(
            _upsert_payload,
            max_retries=_LATEST_CLOSE_MAP_SQLITE_RETRY_ATTEMPTS,
            retry_delay_seconds=_LATEST_CLOSE_MAP_SQLITE_RETRY_DELAY_SECONDS,
        )
    except Exception as error:
        if _is_missing_table_error(error) and _recover_latest_close_map_sqlite_schema(db_path, logger):
            try:
                run_sqlite_with_retry(
                    _upsert_payload,
                    max_retries=_LATEST_CLOSE_MAP_SQLITE_RETRY_ATTEMPTS,
                    retry_delay_seconds=_LATEST_CLOSE_MAP_SQLITE_RETRY_DELAY_SECONDS,
                )
            except Exception as retry_error:
                if logger is not None:
                    logger.debug("Failed to save latest-close sqlite cache after schema recovery: %s", retry_error)
        else:
            if logger is not None:
                logger.debug("Failed to save latest-close sqlite cache: %s", error)


def clear_latest_close_map_cache() -> None:
    with _LATEST_CLOSE_MAP_CACHE_LOCK:
        _LATEST_CLOSE_MAP_CACHE.clear()


def load_cached_latest_close_map(
    *,
    load_csv_file: Callable[[str], pd.DataFrame],
    get_data_path: Callable[[str], str] | None,
    load_csv_readonly: Callable[..., pd.DataFrame],
    build_latest_prices_from_dataframe: Callable[[pd.DataFrame], dict[str, float]],
    logger: logging.Logger | None,
) -> dict[str, float] | None:
    source_path = _resolve_daily_prices_source_path(get_data_path)
    if not source_path:
        return None

    signature = _file_signature(source_path)
    if signature is None:
        return None

    cache_key = (source_path, int(signature[0]), int(signature[1]))
    with _LATEST_CLOSE_MAP_CACHE_LOCK:
        cached = _LATEST_CLOSE_MAP_CACHE.get(cache_key)
    if cached is not None:
        return dict(cached)

    sqlite_cached = _load_latest_close_map_from_sqlite(
        source_path=source_path,
        signature=signature,
        logger=logger,
    )
    if sqlite_cached is not None:
        with _LATEST_CLOSE_MAP_CACHE_LOCK:
            _LATEST_CLOSE_MAP_CACHE.clear()
            _LATEST_CLOSE_MAP_CACHE[cache_key] = dict(sqlite_cached)
        return dict(sqlite_cached)

    try:
        df_prices = load_csv_readonly(
            load_csv_file,
            "daily_prices.csv",
            usecols=["date", "ticker", "close"],
        )
    except Exception as error:
        if logger is not None:
            logger.debug(f"Failed to load daily_prices for latest-close cache: {error}")
        return None

    if df_prices.empty or "ticker" not in df_prices.columns or "close" not in df_prices.columns:
        return None

    latest_prices = build_latest_prices_from_dataframe(df_prices)
    with _LATEST_CLOSE_MAP_CACHE_LOCK:
        _LATEST_CLOSE_MAP_CACHE.clear()
        _LATEST_CLOSE_MAP_CACHE[cache_key] = dict(latest_prices)
    _save_latest_close_map_to_sqlite(
        source_path=source_path,
        signature=signature,
        latest_close_map=latest_prices,
        logger=logger,
    )
    return dict(latest_prices)
