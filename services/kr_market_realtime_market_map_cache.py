#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KR Market Realtime Market Map Cache
"""

from __future__ import annotations

import json
import logging
import os
import threading
from datetime import datetime
from typing import Callable

import pandas as pd

from services.kr_market_csv_utils import load_csv_readonly as _load_csv_readonly
from services.sqlite_utils import connect_sqlite


_MARKET_MAP_CACHE_LOCK = threading.Lock()
_MARKET_MAP_CACHE: dict[tuple[str, int, int], dict[str, str]] = {}
_MARKET_MAP_SQLITE_READY: set[str] = set()
_MARKET_MAP_SQLITE_LOCK = threading.Lock()


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


def _ensure_market_map_sqlite(db_path: str, logger: logging.Logger | None) -> bool:
    if db_path in _MARKET_MAP_SQLITE_READY:
        return True

    with _MARKET_MAP_SQLITE_LOCK:
        if db_path in _MARKET_MAP_SQLITE_READY:
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

    try:
        with connect_sqlite(db_path, timeout_seconds=5) as conn:
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
            row = cursor.fetchone()
        if row is None:
            return None
        loaded = json.loads(str(row[0]))
        if not isinstance(loaded, dict):
            return None
        return {str(key): str(value) for key, value in loaded.items()}
    except Exception as error:
        if logger is not None:
            logger.debug(f"Failed to load market map sqlite cache: {error}")
        return None


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

    try:
        payload_json = json.dumps(market_map, ensure_ascii=False)
        with connect_sqlite(db_path, timeout_seconds=5) as conn:
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
            cursor.execute(
                """
                DELETE FROM realtime_market_map_cache
                WHERE source_path NOT IN (
                    SELECT source_path
                    FROM realtime_market_map_cache
                    ORDER BY updated_at DESC
                    LIMIT 200
                )
                """
            )
            conn.commit()
    except Exception as error:
        if logger is not None:
            logger.debug(f"Failed to save market map sqlite cache: {error}")


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
