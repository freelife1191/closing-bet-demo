#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
chatbot 런타임 종목맵 캐시(SQLite + 메모리).
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
from collections import OrderedDict
from datetime import datetime
from pathlib import Path
from typing import Any

from services.sqlite_utils import (
    add_bounded_ready_key,
    build_sqlite_in_placeholders,
    build_sqlite_order_case_sql,
    build_sqlite_pragmas,
    connect_sqlite,
    is_sqlite_missing_table_error,
    normalize_sqlite_db_key,
    prune_rows_by_updated_at_if_needed,
    run_sqlite_with_retry,
    sqlite_db_path_exists,
)


_STOCK_MAP_CACHE_LOCK = threading.Lock()
_STOCK_MAP_CACHE: OrderedDict[
    str,
    tuple[tuple[int, int], dict[str, str], dict[str, str]],
] = OrderedDict()
_STOCK_MAP_SQLITE_READY_LOCK = threading.Lock()
_STOCK_MAP_SQLITE_READY_CONDITION = threading.Condition(_STOCK_MAP_SQLITE_READY_LOCK)
_STOCK_MAP_SQLITE_INIT_IN_PROGRESS: set[str] = set()
_STOCK_MAP_SQLITE_READY: set[str] = set()
_STOCK_MAP_SQLITE_READY_MAX_ENTRIES = 2_048
_STOCK_MAP_SQLITE_KNOWN_PATHS: OrderedDict[tuple[str, str], None] = OrderedDict()
_STOCK_MAP_SQLITE_KNOWN_PATHS_LOCK = threading.Lock()
_STOCK_MAP_SQLITE_KNOWN_PATHS_MAX_ENTRIES = 4_096
_STOCK_MAP_MEMORY_MAX_ENTRIES = 256
_STOCK_MAP_SQLITE_MAX_ROWS = 128
_STOCK_MAP_SQLITE_TIMEOUT_SECONDS = 30
_STOCK_MAP_SQLITE_RETRY_ATTEMPTS = 2
_STOCK_MAP_SQLITE_RETRY_DELAY_SECONDS = 0.03
_STOCK_MAP_SQLITE_PRUNE_FORCE_INTERVAL = 64
_STOCK_MAP_SQLITE_SAVE_COUNTER = 0
_STOCK_MAP_SQLITE_SAVE_COUNTER_LOCK = threading.Lock()
_STOCK_MAP_SQLITE_INIT_PRAGMAS = build_sqlite_pragmas(
    busy_timeout_ms=_STOCK_MAP_SQLITE_TIMEOUT_SECONDS * 1000,
)
_STOCK_MAP_SQLITE_SESSION_PRAGMAS = build_sqlite_pragmas(
    busy_timeout_ms=_STOCK_MAP_SQLITE_TIMEOUT_SECONDS * 1000,
    base_pragmas=("PRAGMA temp_store=MEMORY", "PRAGMA cache_size=-4000"),
)


def file_signature(path: Path) -> tuple[int, int] | None:
    try:
        stat = path.stat()
    except OSError:
        return None
    return int(stat.st_mtime_ns), int(stat.st_size)


def _stock_map_cache_key(path: Path) -> str:
    return _normalize_stock_map_source_key(path)


def _normalize_stock_map_source_key(path: Path | str) -> str:
    return normalize_sqlite_db_key(str(path))


def _stock_map_source_lookup_keys(path: Path) -> tuple[str, ...]:
    normalized_key = _normalize_stock_map_source_key(path)
    resolved_key = str(path.resolve())
    raw_key = str(path)
    keys: list[str] = [normalized_key]
    for candidate in (resolved_key, raw_key):
        if candidate not in keys:
            keys.append(candidate)

    try:
        relative_key = os.path.relpath(normalized_key, os.getcwd())
        if relative_key not in keys:
            keys.append(relative_key)
    except Exception:
        pass
    return tuple(keys)


def _stock_map_cache_db_path(data_dir: Path) -> Path:
    return data_dir / "runtime_cache.db"


def _invalidate_stock_map_sqlite_ready(db_path: Path) -> None:
    db_key = normalize_sqlite_db_key(str(db_path))
    with _STOCK_MAP_SQLITE_READY_LOCK:
        _STOCK_MAP_SQLITE_READY.discard(db_key)
    with _STOCK_MAP_SQLITE_KNOWN_PATHS_LOCK:
        stale_keys = [key for key in _STOCK_MAP_SQLITE_KNOWN_PATHS if key[0] == db_key]
        for tracker_key in stale_keys:
            _STOCK_MAP_SQLITE_KNOWN_PATHS.pop(tracker_key, None)


def _is_missing_table_error(error: Exception) -> bool:
    return is_sqlite_missing_table_error(error, table_names="chatbot_stock_map_cache")


def _recover_stock_map_sqlite_schema(db_path: Path, logger: Any) -> bool:
    _invalidate_stock_map_sqlite_ready(db_path)
    return _ensure_stock_map_sqlite(db_path, logger)


