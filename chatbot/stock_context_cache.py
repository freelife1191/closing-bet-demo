#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
stock_context 결과 문자열 캐시(SQLite + 메모리).
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from threading import Lock

from services.sqlite_utils import connect_sqlite


LOGGER = logging.getLogger(__name__)

_RESULT_TEXT_CACHE_LOCK = Lock()
_RESULT_TEXT_CACHE: dict[str, tuple[tuple[int, int], str]] = {}
_RESULT_TEXT_SQLITE_LOCK = Lock()
_RESULT_TEXT_SQLITE_READY: set[str] = set()
_RESULT_TEXT_SQLITE_MAX_ROWS = 1024


def _build_result_cache_key(path: Path, *, dataset: str, ticker_padded: str) -> str:
    return f"{path}::{dataset}::{ticker_padded}"


def _resolve_runtime_cache_db_path(data_dir: Path) -> Path:
    return data_dir / "runtime_cache.db"


def _ensure_result_text_sqlite_cache(db_path: Path) -> bool:
    cache_key = str(db_path)
    with _RESULT_TEXT_SQLITE_LOCK:
        if cache_key in _RESULT_TEXT_SQLITE_READY:
            return True

    try:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        with connect_sqlite(
            str(db_path),
            timeout_seconds=30,
            pragmas=(
                "PRAGMA journal_mode=WAL",
                "PRAGMA synchronous=NORMAL",
                "PRAGMA temp_store=MEMORY",
                "PRAGMA busy_timeout=30000",
            ),
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

        with _RESULT_TEXT_SQLITE_LOCK:
            _RESULT_TEXT_SQLITE_READY.add(cache_key)
        return True
    except Exception as exc:
        LOGGER.debug("Failed to initialize stock context sqlite cache (%s): %s", db_path, exc)
        return False


def _load_result_text_from_sqlite(
    *,
    data_dir: Path,
    cache_key: str,
    signature: tuple[int, int],
) -> str | None:
    db_path = _resolve_runtime_cache_db_path(data_dir)
    if not _ensure_result_text_sqlite_cache(db_path):
        return None

    try:
        with connect_sqlite(str(db_path), timeout_seconds=30) as conn:
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
            row = cursor.fetchone()
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

    try:
        with connect_sqlite(str(db_path), timeout_seconds=30) as conn:
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
            cursor.execute(
                """
                DELETE FROM chatbot_stock_context_cache
                WHERE cache_key NOT IN (
                    SELECT cache_key
                    FROM chatbot_stock_context_cache
                    ORDER BY updated_at DESC
                    LIMIT ?
                )
                """,
                (_RESULT_TEXT_SQLITE_MAX_ROWS,),
            )
            conn.commit()
    except Exception as exc:
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

    with _RESULT_TEXT_CACHE_LOCK:
        _RESULT_TEXT_CACHE[cache_key] = (signature, sqlite_cached)
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
    with _RESULT_TEXT_CACHE_LOCK:
        _RESULT_TEXT_CACHE[cache_key] = (signature, payload_text)
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

