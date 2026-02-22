#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KR Market realtime price SQLite cache.
"""

from __future__ import annotations

import logging
import os
import sqlite3
import threading
from datetime import datetime, timedelta
from typing import Any, Callable, Iterator

from services.sqlite_utils import build_sqlite_pragmas, connect_sqlite

_REALTIME_PRICE_SQLITE_READY: set[str] = set()
_REALTIME_PRICE_SQLITE_READY_LOCK = threading.Lock()
_REALTIME_PRICE_SQLITE_TIMEOUT_SECONDS = 5
_YFINANCE_FAILURE_CACHE_RETENTION_DAYS = 7
_SQLITE_TICKER_QUERY_CHUNK_SIZE = 900
_SQLITE_PRUNE_MIN_INTERVAL_SECONDS = 300
_YFINANCE_FAILED_MEMORY_CACHE_LOCK = threading.Lock()
_SQLITE_PRUNE_STATE_LOCK = threading.Lock()
_YFINANCE_FAILED_MEMORY_CACHE: dict[
    str,
    tuple[
        tuple[tuple[int, int, int] | None, tuple[int, int, int] | None, tuple[int, int, int] | None] | None,
        dict[str, float | None],
    ],
] = {}
_REALTIME_PRICE_LAST_PRUNED_AT: dict[str, float] = {}
_YFINANCE_FAILED_LAST_PRUNED_AT: dict[str, float] = {}
_REALTIME_PRICE_INIT_PRAGMAS = build_sqlite_pragmas(
    busy_timeout_ms=_REALTIME_PRICE_SQLITE_TIMEOUT_SECONDS * 1000,
)
_REALTIME_PRICE_SESSION_PRAGMAS = build_sqlite_pragmas(
    busy_timeout_ms=_REALTIME_PRICE_SQLITE_TIMEOUT_SECONDS * 1000,
    base_pragmas=("PRAGMA temp_store=MEMORY", "PRAGMA cache_size=-4000"),
)


def _normalize_ticker(ticker: Any) -> str:
    return str(ticker).zfill(6)


def _normalize_unique_tickers(tickers: list[Any]) -> list[str]:
    unique_tickers: list[str] = []
    seen: set[str] = set()
    for ticker in tickers:
        ticker_key = _normalize_ticker(ticker)
        if ticker_key in seen:
            continue
        seen.add(ticker_key)
        unique_tickers.append(ticker_key)
    return unique_tickers


def _iter_ticker_chunks(tickers: list[str]) -> Iterator[list[str]]:
    chunk_size = max(1, int(_SQLITE_TICKER_QUERY_CHUNK_SIZE))
    for index in range(0, len(tickers), chunk_size):
        yield tickers[index : index + chunk_size]


def _path_signature(path: str) -> tuple[int, int, int] | None:
    try:
        stat = os.stat(path)
    except OSError:
        return None
    return (int(stat.st_ino), int(stat.st_mtime_ns), int(stat.st_size))


def _sqlite_storage_signature(
    db_path: str,
) -> tuple[tuple[int, int, int] | None, tuple[int, int, int] | None, tuple[int, int, int] | None] | None:
    db_sig = _path_signature(db_path)
    wal_sig = _path_signature(f"{db_path}-wal")
    shm_sig = _path_signature(f"{db_path}-shm")
    if db_sig is None and wal_sig is None and shm_sig is None:
        return None
    return (db_sig, wal_sig, shm_sig)


def _parse_iso_timestamp(value: Any) -> float | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value)).timestamp()
    except (TypeError, ValueError):
        return None


def _resolve_runtime_cache_db_path(get_data_path: Callable[[str], str] | None) -> str:
    if get_data_path is not None:
        try:
            source_path = str(get_data_path("korean_stocks_list.csv"))
            source_dir = os.path.dirname(source_path) or "."
            return os.path.join(source_dir, "runtime_cache.db")
        except Exception:
            pass

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_dir, "data", "runtime_cache.db")


def _invalidate_realtime_price_sqlite_ready(db_path: str) -> None:
    with _REALTIME_PRICE_SQLITE_READY_LOCK:
        _REALTIME_PRICE_SQLITE_READY.discard(db_path)
    _reset_sqlite_prune_state(db_path)


def _is_sqlite_cache_prune_due(last_pruned_map: dict[str, float], db_path: str, now_ts: float) -> bool:
    with _SQLITE_PRUNE_STATE_LOCK:
        last_pruned_at = last_pruned_map.get(db_path)
        if last_pruned_at is None:
            return True
        return (now_ts - last_pruned_at) >= max(1, int(_SQLITE_PRUNE_MIN_INTERVAL_SECONDS))


def _mark_sqlite_cache_pruned(last_pruned_map: dict[str, float], db_path: str, now_ts: float) -> None:
    with _SQLITE_PRUNE_STATE_LOCK:
        last_pruned_map[db_path] = now_ts


def _reset_sqlite_prune_state(db_path: str) -> None:
    with _SQLITE_PRUNE_STATE_LOCK:
        _REALTIME_PRICE_LAST_PRUNED_AT.pop(db_path, None)
        _YFINANCE_FAILED_LAST_PRUNED_AT.pop(db_path, None)


def _is_missing_table_error(error: Exception, *, table_name: str) -> bool:
    if not isinstance(error, sqlite3.OperationalError):
        return False
    message = str(error).lower()
    return "no such table" in message and table_name.lower() in message


def _recover_realtime_price_sqlite_schema(
    db_path: str,
    logger: logging.Logger | None,
) -> bool:
    _invalidate_realtime_price_sqlite_ready(db_path)
    return _ensure_realtime_price_sqlite(db_path, logger)


def _ensure_realtime_price_sqlite(db_path: str, logger: logging.Logger | None) -> bool:
    with _REALTIME_PRICE_SQLITE_READY_LOCK:
        if db_path in _REALTIME_PRICE_SQLITE_READY:
            if os.path.exists(db_path):
                return True
            _REALTIME_PRICE_SQLITE_READY.discard(db_path)

        try:
            with connect_sqlite(
                db_path,
                timeout_seconds=_REALTIME_PRICE_SQLITE_TIMEOUT_SECONDS,
                pragmas=_REALTIME_PRICE_INIT_PRAGMAS,
            ) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS realtime_price_cache (
                        ticker TEXT PRIMARY KEY,
                        price REAL NOT NULL,
                        source TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    )
                    """
                )
                cursor.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_realtime_price_cache_updated_at
                    ON realtime_price_cache(updated_at DESC)
                    """
                )
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS yfinance_failed_ticker_cache (
                        ticker TEXT PRIMARY KEY,
                        updated_at TEXT NOT NULL
                    )
                    """
                )
                cursor.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_yfinance_failed_ticker_cache_updated_at
                    ON yfinance_failed_ticker_cache(updated_at DESC)
                    """
                )
                conn.commit()
            _REALTIME_PRICE_SQLITE_READY.add(db_path)
            return True
        except Exception as error:
            if logger is not None:
                logger.debug(f"Failed to initialize realtime price sqlite cache: {error}")
            return False


def load_cached_realtime_prices(
    tickers: list[Any],
    *,
    get_data_path: Callable[[str], str] | None = None,
    logger: logging.Logger | None = None,
    max_age_seconds: int = 900,
) -> dict[str, float]:
    if not tickers:
        return {}

    db_path = _resolve_runtime_cache_db_path(get_data_path)
    if not _ensure_realtime_price_sqlite(db_path, logger):
        return {}

    unique_tickers = _normalize_unique_tickers(tickers)
    if not unique_tickers:
        return {}

    cutoff_iso = (datetime.now() - timedelta(seconds=max(0, int(max_age_seconds)))).isoformat()
    def _query_rows() -> list[tuple[Any, Any]]:
        with connect_sqlite(
            db_path,
            timeout_seconds=_REALTIME_PRICE_SQLITE_TIMEOUT_SECONDS,
            pragmas=_REALTIME_PRICE_SESSION_PRAGMAS,
        ) as conn:
            cursor = conn.cursor()
            rows: list[tuple[Any, Any]] = []
            for chunk in _iter_ticker_chunks(unique_tickers):
                placeholders = ",".join("?" for _ in chunk)
                cursor.execute(
                    f"""
                    SELECT ticker, price
                    FROM realtime_price_cache
                    WHERE ticker IN ({placeholders})
                      AND updated_at >= ?
                    """,
                    [*chunk, cutoff_iso],
                )
                rows.extend(cursor.fetchall())
            return rows

    try:
        rows = _query_rows()
    except Exception as error:
        if _is_missing_table_error(error, table_name="realtime_price_cache") and _recover_realtime_price_sqlite_schema(
            db_path,
            logger,
        ):
            try:
                rows = _query_rows()
            except Exception as retry_error:
                if logger is not None:
                    logger.debug("Failed to load realtime price cache after schema recovery: %s", retry_error)
                return {}
        else:
            if logger is not None:
                logger.debug("Failed to load realtime price cache: %s", error)
            return {}

    resolved: dict[str, float] = {}
    for ticker, price in rows:
        ticker_key = _normalize_ticker(ticker)
        try:
            price_value = float(price or 0)
        except (TypeError, ValueError):
            price_value = 0.0
        if price_value > 0:
            resolved[ticker_key] = price_value
    return resolved


def save_realtime_prices_to_cache(
    prices: dict[str, float],
    *,
    source: str,
    get_data_path: Callable[[str], str] | None = None,
    logger: logging.Logger | None = None,
) -> None:
    if not prices:
        return

    db_path = _resolve_runtime_cache_db_path(get_data_path)
    if not _ensure_realtime_price_sqlite(db_path, logger):
        return

    rows: list[tuple[str, float, str, str]] = []
    now_dt = datetime.now()
    now_iso = now_dt.isoformat()
    for ticker, price in prices.items():
        ticker_key = _normalize_ticker(ticker)
        try:
            price_value = float(price or 0)
        except (TypeError, ValueError):
            continue
        if price_value <= 0:
            continue
        rows.append((ticker_key, price_value, str(source), now_iso))

    if not rows:
        return

    now_ts = now_dt.timestamp()
    should_prune = _is_sqlite_cache_prune_due(
        _REALTIME_PRICE_LAST_PRUNED_AT,
        db_path,
        now_ts,
    )
    prune_cutoff_iso = (now_dt - timedelta(days=3)).isoformat() if should_prune else None

    def _upsert_rows() -> None:
        with connect_sqlite(
            db_path,
            timeout_seconds=_REALTIME_PRICE_SQLITE_TIMEOUT_SECONDS,
            pragmas=_REALTIME_PRICE_SESSION_PRAGMAS,
        ) as conn:
            cursor = conn.cursor()
            cursor.executemany(
                """
                INSERT INTO realtime_price_cache (ticker, price, source, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(ticker) DO UPDATE SET
                    price = excluded.price,
                    source = excluded.source,
                    updated_at = excluded.updated_at
                """,
                rows,
            )
            if should_prune and prune_cutoff_iso is not None:
                cursor.execute(
                    """
                    DELETE FROM realtime_price_cache
                    WHERE updated_at < ?
                    """,
                    (prune_cutoff_iso,),
                )
            conn.commit()
        if should_prune:
            _mark_sqlite_cache_pruned(_REALTIME_PRICE_LAST_PRUNED_AT, db_path, now_ts)

    try:
        _upsert_rows()
    except Exception as error:
        if _is_missing_table_error(error, table_name="realtime_price_cache") and _recover_realtime_price_sqlite_schema(
            db_path,
            logger,
        ):
            try:
                _upsert_rows()
            except Exception as retry_error:
                if logger is not None:
                    logger.debug("Failed to save realtime price cache after schema recovery: %s", retry_error)
        else:
            if logger is not None:
                logger.debug("Failed to save realtime price cache: %s", error)


def load_recent_yfinance_failed_tickers(
    tickers: list[Any],
    *,
    get_data_path: Callable[[str], str] | None = None,
    logger: logging.Logger | None = None,
    max_age_seconds: int = 1_800,
) -> set[str]:
    if not tickers:
        return set()

    db_path = _resolve_runtime_cache_db_path(get_data_path)
    if not _ensure_realtime_price_sqlite(db_path, logger):
        return set()

    unique_tickers = _normalize_unique_tickers(tickers)
    if not unique_tickers:
        return set()

    now_ts = datetime.now().timestamp()
    cutoff_ts = now_ts - max(0, int(max_age_seconds))
    cutoff_iso = datetime.fromtimestamp(cutoff_ts).isoformat()
    storage_signature = _sqlite_storage_signature(db_path)
    resolved_from_memory: set[str] = set()
    unresolved_tickers: list[str] = unique_tickers

    with _YFINANCE_FAILED_MEMORY_CACHE_LOCK:
        entry = _YFINANCE_FAILED_MEMORY_CACHE.get(db_path)
        if entry is None or entry[0] != storage_signature:
            memory_map: dict[str, float | None] = {}
            _YFINANCE_FAILED_MEMORY_CACHE[db_path] = (storage_signature, memory_map)
        else:
            memory_map = entry[1]
            unresolved_tickers = [ticker for ticker in unique_tickers if ticker not in memory_map]
            for ticker in unique_tickers:
                updated_ts = memory_map.get(ticker)
                if updated_ts is not None and updated_ts >= cutoff_ts:
                    resolved_from_memory.add(ticker)

    if not unresolved_tickers:
        return resolved_from_memory

    fetched_map: dict[str, float | None] = {}

    def _query_failed_tickers() -> list[tuple[Any, Any]]:
        with connect_sqlite(
            db_path,
            timeout_seconds=_REALTIME_PRICE_SQLITE_TIMEOUT_SECONDS,
            pragmas=_REALTIME_PRICE_SESSION_PRAGMAS,
        ) as conn:
            cursor = conn.cursor()
            rows: list[tuple[Any, Any]] = []
            for chunk in _iter_ticker_chunks(unresolved_tickers):
                placeholders = ",".join("?" for _ in chunk)
                cursor.execute(
                    f"""
                    SELECT ticker, updated_at
                    FROM yfinance_failed_ticker_cache
                    WHERE ticker IN ({placeholders})
                      AND updated_at >= ?
                    """,
                    [*chunk, cutoff_iso],
                )
                rows.extend(cursor.fetchall())
            return rows

    try:
        rows = _query_failed_tickers()
    except Exception as error:
        if _is_missing_table_error(error, table_name="yfinance_failed_ticker_cache") and _recover_realtime_price_sqlite_schema(
            db_path,
            logger,
        ):
            try:
                rows = _query_failed_tickers()
            except Exception as retry_error:
                if logger is not None:
                    logger.debug(
                        "Failed to load yfinance failed ticker cache after schema recovery: %s",
                        retry_error,
                    )
                return resolved_from_memory
        else:
            if logger is not None:
                logger.debug("Failed to load yfinance failed ticker cache: %s", error)
            return resolved_from_memory

    for ticker, updated_at in rows:
        ticker_key = _normalize_ticker(ticker)
        fetched_map[ticker_key] = _parse_iso_timestamp(updated_at)
    for ticker in unresolved_tickers:
        fetched_map.setdefault(ticker, None)

    refreshed_signature = _sqlite_storage_signature(db_path)
    with _YFINANCE_FAILED_MEMORY_CACHE_LOCK:
        entry = _YFINANCE_FAILED_MEMORY_CACHE.get(db_path)
        if entry is None or entry[0] != refreshed_signature:
            cache_map: dict[str, float | None] = {}
            _YFINANCE_FAILED_MEMORY_CACHE[db_path] = (refreshed_signature, cache_map)
        else:
            cache_map = entry[1]
        cache_map.update(fetched_map)

    for ticker, updated_ts in fetched_map.items():
        if updated_ts is not None and updated_ts >= cutoff_ts:
            resolved_from_memory.add(ticker)

    return resolved_from_memory


def save_yfinance_failed_tickers(
    tickers: list[Any],
    *,
    get_data_path: Callable[[str], str] | None = None,
    logger: logging.Logger | None = None,
) -> None:
    if not tickers:
        return

    db_path = _resolve_runtime_cache_db_path(get_data_path)
    if not _ensure_realtime_price_sqlite(db_path, logger):
        return

    unique_tickers = _normalize_unique_tickers(tickers)
    if not unique_tickers:
        return

    now_dt = datetime.now()
    now_iso = now_dt.isoformat()
    rows = [(ticker, now_iso) for ticker in unique_tickers]
    now_ts = now_dt.timestamp()
    should_prune = _is_sqlite_cache_prune_due(
        _YFINANCE_FAILED_LAST_PRUNED_AT,
        db_path,
        now_ts,
    )
    prune_cutoff_iso = (
        now_dt - timedelta(days=_YFINANCE_FAILURE_CACHE_RETENTION_DAYS)
    ).isoformat() if should_prune else None

    def _upsert_failed_tickers() -> None:
        with connect_sqlite(
            db_path,
            timeout_seconds=_REALTIME_PRICE_SQLITE_TIMEOUT_SECONDS,
            pragmas=_REALTIME_PRICE_SESSION_PRAGMAS,
        ) as conn:
            cursor = conn.cursor()
            cursor.executemany(
                """
                INSERT INTO yfinance_failed_ticker_cache (ticker, updated_at)
                VALUES (?, ?)
                ON CONFLICT(ticker) DO UPDATE SET
                    updated_at = excluded.updated_at
                """,
                rows,
            )
            if should_prune and prune_cutoff_iso is not None:
                cursor.execute(
                    """
                    DELETE FROM yfinance_failed_ticker_cache
                    WHERE updated_at < ?
                    """,
                    (prune_cutoff_iso,),
                )
            conn.commit()
        if should_prune:
            _mark_sqlite_cache_pruned(_YFINANCE_FAILED_LAST_PRUNED_AT, db_path, now_ts)

    try:
        _upsert_failed_tickers()
    except Exception as error:
        if _is_missing_table_error(error, table_name="yfinance_failed_ticker_cache") and _recover_realtime_price_sqlite_schema(
            db_path,
            logger,
        ):
            try:
                _upsert_failed_tickers()
            except Exception as retry_error:
                if logger is not None:
                    logger.debug(
                        "Failed to save yfinance failed ticker cache after schema recovery: %s",
                        retry_error,
                    )
                return
        else:
            if logger is not None:
                logger.debug("Failed to save yfinance failed ticker cache: %s", error)
            return

    now_ts = datetime.now().timestamp()
    refreshed_signature = _sqlite_storage_signature(db_path)
    with _YFINANCE_FAILED_MEMORY_CACHE_LOCK:
        entry = _YFINANCE_FAILED_MEMORY_CACHE.get(db_path)
        if entry is None or entry[0] != refreshed_signature:
            cache_map: dict[str, float | None] = {}
            _YFINANCE_FAILED_MEMORY_CACHE[db_path] = (refreshed_signature, cache_map)
        else:
            cache_map = entry[1]
        for ticker in unique_tickers:
            cache_map[ticker] = now_ts


__all__ = [
    "load_cached_realtime_prices",
    "load_recent_yfinance_failed_tickers",
    "save_realtime_prices_to_cache",
    "save_yfinance_failed_tickers",
]
