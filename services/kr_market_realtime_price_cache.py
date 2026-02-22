#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KR Market realtime price SQLite cache.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta
from typing import Any, Callable

from services.sqlite_utils import connect_sqlite

_REALTIME_PRICE_SQLITE_READY: set[str] = set()


def _normalize_ticker(ticker: Any) -> str:
    return str(ticker).zfill(6)


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


def _ensure_realtime_price_sqlite(db_path: str, logger: logging.Logger | None) -> bool:
    if db_path in _REALTIME_PRICE_SQLITE_READY:
        return True

    try:
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        with connect_sqlite(
            db_path,
            timeout_seconds=5,
            pragmas=(
                "PRAGMA journal_mode=WAL",
                "PRAGMA synchronous=NORMAL",
                "PRAGMA temp_store=MEMORY",
                "PRAGMA busy_timeout=5000",
            ),
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

    normalized_tickers = [_normalize_ticker(ticker) for ticker in tickers]
    unique_tickers = list(dict.fromkeys(normalized_tickers))
    if not unique_tickers:
        return {}

    cutoff_iso = (datetime.now() - timedelta(seconds=max(0, int(max_age_seconds)))).isoformat()
    placeholders = ",".join("?" for _ in unique_tickers)

    try:
        with connect_sqlite(db_path, timeout_seconds=5) as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"""
                SELECT ticker, price
                FROM realtime_price_cache
                WHERE ticker IN ({placeholders})
                  AND updated_at >= ?
                """,
                [*unique_tickers, cutoff_iso],
            )
            rows = cursor.fetchall()
    except Exception as error:
        if logger is not None:
            logger.debug(f"Failed to load realtime price cache: {error}")
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
    now_iso = datetime.now().isoformat()
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

    try:
        with connect_sqlite(db_path, timeout_seconds=5) as conn:
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
            cursor.execute(
                """
                DELETE FROM realtime_price_cache
                WHERE updated_at < ?
                """,
                ((datetime.now() - timedelta(days=3)).isoformat(),),
            )
            conn.commit()
    except Exception as error:
        if logger is not None:
            logger.debug(f"Failed to save realtime price cache: {error}")


__all__ = [
    "load_cached_realtime_prices",
    "save_realtime_prices_to_cache",
]
