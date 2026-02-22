#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KR AI 종목정보 캐시(SQLite + 메모리).
"""

from __future__ import annotations

import copy
import json
import os
import threading
from datetime import datetime
from typing import Any, Callable

from services.sqlite_utils import connect_sqlite


_STOCK_INFO_CACHE_LOCK = threading.Lock()
_STOCK_INFO_CACHE: dict[str, tuple[tuple[int, int], dict[str, object]]] = {}
_STOCK_INFO_SQLITE_READY_LOCK = threading.Lock()
_STOCK_INFO_SQLITE_READY: set[str] = set()
_STOCK_INFO_SQLITE_MAX_ROWS = 512


def _stock_info_cache_key(signals_file: str, ticker: str) -> str:
    return f"{os.path.abspath(signals_file)}::{str(ticker)}"


def resolve_stock_info_cache_db_path(signals_file: str) -> str:
    return os.path.join(os.path.dirname(signals_file), "runtime_cache.db")


def _ensure_stock_info_sqlite(db_path: str, logger: Any) -> bool:
    with _STOCK_INFO_SQLITE_READY_LOCK:
        if db_path in _STOCK_INFO_SQLITE_READY:
            return True

    try:
        with connect_sqlite(
            db_path,
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
        with _STOCK_INFO_SQLITE_READY_LOCK:
            _STOCK_INFO_SQLITE_READY.add(db_path)
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

    try:
        with connect_sqlite(db_path, timeout_seconds=30) as conn:
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
                    os.path.abspath(signals_file),
                    str(ticker),
                    int(signature[0]),
                    int(signature[1]),
                ),
            )
            row = cursor.fetchone()
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

    try:
        payload_json = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    except Exception as error:
        logger.debug("Failed to serialize KR AI stock info cache: %s", error)
        return

    try:
        with connect_sqlite(db_path, timeout_seconds=30) as conn:
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
                    os.path.abspath(signals_file),
                    str(ticker),
                    int(signature[0]),
                    int(signature[1]),
                    payload_json,
                    now_iso,
                ),
            )
            cursor.execute(
                """
                DELETE FROM kr_ai_stock_info_cache
                WHERE (signals_path, ticker) NOT IN (
                    SELECT signals_path, ticker
                    FROM kr_ai_stock_info_cache
                    ORDER BY updated_at DESC
                    LIMIT ?
                )
                """,
                (_STOCK_INFO_SQLITE_MAX_ROWS,),
            )
            conn.commit()
    except Exception as error:
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

