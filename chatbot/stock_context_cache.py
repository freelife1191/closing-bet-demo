#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
stock_context 결과 문자열 캐시(SQLite + 메모리).
"""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from threading import Lock

from services.sqlite_utils import (
    build_sqlite_pragmas,
    connect_sqlite,
    is_sqlite_missing_table_error,
    normalize_sqlite_db_key,
    prune_rows_by_updated_at_if_needed,
    run_sqlite_with_retry,
    sqlite_db_path_exists,
)


LOGGER = logging.getLogger(__name__)

_RESULT_TEXT_CACHE_LOCK = Lock()
_RESULT_TEXT_CACHE: dict[str, tuple[tuple[int, int], str]] = {}
_RESULT_TEXT_SQLITE_LOCK = Lock()
_RESULT_TEXT_SQLITE_READY: set[str] = set()
_RESULT_TEXT_MEMORY_MAX_ENTRIES = 2048
_RESULT_TEXT_SQLITE_MAX_ROWS = 1024
_RESULT_TEXT_SQLITE_TIMEOUT_SECONDS = 30
_RESULT_TEXT_SQLITE_RETRY_ATTEMPTS = 2
_RESULT_TEXT_SQLITE_RETRY_DELAY_SECONDS = 0.03
_RESULT_TEXT_SQLITE_PRAGMAS = build_sqlite_pragmas(
    busy_timeout_ms=_RESULT_TEXT_SQLITE_TIMEOUT_SECONDS * 1000,
)


def _build_result_cache_key(path: Path, *, dataset: str, ticker_padded: str) -> str:
    return f"{path}::{dataset}::{ticker_padded}"


def _resolve_runtime_cache_db_path(data_dir: Path) -> Path:
    return data_dir / "runtime_cache.db"


def _invalidate_result_text_sqlite_ready(db_path: Path) -> None:
    cache_key = normalize_sqlite_db_key(str(db_path))
    with _RESULT_TEXT_SQLITE_LOCK:
        _RESULT_TEXT_SQLITE_READY.discard(cache_key)


def _is_missing_table_error(error: Exception) -> bool:
    return is_sqlite_missing_table_error(error, table_names="chatbot_stock_context_cache")


def _recover_result_text_sqlite_schema(db_path: Path) -> bool:
    _invalidate_result_text_sqlite_ready(db_path)
    return _ensure_result_text_sqlite_cache(db_path)


def _ensure_result_text_sqlite_cache(db_path: Path) -> bool:
    db_path_text = str(db_path)
    cache_key = normalize_sqlite_db_key(db_path_text)
    with _RESULT_TEXT_SQLITE_LOCK:
        if cache_key in _RESULT_TEXT_SQLITE_READY:
            if sqlite_db_path_exists(db_path_text):
                return True
            _RESULT_TEXT_SQLITE_READY.discard(cache_key)

        def _initialize_schema() -> None:
            with connect_sqlite(
                db_path_text,
                timeout_seconds=_RESULT_TEXT_SQLITE_TIMEOUT_SECONDS,
                pragmas=_RESULT_TEXT_SQLITE_PRAGMAS,
            ) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS chatbot_stock_context_cache (
                        cache_key TEXT PRIMARY KEY,
                        dataset TEXT NOT NULL,
                        ticker TEXT NOT NULL,
                        mtime_ns INTEGER NOT NULL,
                        size INTEGER NOT NULL,
                        payload_text TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    )
                    """
                )
                cursor.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_chatbot_stock_context_cache_updated_at
                    ON chatbot_stock_context_cache(updated_at DESC)
                    """
                )
                conn.commit()

        try:
            run_sqlite_with_retry(
                _initialize_schema,
                max_retries=_RESULT_TEXT_SQLITE_RETRY_ATTEMPTS,
                retry_delay_seconds=_RESULT_TEXT_SQLITE_RETRY_DELAY_SECONDS,
            )

            _RESULT_TEXT_SQLITE_READY.add(cache_key)
            return True
        except Exception as exc:
            LOGGER.debug("Failed to initialize stock context sqlite cache (%s): %s", db_path, exc)
            return False


def _save_result_text_memory_entry(cache_key: str, signature: tuple[int, int], payload_text: str) -> None:
    max_entries = max(1, int(_RESULT_TEXT_MEMORY_MAX_ENTRIES))
    with _RESULT_TEXT_CACHE_LOCK:
        if cache_key in _RESULT_TEXT_CACHE:
            _RESULT_TEXT_CACHE.pop(cache_key, None)
        elif len(_RESULT_TEXT_CACHE) >= max_entries:
            oldest_key = next(iter(_RESULT_TEXT_CACHE))
            _RESULT_TEXT_CACHE.pop(oldest_key, None)
        _RESULT_TEXT_CACHE[cache_key] = (signature, payload_text)


def _load_result_text_from_sqlite(
    *,
    data_dir: Path,
    cache_key: str,
    signature: tuple[int, int],
) -> str | None:
    db_path = _resolve_runtime_cache_db_path(data_dir)
    if not _ensure_result_text_sqlite_cache(db_path):
        return None
    db_path_text = str(db_path)

    def _query_row() -> tuple[object, ...] | None:
        with connect_sqlite(
            db_path_text,
            timeout_seconds=_RESULT_TEXT_SQLITE_TIMEOUT_SECONDS,
            pragmas=_RESULT_TEXT_SQLITE_PRAGMAS,
        ) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT payload_text
                FROM chatbot_stock_context_cache
                WHERE cache_key = ?
                  AND mtime_ns = ?
                  AND size = ?
                LIMIT 1
                """,
                (cache_key, int(signature[0]), int(signature[1])),
            )
            return cursor.fetchone()

    try:
        row = run_sqlite_with_retry(
            _query_row,
            max_retries=_RESULT_TEXT_SQLITE_RETRY_ATTEMPTS,
            retry_delay_seconds=_RESULT_TEXT_SQLITE_RETRY_DELAY_SECONDS,
        )
    except Exception as exc:
        if _is_missing_table_error(exc) and _recover_result_text_sqlite_schema(db_path):
            try:
                row = run_sqlite_with_retry(
                    _query_row,
                    max_retries=_RESULT_TEXT_SQLITE_RETRY_ATTEMPTS,
                    retry_delay_seconds=_RESULT_TEXT_SQLITE_RETRY_DELAY_SECONDS,
                )
            except Exception as retry_exc:
                LOGGER.debug("Failed to load stock context sqlite cache after schema recovery (%s): %s", cache_key, retry_exc)
                return None
        else:
            LOGGER.debug("Failed to load stock context sqlite cache (%s): %s", cache_key, exc)
            return None

    try:
        if not row:
            return None
        payload_text = row[0]
        return payload_text if isinstance(payload_text, str) else None
    except Exception as exc:
        LOGGER.debug("Failed to load stock context sqlite cache (%s): %s", cache_key, exc)
        return None


