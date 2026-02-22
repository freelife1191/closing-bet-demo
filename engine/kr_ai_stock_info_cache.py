#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KR AI 종목정보 캐시(SQLite + 메모리).
"""

from __future__ import annotations

import copy
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


_STOCK_INFO_CACHE_LOCK = threading.Lock()
_STOCK_INFO_CACHE: dict[str, tuple[tuple[int, int], dict[str, object]]] = {}
_STOCK_INFO_SQLITE_READY_LOCK = threading.Lock()
_STOCK_INFO_SQLITE_READY: set[str] = set()
_STOCK_INFO_SQLITE_MAX_ROWS = 512
_STOCK_INFO_SQLITE_INIT_PRAGMAS = build_sqlite_pragmas(busy_timeout_ms=30_000)
_STOCK_INFO_SQLITE_SESSION_PRAGMAS = build_sqlite_pragmas(busy_timeout_ms=30_000)
_STOCK_INFO_SQLITE_RETRY_ATTEMPTS = 2
_STOCK_INFO_SQLITE_RETRY_DELAY_SECONDS = 0.03


def _stock_info_cache_key(signals_file: str, ticker: str) -> str:
    return f"{os.path.abspath(signals_file)}::{str(ticker)}"


def resolve_stock_info_cache_db_path(signals_file: str) -> str:
    return os.path.join(os.path.dirname(signals_file), "runtime_cache.db")


def _invalidate_stock_info_sqlite_ready(db_path: str) -> None:
    db_key = normalize_sqlite_db_key(db_path)
    with _STOCK_INFO_SQLITE_READY_LOCK:
        _STOCK_INFO_SQLITE_READY.discard(db_key)


def _is_missing_table_error(error: Exception) -> bool:
    return is_sqlite_missing_table_error(error, table_names="kr_ai_stock_info_cache")


def _recover_stock_info_sqlite_schema(db_path: str, logger: Any) -> bool:
    _invalidate_stock_info_sqlite_ready(db_path)
    return _ensure_stock_info_sqlite(db_path, logger)


def _ensure_stock_info_sqlite(db_path: str, logger: Any) -> bool:
    db_key = normalize_sqlite_db_key(db_path)
    with _STOCK_INFO_SQLITE_READY_LOCK:
        if db_key in _STOCK_INFO_SQLITE_READY:
            if sqlite_db_path_exists(db_path):
                return True
            _STOCK_INFO_SQLITE_READY.discard(db_key)

        def _initialize_schema() -> None:
            with connect_sqlite(
                db_path,
                timeout_seconds=30,
                pragmas=_STOCK_INFO_SQLITE_INIT_PRAGMAS,
            ) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS kr_ai_stock_info_cache (
                        signals_path TEXT NOT NULL,
                        ticker TEXT NOT NULL,
                        mtime_ns INTEGER NOT NULL,
                        size INTEGER NOT NULL,
                        payload_json TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        PRIMARY KEY (signals_path, ticker)
                    )
                    """
                )
                cursor.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_kr_ai_stock_info_cache_updated_at
                    ON kr_ai_stock_info_cache(updated_at DESC)
                    """
                )
                conn.commit()

        try:
            run_sqlite_with_retry(
                _initialize_schema,
                max_retries=_STOCK_INFO_SQLITE_RETRY_ATTEMPTS,
                retry_delay_seconds=_STOCK_INFO_SQLITE_RETRY_DELAY_SECONDS,
            )
            _STOCK_INFO_SQLITE_READY.add(db_key)
            return True
        except Exception as error:
            logger.debug("Failed to initialize KR AI stock info sqlite cache: %s", error)
            return False


def _load_stock_info_from_sqlite(
    *,
    signals_file: str,
    ticker: str,
    signature: tuple[int, int],
    logger: Any,
    resolve_db_path_fn: Callable[[str], str],
) -> dict[str, object] | None:
    db_path = resolve_db_path_fn(signals_file)
    if not _ensure_stock_info_sqlite(db_path, logger):
        return None
    normalized_signals_path = os.path.abspath(signals_file)
    normalized_ticker = str(ticker)

    def _query_payload() -> tuple[Any, ...] | None:
        with connect_sqlite(
            db_path,
            timeout_seconds=30,
            pragmas=_STOCK_INFO_SQLITE_SESSION_PRAGMAS,
        ) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT payload_json
                FROM kr_ai_stock_info_cache
                WHERE signals_path = ?
                  AND ticker = ?
                  AND mtime_ns = ?
                  AND size = ?
                LIMIT 1
                """,
                (
                    normalized_signals_path,
                    normalized_ticker,
                    int(signature[0]),
                    int(signature[1]),
                ),
            )
            return cursor.fetchone()

    try:
        row = run_sqlite_with_retry(
            _query_payload,
            max_retries=_STOCK_INFO_SQLITE_RETRY_ATTEMPTS,
            retry_delay_seconds=_STOCK_INFO_SQLITE_RETRY_DELAY_SECONDS,
        )
    except Exception as error:
        if _is_missing_table_error(error) and _recover_stock_info_sqlite_schema(db_path, logger):
            try:
                row = run_sqlite_with_retry(
                    _query_payload,
                    max_retries=_STOCK_INFO_SQLITE_RETRY_ATTEMPTS,
                    retry_delay_seconds=_STOCK_INFO_SQLITE_RETRY_DELAY_SECONDS,
                )
            except Exception as retry_error:
                logger.debug("Failed to load KR AI stock info sqlite cache after schema recovery: %s", retry_error)
                return None
        else:
            logger.debug("Failed to load KR AI stock info sqlite cache: %s", error)
            return None

    try:
        if not row:
            return None
        payload = json.loads(row[0])
        return payload if isinstance(payload, dict) else None
    except Exception as error:
        logger.debug("Failed to load KR AI stock info sqlite cache: %s", error)
        return None


