#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KR Market Realtime Market Map Cache
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import threading
from datetime import datetime
from typing import Callable

import pandas as pd

from services.kr_market_csv_utils import load_csv_readonly as _load_csv_readonly
from services.sqlite_utils import (
    build_sqlite_pragmas,
    connect_sqlite,
    prune_rows_by_updated_at_if_needed,
)


_MARKET_MAP_CACHE_LOCK = threading.Lock()
_MARKET_MAP_CACHE: dict[tuple[str, int, int], dict[str, str]] = {}
_MARKET_MAP_SQLITE_READY: set[str] = set()
_MARKET_MAP_SQLITE_LOCK = threading.Lock()
_MARKET_MAP_SQLITE_MAX_ROWS = 200
_MARKET_MAP_SQLITE_INIT_PRAGMAS = build_sqlite_pragmas(busy_timeout_ms=5_000)
_MARKET_MAP_SQLITE_SESSION_PRAGMAS = build_sqlite_pragmas(busy_timeout_ms=5_000)


def _file_signature(path: str) -> tuple[int, int] | None:
    try:
        stat = os.stat(path)
    except OSError:
        return None
    return int(stat.st_mtime_ns), int(stat.st_size)


def _resolve_market_map_source_path(get_data_path: Callable[[str], str] | None) -> str | None:
    if get_data_path is None:
        return None
    try:
        return str(get_data_path("korean_stocks_list.csv"))
    except Exception:
        return None


def _resolve_market_map_cache_db_path(source_path: str) -> str:
    source_dir = os.path.dirname(source_path) or "."
    return os.path.join(source_dir, "runtime_cache.db")


def _invalidate_market_map_sqlite_ready(db_path: str) -> None:
    with _MARKET_MAP_SQLITE_LOCK:
        _MARKET_MAP_SQLITE_READY.discard(db_path)


def _is_missing_table_error(error: Exception) -> bool:
    if not isinstance(error, sqlite3.OperationalError):
        return False
    message = str(error).lower()
    return "no such table" in message and "realtime_market_map_cache" in message


def _recover_market_map_sqlite_schema(db_path: str, logger: logging.Logger | None) -> bool:
    _invalidate_market_map_sqlite_ready(db_path)
    return _ensure_market_map_sqlite(db_path, logger)


def _ensure_market_map_sqlite(db_path: str, logger: logging.Logger | None) -> bool:
    with _MARKET_MAP_SQLITE_LOCK:
        if db_path in _MARKET_MAP_SQLITE_READY:
            if os.path.exists(db_path):
                return True
            _MARKET_MAP_SQLITE_READY.discard(db_path)
        try:
            with connect_sqlite(
                db_path,
                timeout_seconds=5,
                pragmas=_MARKET_MAP_SQLITE_INIT_PRAGMAS,
            ) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS realtime_market_map_cache (
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
                    CREATE INDEX IF NOT EXISTS idx_realtime_market_map_cache_updated_at
                    ON realtime_market_map_cache(updated_at DESC)
                    """
                )
                conn.commit()
            _MARKET_MAP_SQLITE_READY.add(db_path)
            return True
        except Exception as error:
            if logger is not None:
                logger.debug(f"Failed to initialize market map sqlite cache: {error}")
            return False


def _load_market_map_from_sqlite(
    *,
    source_path: str,
    signature: tuple[int, int],
    logger: logging.Logger | None,
) -> dict[str, str] | None:
    db_path = _resolve_market_map_cache_db_path(source_path)
    if not _ensure_market_map_sqlite(db_path, logger):
        return None

    def _query_payload() -> tuple[object, ...] | None:
        with connect_sqlite(
            db_path,
            timeout_seconds=5,
            pragmas=_MARKET_MAP_SQLITE_SESSION_PRAGMAS,
        ) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT payload_json
                FROM realtime_market_map_cache
                WHERE source_path = ?
                  AND mtime_ns = ?
                  AND size_bytes = ?
                LIMIT 1
                """,
                (source_path, int(signature[0]), int(signature[1])),
            )
            return cursor.fetchone()

    try:
        row = _query_payload()
    except Exception as error:
        if _is_missing_table_error(error) and _recover_market_map_sqlite_schema(db_path, logger):
            try:
                row = _query_payload()
            except Exception as retry_error:
                if logger is not None:
                    logger.debug("Failed to load market map sqlite cache after schema recovery: %s", retry_error)
                return None
        else:
            if logger is not None:
                logger.debug("Failed to load market map sqlite cache: %s", error)
            return None

    try:
        if row is None:
            return None
        loaded = json.loads(str(row[0]))
        if not isinstance(loaded, dict):
            return None
        return {str(key): str(value) for key, value in loaded.items()}
    except Exception as error:
        if logger is not None:
            logger.debug("Failed to load market map sqlite cache: %s", error)
        return None