def _save_result_text_to_sqlite(
    *,
    data_dir: Path,
    cache_key: str,
    dataset: str,
    ticker_padded: str,
    signature: tuple[int, int],
    payload_text: str,
) -> None:
    db_path = _resolve_runtime_cache_db_path(data_dir)
    if not _ensure_result_text_sqlite_cache(db_path):
        return
    db_path_text = str(db_path)

    normalized_max_rows = max(1, int(_RESULT_TEXT_SQLITE_MAX_ROWS))

    def _prune_rows_if_needed(cursor: sqlite3.Cursor) -> None:
        prune_rows_by_updated_at_if_needed(
            cursor,
            table_name="chatbot_stock_context_cache",
            max_rows=normalized_max_rows,
        )

    def _upsert_payload_text() -> None:
        with connect_sqlite(
            db_path_text,
            timeout_seconds=_RESULT_TEXT_SQLITE_TIMEOUT_SECONDS,
            pragmas=_RESULT_TEXT_SQLITE_PRAGMAS,
        ) as conn:
            now_iso = datetime.now().isoformat()
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO chatbot_stock_context_cache (
                    cache_key,
                    dataset,
                    ticker,
                    mtime_ns,
                    size,
                    payload_text,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(cache_key) DO UPDATE SET
                    dataset = excluded.dataset,
                    ticker = excluded.ticker,
                    mtime_ns = excluded.mtime_ns,
                    size = excluded.size,
                    payload_text = excluded.payload_text,
                    updated_at = excluded.updated_at
                """,
                (
                    cache_key,
                    dataset,
                    ticker_padded,
                    int(signature[0]),
                    int(signature[1]),
                    payload_text,
                    now_iso,
                ),
            )
            _prune_rows_if_needed(cursor)
            conn.commit()

    try:
        run_sqlite_with_retry(
            _upsert_payload_text,
            max_retries=_RESULT_TEXT_SQLITE_RETRY_ATTEMPTS,
            retry_delay_seconds=_RESULT_TEXT_SQLITE_RETRY_DELAY_SECONDS,
        )
    except Exception as exc:
        if _is_missing_table_error(exc) and _recover_result_text_sqlite_schema(db_path):
            try:
                run_sqlite_with_retry(
                    _upsert_payload_text,
                    max_retries=_RESULT_TEXT_SQLITE_RETRY_ATTEMPTS,
                    retry_delay_seconds=_RESULT_TEXT_SQLITE_RETRY_DELAY_SECONDS,
                )
            except Exception as retry_exc:
                LOGGER.debug(
                    "Failed to save stock context sqlite cache after schema recovery (%s): %s",
                    cache_key,
                    retry_exc,
                )
        else:
            LOGGER.debug("Failed to save stock context sqlite cache (%s): %s", cache_key, exc)


def load_cached_result_text(
    *,
    data_dir: Path,
    path: Path,
    dataset: str,
    ticker_padded: str,
    signature: tuple[int, int],
) -> str | None:
    cache_key = _build_result_cache_key(path, dataset=dataset, ticker_padded=ticker_padded)
    with _RESULT_TEXT_CACHE_LOCK:
        cached = _RESULT_TEXT_CACHE.get(cache_key)
        if cached and cached[0] == signature:
            return cached[1]

    sqlite_cached = _load_result_text_from_sqlite(
        data_dir=data_dir,
        cache_key=cache_key,
        signature=signature,
    )
    if sqlite_cached is None:
        return None

    _save_result_text_memory_entry(cache_key, signature, sqlite_cached)
    return sqlite_cached


def save_cached_result_text(
    *,
    data_dir: Path,
    path: Path,
    dataset: str,
    ticker_padded: str,
    signature: tuple[int, int],
    payload_text: str,
) -> None:
    cache_key = _build_result_cache_key(path, dataset=dataset, ticker_padded=ticker_padded)
    _save_result_text_memory_entry(cache_key, signature, payload_text)
    _save_result_text_to_sqlite(
        data_dir=data_dir,
        cache_key=cache_key,
        dataset=dataset,
        ticker_padded=ticker_padded,
        signature=signature,
        payload_text=payload_text,
    )


def clear_result_text_cache() -> None:
    with _RESULT_TEXT_CACHE_LOCK:
        _RESULT_TEXT_CACHE.clear()