def _save_stock_info_to_sqlite(
    *,
    signals_file: str,
    ticker: str,
    signature: tuple[int, int],
    payload: dict[str, object],
    logger: Any,
    resolve_db_path_fn: Callable[[str], str],
) -> None:
    db_path = resolve_db_path_fn(signals_file)
    if not _ensure_stock_info_sqlite(db_path, logger):
        return
    normalized_signals_path = os.path.abspath(signals_file)
    normalized_ticker = str(ticker)

    try:
        payload_json = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    except Exception as error:
        logger.debug("Failed to serialize KR AI stock info cache: %s", error)
        return

    normalized_max_rows = max(1, int(_STOCK_INFO_SQLITE_MAX_ROWS))

    def _prune_rows_if_needed(cursor: sqlite3.Cursor) -> None:
        prune_rows_by_updated_at_if_needed(
            cursor,
            table_name="kr_ai_stock_info_cache",
            max_rows=normalized_max_rows,
        )

    def _upsert_payload() -> None:
        with connect_sqlite(
            db_path,
            timeout_seconds=30,
            pragmas=_STOCK_INFO_SQLITE_SESSION_PRAGMAS,
        ) as conn:
            now_iso = datetime.now().isoformat()
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO kr_ai_stock_info_cache (
                    signals_path,
                    ticker,
                    mtime_ns,
                    size,
                    payload_json,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(signals_path, ticker) DO UPDATE SET
                    mtime_ns = excluded.mtime_ns,
                    size = excluded.size,
                    payload_json = excluded.payload_json,
                    updated_at = excluded.updated_at
                """,
                (
                    normalized_signals_path,
                    normalized_ticker,
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
            max_retries=_STOCK_INFO_SQLITE_RETRY_ATTEMPTS,
            retry_delay_seconds=_STOCK_INFO_SQLITE_RETRY_DELAY_SECONDS,
        )
    except Exception as error:
        if _is_missing_table_error(error) and _recover_stock_info_sqlite_schema(db_path, logger):
            try:
                run_sqlite_with_retry(
                    _upsert_payload,
                    max_retries=_STOCK_INFO_SQLITE_RETRY_ATTEMPTS,
                    retry_delay_seconds=_STOCK_INFO_SQLITE_RETRY_DELAY_SECONDS,
                )
            except Exception as retry_error:
                logger.debug("Failed to save KR AI stock info sqlite cache after schema recovery: %s", retry_error)
        else:
            logger.debug("Failed to save KR AI stock info sqlite cache: %s", error)


def load_cached_stock_info(
    *,
    signals_file: str,
    ticker: str,
    signature: tuple[int, int],
    logger: Any,
    resolve_db_path_fn: Callable[[str], str] = resolve_stock_info_cache_db_path,
) -> dict[str, object] | None:
    cache_key = _stock_info_cache_key(signals_file, ticker)
    with _STOCK_INFO_CACHE_LOCK:
        cached = _STOCK_INFO_CACHE.get(cache_key)
        if cached and cached[0] == signature:
            return copy.deepcopy(cached[1])

    sqlite_cached = _load_stock_info_from_sqlite(
        signals_file=signals_file,
        ticker=ticker,
        signature=signature,
        logger=logger,
        resolve_db_path_fn=resolve_db_path_fn,
    )
    if sqlite_cached is None:
        return None

    with _STOCK_INFO_CACHE_LOCK:
        _STOCK_INFO_CACHE[cache_key] = (signature, dict(sqlite_cached))
    return copy.deepcopy(sqlite_cached)


def save_cached_stock_info(
    *,
    signals_file: str,
    ticker: str,
    signature: tuple[int, int],
    payload: dict[str, object],
    logger: Any,
    resolve_db_path_fn: Callable[[str], str] = resolve_stock_info_cache_db_path,
) -> None:
    cache_key = _stock_info_cache_key(signals_file, ticker)
    with _STOCK_INFO_CACHE_LOCK:
        _STOCK_INFO_CACHE[cache_key] = (signature, dict(payload))

    _save_stock_info_to_sqlite(
        signals_file=signals_file,
        ticker=ticker,
        signature=signature,
        payload=payload,
        logger=logger,
        resolve_db_path_fn=resolve_db_path_fn,
    )


def clear_stock_info_cache() -> None:
    with _STOCK_INFO_CACHE_LOCK:
        _STOCK_INFO_CACHE.clear()