def _prune_market_map_cache_if_needed(
    cursor: sqlite3.Cursor,
    *,
    max_rows: int,
) -> None:
    normalized_max_rows = max(1, int(max_rows))
    prune_rows_by_updated_at_if_needed(
        cursor,
        table_name="realtime_market_map_cache",
        max_rows=normalized_max_rows,
    )


def _save_market_map_to_sqlite(
    *,
    source_path: str,
    signature: tuple[int, int],
    market_map: dict[str, str],
    logger: logging.Logger | None,
) -> None:
    db_path = _resolve_market_map_cache_db_path(source_path)
    if not _ensure_market_map_sqlite(db_path, logger):
        return

    normalized_max_rows = max(1, int(_MARKET_MAP_SQLITE_MAX_ROWS))
    try:
        payload_json = json.dumps(market_map, ensure_ascii=False, separators=(",", ":"))
    except Exception as error:
        if logger is not None:
            logger.debug("Failed to serialize market map sqlite cache payload: %s", error)
        return

    def _upsert_payload() -> None:
        with connect_sqlite(
            db_path,
            timeout_seconds=5,
            pragmas=_MARKET_MAP_SQLITE_SESSION_PRAGMAS,
        ) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO realtime_market_map_cache (
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
            _prune_market_map_cache_if_needed(
                cursor,
                max_rows=normalized_max_rows,
            )
            conn.commit()

    try:
        _upsert_payload()
    except Exception as error:
        if _is_missing_table_error(error) and _recover_market_map_sqlite_schema(db_path, logger):
            try:
                _upsert_payload()
            except Exception as retry_error:
                if logger is not None:
                    logger.debug("Failed to save market map sqlite cache after schema recovery: %s", retry_error)
        else:
            if logger is not None:
                logger.debug("Failed to save market map sqlite cache: %s", error)


def clear_market_map_cache() -> None:
    with _MARKET_MAP_CACHE_LOCK:
        _MARKET_MAP_CACHE.clear()


def build_market_map(
    load_csv_file: Callable[[str], pd.DataFrame],
    logger: logging.Logger | None = None,
    get_data_path: Callable[[str], str] | None = None,
) -> dict[str, str]:
    source_path = _resolve_market_map_source_path(get_data_path)
    signature = _file_signature(source_path) if source_path else None

    cache_key: tuple[str, int, int] | None = None
    if source_path and signature is not None:
        cache_key = (source_path, int(signature[0]), int(signature[1]))
        with _MARKET_MAP_CACHE_LOCK:
            cached = _MARKET_MAP_CACHE.get(cache_key)
        if cached is not None:
            return dict(cached)

        sqlite_cached = _load_market_map_from_sqlite(
            source_path=source_path,
            signature=signature,
            logger=logger,
        )
        if sqlite_cached is not None:
            with _MARKET_MAP_CACHE_LOCK:
                _MARKET_MAP_CACHE.clear()
                _MARKET_MAP_CACHE[cache_key] = dict(sqlite_cached)
            return dict(sqlite_cached)

    try:
        stocks_df = _load_csv_readonly(
            load_csv_file,
            "korean_stocks_list.csv",
            usecols=["ticker", "market"],
        )
    except Exception as error:
        if logger is not None:
            logger.debug(f"Failed to load market map source: {error}")
        return {}

    if stocks_df.empty:
        return {}
    if "ticker" not in stocks_df.columns or "market" not in stocks_df.columns:
        return {}

    mapped = stocks_df.loc[:, ["ticker", "market"]].dropna(subset=["ticker", "market"]).copy()
    if mapped.empty:
        return {}

    mapped["ticker"] = mapped["ticker"].astype(str).str.zfill(6)
    mapped = mapped.drop_duplicates(subset=["ticker"], keep="last")
    result = dict(zip(mapped["ticker"], mapped["market"]))

    if cache_key is not None and signature is not None and source_path:
        with _MARKET_MAP_CACHE_LOCK:
            _MARKET_MAP_CACHE.clear()
            _MARKET_MAP_CACHE[cache_key] = dict(result)
        _save_market_map_to_sqlite(
            source_path=source_path,
            signature=signature,
            market_map=result,
            logger=logger,
        )

    return result