def _ensure_stock_map_sqlite(db_path: Path, logger: Any) -> bool:
    db_path_text = str(db_path)
    db_key = normalize_sqlite_db_key(db_path_text)
    with _STOCK_MAP_SQLITE_READY_CONDITION:
        if db_key in _STOCK_MAP_SQLITE_READY:
            if sqlite_db_path_exists(db_path_text):
                return True
            _STOCK_MAP_SQLITE_READY.discard(db_key)

        while db_key in _STOCK_MAP_SQLITE_INIT_IN_PROGRESS:
            _STOCK_MAP_SQLITE_READY_CONDITION.wait()
            if db_key in _STOCK_MAP_SQLITE_READY:
                if sqlite_db_path_exists(db_path_text):
                    return True
                _STOCK_MAP_SQLITE_READY.discard(db_key)

        _STOCK_MAP_SQLITE_INIT_IN_PROGRESS.add(db_key)

    def _initialize_schema() -> None:
        with connect_sqlite(
            db_path_text,
            timeout_seconds=_STOCK_MAP_SQLITE_TIMEOUT_SECONDS,
            pragmas=_STOCK_MAP_SQLITE_INIT_PRAGMAS,
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

    initialization_succeeded = False
    try:
        run_sqlite_with_retry(
            _initialize_schema,
            max_retries=_STOCK_MAP_SQLITE_RETRY_ATTEMPTS,
            retry_delay_seconds=_STOCK_MAP_SQLITE_RETRY_DELAY_SECONDS,
        )
        initialization_succeeded = True
        return True
    except Exception as error:
        logger.debug("Failed to initialize stock map sqlite cache: %s", error)
        return False
    finally:
        with _STOCK_MAP_SQLITE_READY_CONDITION:
            _STOCK_MAP_SQLITE_INIT_IN_PROGRESS.discard(db_key)
            if initialization_succeeded:
                add_bounded_ready_key(
                    _STOCK_MAP_SQLITE_READY,
                    db_key,
                    max_entries=_STOCK_MAP_SQLITE_READY_MAX_ENTRIES,
                )
            else:
                _STOCK_MAP_SQLITE_READY.discard(db_key)
            _STOCK_MAP_SQLITE_READY_CONDITION.notify_all()


def _save_stock_map_memory_entry(
    cache_key: str,
    signature: tuple[int, int],
    stock_map: dict[str, str],
    ticker_map: dict[str, str],
) -> None:
    max_entries = max(1, int(_STOCK_MAP_MEMORY_MAX_ENTRIES))
    with _STOCK_MAP_CACHE_LOCK:
        _STOCK_MAP_CACHE[cache_key] = (signature, dict(stock_map), dict(ticker_map))
        _STOCK_MAP_CACHE.move_to_end(cache_key)
        while len(_STOCK_MAP_CACHE) > max_entries:
            _STOCK_MAP_CACHE.popitem(last=False)


def _mark_stock_map_sqlite_source_path_seen(*, db_path: Path, source_path_key: str) -> bool:
    """
    (db_path, source_path) 조합의 SQLite key를 추적한다.
    return True면 신규 key로 간주해 prune을 수행한다.
    """
    db_key = normalize_sqlite_db_key(str(db_path))
    normalized_source_key = _normalize_stock_map_source_key(source_path_key)
    tracker_key = (db_key, normalized_source_key)
    with _STOCK_MAP_SQLITE_KNOWN_PATHS_LOCK:
        if tracker_key in _STOCK_MAP_SQLITE_KNOWN_PATHS:
            _STOCK_MAP_SQLITE_KNOWN_PATHS.move_to_end(tracker_key)
            return False

        _STOCK_MAP_SQLITE_KNOWN_PATHS[tracker_key] = None
        _STOCK_MAP_SQLITE_KNOWN_PATHS.move_to_end(tracker_key)
        normalized_max_entries = max(1, int(_STOCK_MAP_SQLITE_KNOWN_PATHS_MAX_ENTRIES))
        while len(_STOCK_MAP_SQLITE_KNOWN_PATHS) > normalized_max_entries:
            _STOCK_MAP_SQLITE_KNOWN_PATHS.popitem(last=False)
        return True


def _should_force_stock_map_sqlite_prune() -> bool:
    global _STOCK_MAP_SQLITE_SAVE_COUNTER
    with _STOCK_MAP_SQLITE_SAVE_COUNTER_LOCK:
        _STOCK_MAP_SQLITE_SAVE_COUNTER += 1
        normalized_interval = max(1, int(_STOCK_MAP_SQLITE_PRUNE_FORCE_INTERVAL))
        return (_STOCK_MAP_SQLITE_SAVE_COUNTER % normalized_interval) == 0


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
    db_path_text = str(db_path)
    lookup_keys = _stock_map_source_lookup_keys(source_path)
    lookup_placeholders = build_sqlite_in_placeholders(lookup_keys)
    order_case_sql = build_sqlite_order_case_sql(
        column_name="source_path",
        lookup_keys=lookup_keys,
    )
    query_params = (
        *lookup_keys,
        int(signature[0]),
        int(signature[1]),
        *lookup_keys,
    )

    def _query_row() -> tuple[Any, ...] | None:
        with connect_sqlite(
            db_path_text,
            timeout_seconds=_STOCK_MAP_SQLITE_TIMEOUT_SECONDS,
            pragmas=_STOCK_MAP_SQLITE_SESSION_PRAGMAS,
            read_only=True,
        ) as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"""
                SELECT stock_map_json, ticker_map_json
                FROM chatbot_stock_map_cache
                WHERE source_path IN ({lookup_placeholders})
                  AND mtime_ns = ?
                  AND size = ?
                ORDER BY {order_case_sql}
                LIMIT 1
                """,
                query_params,
            )
            return cursor.fetchone()

    try:
        row = run_sqlite_with_retry(
            _query_row,
            max_retries=_STOCK_MAP_SQLITE_RETRY_ATTEMPTS,
            retry_delay_seconds=_STOCK_MAP_SQLITE_RETRY_DELAY_SECONDS,
        )
    except Exception as error:
        if _is_missing_table_error(error) and _recover_stock_map_sqlite_schema(db_path, logger):
            try:
                row = run_sqlite_with_retry(
                    _query_row,
                    max_retries=_STOCK_MAP_SQLITE_RETRY_ATTEMPTS,
                    retry_delay_seconds=_STOCK_MAP_SQLITE_RETRY_DELAY_SECONDS,
                )
            except Exception as retry_error:
                logger.debug("Failed to load stock map sqlite cache after schema recovery: %s", retry_error)
                return None
        else:
            logger.debug("Failed to load stock map sqlite cache: %s", error)
            return None

    try:
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
    db_path_text = str(db_path)
    source_path_key = _normalize_stock_map_source_key(source_path)

    try:
        stock_map_json = json.dumps(stock_map, ensure_ascii=False, separators=(",", ":"))
        ticker_map_json = json.dumps(ticker_map, ensure_ascii=False, separators=(",", ":"))
    except Exception as error:
        logger.debug("Failed to serialize stock map cache: %s", error)
        return

    normalized_max_rows = max(1, int(_STOCK_MAP_SQLITE_MAX_ROWS))
    should_prune_for_new_path = _mark_stock_map_sqlite_source_path_seen(
        db_path=db_path,
        source_path_key=source_path_key,
    )
    should_force_prune = _should_force_stock_map_sqlite_prune()
    should_prune_after_upsert = should_prune_for_new_path or should_force_prune

    def _upsert_stock_map() -> None:
        with connect_sqlite(
            db_path_text,
            timeout_seconds=_STOCK_MAP_SQLITE_TIMEOUT_SECONDS,
            pragmas=_STOCK_MAP_SQLITE_SESSION_PRAGMAS,
        ) as conn:
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
                    source_path_key,
                    int(signature[0]),
                    int(signature[1]),
                    stock_map_json,
                    ticker_map_json,
                    now_iso,
                ),
            )
            if should_prune_after_upsert:
                prune_rows_by_updated_at_if_needed(
                    cursor,
                    table_name="chatbot_stock_map_cache",
                    max_rows=normalized_max_rows,
                )
            conn.commit()

    try:
        run_sqlite_with_retry(
            _upsert_stock_map,
            max_retries=_STOCK_MAP_SQLITE_RETRY_ATTEMPTS,
            retry_delay_seconds=_STOCK_MAP_SQLITE_RETRY_DELAY_SECONDS,
        )
    except Exception as error:
        if _is_missing_table_error(error) and _recover_stock_map_sqlite_schema(db_path, logger):
            try:
                run_sqlite_with_retry(
                    _upsert_stock_map,
                    max_retries=_STOCK_MAP_SQLITE_RETRY_ATTEMPTS,
                    retry_delay_seconds=_STOCK_MAP_SQLITE_RETRY_DELAY_SECONDS,
                )
            except Exception as retry_error:
                logger.debug("Failed to save stock map sqlite cache after schema recovery: %s", retry_error)
        else:
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
        if cached:
            if cached[0] == signature:
                _STOCK_MAP_CACHE.move_to_end(cache_key)
                return dict(cached[1]), dict(cached[2])
            _STOCK_MAP_CACHE.pop(cache_key, None)

    sqlite_cached = _load_stock_map_from_sqlite(
        data_dir=data_dir,
        source_path=source_path,
        signature=signature,
        logger=logger,
    )
    if sqlite_cached is None:
        return None

    stock_map, ticker_map = sqlite_cached
    _save_stock_map_memory_entry(cache_key, signature, stock_map, ticker_map)
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
    _save_stock_map_memory_entry(cache_key, signature, stock_map, ticker_map)

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
    with _STOCK_MAP_SQLITE_KNOWN_PATHS_LOCK:
        _STOCK_MAP_SQLITE_KNOWN_PATHS.clear()
    global _STOCK_MAP_SQLITE_SAVE_COUNTER
    with _STOCK_MAP_SQLITE_SAVE_COUNTER_LOCK:
        _STOCK_MAP_SQLITE_SAVE_COUNTER = 0
