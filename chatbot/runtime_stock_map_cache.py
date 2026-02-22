#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
chatbot 런타임 종목맵 캐시(SQLite + 메모리).
"""

from __future__ import annotations

import json
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

from services.sqlite_utils import connect_sqlite


_STOCK_MAP_CACHE_LOCK = threading.Lock()
_STOCK_MAP_CACHE: dict[str, tuple[tuple[int, int], dict[str, str], dict[str, str]]] = {}
_STOCK_MAP_SQLITE_READY_LOCK = threading.Lock()
_STOCK_MAP_SQLITE_READY: set[str] = set()
_STOCK_MAP_SQLITE_MAX_ROWS = 128


def file_signature(path: Path) -> tuple[int, int] | None:
    try:
        stat = path.stat()
    except OSError:
        return None
    return int(stat.st_mtime_ns), int(stat.st_size)


def _stock_map_cache_key(path: Path) -> str:
    return str(path.resolve())


def _stock_map_cache_db_path(data_dir: Path) -> Path:
    return data_dir / "runtime_cache.db"


def _ensure_stock_map_sqlite(db_path: Path, logger: Any) -> bool:
    db_key = str(db_path)
    with _STOCK_MAP_SQLITE_READY_LOCK:
        if db_key in _STOCK_MAP_SQLITE_READY:
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
                CREATE TABLE IF NOT EXISTS chatbot_stock_map_cache (
                    source_path TEXT PRIMARY KEY,
                    mtime_ns INTEGER NOT NULL,
                    size INTEGER NOT NULL,
                    stock_map_json TEXT NOT NULL,
                    ticker_map_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_chatbot_stock_map_cache_updated_at
                ON chatbot_stock_map_cache(updated_at DESC)
                """
            )
            conn.commit()
        with _STOCK_MAP_SQLITE_READY_LOCK:
            _STOCK_MAP_SQLITE_READY.add(db_key)
        return True
    except Exception as error:
        logger.debug("Failed to initialize stock map sqlite cache: %s", error)
        return False


def _load_stock_map_from_sqlite(
    *,
    data_dir: Path,
    source_path: Path,
    signature: tuple[int, int],
    logger: Any,
) -> tuple[dict[str, str], dict[str, str]] | None:
    db_path = _stock_map_cache_db_path(data_dir)
    if not _ensure_stock_map_sqlite(db_path, logger):
        return None

    try:
        with connect_sqlite(str(db_path), timeout_seconds=30) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT stock_map_json, ticker_map_json
                FROM chatbot_stock_map_cache
                WHERE source_path = ?
                  AND mtime_ns = ?
                  AND size = ?
                LIMIT 1
                """,
                (str(source_path.resolve()), int(signature[0]), int(signature[1])),
            )
            row = cursor.fetchone()
            if not row:
                return None

            stock_map = json.loads(row[0])
            ticker_map = json.loads(row[1])
            if isinstance(stock_map, dict) and isinstance(ticker_map, dict):
                return (
                    {str(k): str(v) for k, v in stock_map.items()},
                    {str(k): str(v) for k, v in ticker_map.items()},
                )
            return None
    except Exception as error:
        logger.debug("Failed to load stock map sqlite cache: %s", error)
        return None


def _save_stock_map_to_sqlite(
    *,
    data_dir: Path,
    source_path: Path,
    signature: tuple[int, int],
    stock_map: dict[str, str],
    ticker_map: dict[str, str],
    logger: Any,
) -> None:
    db_path = _stock_map_cache_db_path(data_dir)
    if not _ensure_stock_map_sqlite(db_path, logger):
        return

    try:
        stock_map_json = json.dumps(stock_map, ensure_ascii=False, separators=(",", ":"))
        ticker_map_json = json.dumps(ticker_map, ensure_ascii=False, separators=(",", ":"))
    except Exception as error:
        logger.debug("Failed to serialize stock map cache: %s", error)
        return

    try:
        with connect_sqlite(str(db_path), timeout_seconds=30) as conn:
            now_iso = datetime.now().isoformat()
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO chatbot_stock_map_cache (
                    source_path,
                    mtime_ns,
                    size,
                    stock_map_json,
                    ticker_map_json,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(source_path) DO UPDATE SET
                    mtime_ns = excluded.mtime_ns,
                    size = excluded.size,
                    stock_map_json = excluded.stock_map_json,
                    ticker_map_json = excluded.ticker_map_json,
                    updated_at = excluded.updated_at
                """,
                (
                    str(source_path.resolve()),
                    int(signature[0]),
                    int(signature[1]),
                    stock_map_json,
                    ticker_map_json,
                    now_iso,
                ),
            )
            cursor.execute(
                """
                DELETE FROM chatbot_stock_map_cache
                WHERE source_path NOT IN (
                    SELECT source_path
                    FROM chatbot_stock_map_cache
                    ORDER BY updated_at DESC
                    LIMIT ?
                )
                """,
                (_STOCK_MAP_SQLITE_MAX_ROWS,),
            )
            conn.commit()
    except Exception as error:
        logger.debug("Failed to save stock map sqlite cache: %s", error)


def load_stock_map_cache(
    *,
    data_dir: Path,
    source_path: Path,
    signature: tuple[int, int],
    logger: Any,
) -> tuple[dict[str, str], dict[str, str]] | None:
    cache_key = _stock_map_cache_key(source_path)
    with _STOCK_MAP_CACHE_LOCK:
        cached = _STOCK_MAP_CACHE.get(cache_key)
        if cached and cached[0] == signature:
            return dict(cached[1]), dict(cached[2])

    sqlite_cached = _load_stock_map_from_sqlite(
        data_dir=data_dir,
        source_path=source_path,
        signature=signature,
        logger=logger,
    )
    if sqlite_cached is None:
        return None

    stock_map, ticker_map = sqlite_cached
    with _STOCK_MAP_CACHE_LOCK:
        _STOCK_MAP_CACHE[cache_key] = (signature, dict(stock_map), dict(ticker_map))
    return dict(stock_map), dict(ticker_map)


def save_stock_map_cache(
    *,
    data_dir: Path,
    source_path: Path,
    signature: tuple[int, int],
    stock_map: dict[str, str],
    ticker_map: dict[str, str],
    logger: Any,
) -> None:
    cache_key = _stock_map_cache_key(source_path)
    with _STOCK_MAP_CACHE_LOCK:
        _STOCK_MAP_CACHE[cache_key] = (signature, dict(stock_map), dict(ticker_map))

    _save_stock_map_to_sqlite(
        data_dir=data_dir,
        source_path=source_path,
        signature=signature,
        stock_map=stock_map,
        ticker_map=ticker_map,
        logger=logger,
    )


def build_stock_maps(df: Any) -> tuple[dict[str, str], dict[str, str]]:
    if df.empty or not {"name", "ticker"}.issubset(df.columns):
        return {}, {}

    working = df[["name", "ticker"]].dropna(subset=["name", "ticker"])
    stock_map: dict[str, str] = {}
    ticker_map: dict[str, str] = {}
    for name, ticker in zip(working["name"], working["ticker"]):
        name_text = str(name)
        ticker_text = str(ticker).strip()
        if ticker_text.isdigit():
            ticker_text = ticker_text.zfill(6)
        stock_map[name_text] = ticker_text
        ticker_map[ticker_text] = name_text
    return stock_map, ticker_map


def clear_stock_map_cache() -> None:
    with _STOCK_MAP_CACHE_LOCK:
        _STOCK_MAP_CACHE.clear()

