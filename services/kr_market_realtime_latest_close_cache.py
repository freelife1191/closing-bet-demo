#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KR Market realtime latest-close cache helpers.
"""

from __future__ import annotations

import json
import logging
import os
import threading
from collections import OrderedDict
from collections.abc import Callable
from datetime import datetime
from typing import Any

import pandas as pd

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


_LATEST_CLOSE_MAP_CACHE_LOCK = threading.Lock()
_LATEST_CLOSE_MAP_CACHE: OrderedDict[tuple[str, int, int], dict[str, float]] = OrderedDict()
_LATEST_CLOSE_MAP_MEMORY_MAX_ENTRIES = 16
_LATEST_CLOSE_MAP_SQLITE_READY: set[str] = set()
_LATEST_CLOSE_MAP_SQLITE_LOCK = threading.Lock()
_LATEST_CLOSE_MAP_SQLITE_CONDITION = threading.Condition(_LATEST_CLOSE_MAP_SQLITE_LOCK)
_LATEST_CLOSE_MAP_SQLITE_INIT_IN_PROGRESS: set[str] = set()
_LATEST_CLOSE_MAP_SQLITE_READY_MAX_ENTRIES = 2_048
_LATEST_CLOSE_MAP_SQLITE_KNOWN_PATHS: OrderedDict[tuple[str, str], None] = OrderedDict()
_LATEST_CLOSE_MAP_SQLITE_KNOWN_PATHS_LOCK = threading.Lock()
_LATEST_CLOSE_MAP_SQLITE_KNOWN_PATHS_MAX_ENTRIES = 4_096
_LATEST_CLOSE_MAP_SQLITE_MAX_ROWS = 200
_LATEST_CLOSE_MAP_SQLITE_PRUNE_FORCE_INTERVAL = 64
_LATEST_CLOSE_MAP_SQLITE_SAVE_COUNTER = 0
_LATEST_CLOSE_MAP_SQLITE_SAVE_COUNTER_LOCK = threading.Lock()
_LATEST_CLOSE_MAP_SQLITE_INIT_PRAGMAS = build_sqlite_pragmas(busy_timeout_ms=5_000)
_LATEST_CLOSE_MAP_SQLITE_SESSION_PRAGMAS = build_sqlite_pragmas(
    busy_timeout_ms=5_000,
    base_pragmas=("PRAGMA temp_store=MEMORY", "PRAGMA cache_size=-4000"),
)
_LATEST_CLOSE_MAP_SQLITE_RETRY_ATTEMPTS = 2
_LATEST_CLOSE_MAP_SQLITE_RETRY_DELAY_SECONDS = 0.03


def _save_latest_close_memory_entry(
    *,
    cache_key: tuple[str, int, int],
    value: dict[str, float],
) -> None:
    normalized_max_entries = max(1, int(_LATEST_CLOSE_MAP_MEMORY_MAX_ENTRIES))
    with _LATEST_CLOSE_MAP_CACHE_LOCK:
        _LATEST_CLOSE_MAP_CACHE[cache_key] = dict(value)
        _LATEST_CLOSE_MAP_CACHE.move_to_end(cache_key)
        while len(_LATEST_CLOSE_MAP_CACHE) > normalized_max_entries:
            _LATEST_CLOSE_MAP_CACHE.popitem(last=False)


def _file_signature(path: str) -> tuple[int, int] | None:
    try:
        stat = os.stat(path)
    except OSError:
        return None
    return int(stat.st_mtime_ns), int(stat.st_size)


def _resolve_daily_prices_source_path(get_data_path: Callable[[str], str] | None) -> str | None:
    if get_data_path is None:
        return None
    try:
        return str(get_data_path("daily_prices.csv"))
    except Exception:
        return None


def _resolve_latest_close_map_cache_db_path(source_path: str) -> str:
    source_dir = os.path.dirname(source_path) or "."
    return os.path.join(source_dir, "runtime_cache.db")


def _normalize_latest_close_source_path(path: str) -> str:
    return normalize_sqlite_db_key(path)


def _latest_close_source_lookup_keys(path: str) -> tuple[str, ...]:
    normalized_path = _normalize_latest_close_source_path(path)
    raw_path = str(path)
    keys: list[str] = [normalized_path]
    if raw_path not in keys:
        keys.append(raw_path)

    try:
        relative_path = os.path.relpath(normalized_path, os.getcwd())
        if relative_path not in keys:
            keys.append(relative_path)
    except Exception:
        pass
    return tuple(keys)


def _invalidate_latest_close_map_sqlite_ready(db_path: str) -> None:
    db_key = normalize_sqlite_db_key(db_path)
    with _LATEST_CLOSE_MAP_SQLITE_CONDITION:
        _LATEST_CLOSE_MAP_SQLITE_READY.discard(db_key)
    with _LATEST_CLOSE_MAP_SQLITE_KNOWN_PATHS_LOCK:
        stale_keys = [key for key in _LATEST_CLOSE_MAP_SQLITE_KNOWN_PATHS if key[0] == db_key]
        for tracker_key in stale_keys:
            _LATEST_CLOSE_MAP_SQLITE_KNOWN_PATHS.pop(tracker_key, None)


def _is_missing_table_error(error: Exception) -> bool:
    return is_sqlite_missing_table_error(error, table_names="realtime_latest_close_map_cache")


def _recover_latest_close_map_sqlite_schema(db_path: str, logger: logging.Logger | None) -> bool:
    _invalidate_latest_close_map_sqlite_ready(db_path)
    return _ensure_latest_close_map_sqlite(db_path, logger)


def _mark_latest_close_map_sqlite_source_path_seen(*, db_path: str, source_path: str) -> bool:
    """
    (db_path, source_path) 조합을 추적한다.
    return True면 신규 key로 간주해 prune을 수행한다.
    """
    db_key = normalize_sqlite_db_key(db_path)
    source_path_key = _normalize_latest_close_source_path(source_path)
    tracker_key = (db_key, source_path_key)
    with _LATEST_CLOSE_MAP_SQLITE_KNOWN_PATHS_LOCK:
        if tracker_key in _LATEST_CLOSE_MAP_SQLITE_KNOWN_PATHS:
            _LATEST_CLOSE_MAP_SQLITE_KNOWN_PATHS.move_to_end(tracker_key)
            return False

        _LATEST_CLOSE_MAP_SQLITE_KNOWN_PATHS[tracker_key] = None
        _LATEST_CLOSE_MAP_SQLITE_KNOWN_PATHS.move_to_end(tracker_key)
        normalized_max_entries = max(1, int(_LATEST_CLOSE_MAP_SQLITE_KNOWN_PATHS_MAX_ENTRIES))
        while len(_LATEST_CLOSE_MAP_SQLITE_KNOWN_PATHS) > normalized_max_entries:
            _LATEST_CLOSE_MAP_SQLITE_KNOWN_PATHS.popitem(last=False)
        return True


def _should_force_latest_close_map_sqlite_prune() -> bool:
    global _LATEST_CLOSE_MAP_SQLITE_SAVE_COUNTER
    with _LATEST_CLOSE_MAP_SQLITE_SAVE_COUNTER_LOCK:
        _LATEST_CLOSE_MAP_SQLITE_SAVE_COUNTER += 1
        normalized_interval = max(1, int(_LATEST_CLOSE_MAP_SQLITE_PRUNE_FORCE_INTERVAL))
        return (_LATEST_CLOSE_MAP_SQLITE_SAVE_COUNTER % normalized_interval) == 0


def _ensure_latest_close_map_sqlite(db_path: str, logger: logging.Logger | None) -> bool:
    db_key = normalize_sqlite_db_key(db_path)
    with _LATEST_CLOSE_MAP_SQLITE_CONDITION:
        if db_key in _LATEST_CLOSE_MAP_SQLITE_READY:
            if sqlite_db_path_exists(db_path):
                return True
            _LATEST_CLOSE_MAP_SQLITE_READY.discard(db_key)

        while db_key in _LATEST_CLOSE_MAP_SQLITE_INIT_IN_PROGRESS:
            _LATEST_CLOSE_MAP_SQLITE_CONDITION.wait()
            if db_key in _LATEST_CLOSE_MAP_SQLITE_READY:
                if sqlite_db_path_exists(db_path):
                    return True
                _LATEST_CLOSE_MAP_SQLITE_READY.discard(db_key)

        _LATEST_CLOSE_MAP_SQLITE_INIT_IN_PROGRESS.add(db_key)

    def _initialize_schema() -> None:
        with connect_sqlite(
            db_path,
            timeout_seconds=5,
            pragmas=_LATEST_CLOSE_MAP_SQLITE_INIT_PRAGMAS,
        ) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS realtime_latest_close_map_cache (
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
                CREATE INDEX IF NOT EXISTS idx_realtime_latest_close_map_cache_updated_at
                ON realtime_latest_close_map_cache(updated_at DESC)
                """
            )
            conn.commit()

    initialization_succeeded = False
    try:
        run_sqlite_with_retry(
            _initialize_schema,
            max_retries=_LATEST_CLOSE_MAP_SQLITE_RETRY_ATTEMPTS,
            retry_delay_seconds=_LATEST_CLOSE_MAP_SQLITE_RETRY_DELAY_SECONDS,
        )
        initialization_succeeded = True
        return True
    except Exception as error:
        if logger is not None:
            logger.debug(f"Failed to initialize latest-close sqlite cache: {error}")
        return False
    finally:
        with _LATEST_CLOSE_MAP_SQLITE_CONDITION:
            _LATEST_CLOSE_MAP_SQLITE_INIT_IN_PROGRESS.discard(db_key)
            if initialization_succeeded:
                add_bounded_ready_key(
                    _LATEST_CLOSE_MAP_SQLITE_READY,
                    db_key,
                    max_entries=_LATEST_CLOSE_MAP_SQLITE_READY_MAX_ENTRIES,
                )
            else:
                _LATEST_CLOSE_MAP_SQLITE_READY.discard(db_key)
            _LATEST_CLOSE_MAP_SQLITE_CONDITION.notify_all()


def _load_latest_close_map_from_sqlite(
    *,
    source_path: str,
    signature: tuple[int, int],
    logger: logging.Logger | None,
) -> dict[str, float] | None:
    lookup_keys = _latest_close_source_lookup_keys(source_path)
    lookup_placeholders = build_sqlite_in_placeholders(lookup_keys)
    order_case_sql = build_sqlite_order_case_sql(
        column_name="source_path",
        lookup_keys=lookup_keys,
    )
    source_path_key = lookup_keys[0]
    db_path = _resolve_latest_close_map_cache_db_path(source_path_key)
    if not _ensure_latest_close_map_sqlite(db_path, logger):
        return None

    query_params = (
        *lookup_keys,
        int(signature[0]),
        int(signature[1]),
        *lookup_keys,
    )

    def _query_payload() -> tuple[Any, ...] | None:
        with connect_sqlite(
            db_path,
            timeout_seconds=5,
            pragmas=_LATEST_CLOSE_MAP_SQLITE_SESSION_PRAGMAS,
            read_only=True,
        ) as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"""
                SELECT payload_json
                FROM realtime_latest_close_map_cache
                WHERE source_path IN ({lookup_placeholders})
                  AND mtime_ns = ?
                  AND size_bytes = ?
                ORDER BY {order_case_sql}
                LIMIT 1
                """,
                query_params,
            )
            return cursor.fetchone()

    try:
        row = run_sqlite_with_retry(
            _query_payload,
            max_retries=_LATEST_CLOSE_MAP_SQLITE_RETRY_ATTEMPTS,
            retry_delay_seconds=_LATEST_CLOSE_MAP_SQLITE_RETRY_DELAY_SECONDS,
        )
    except Exception as error:
        if _is_missing_table_error(error) and _recover_latest_close_map_sqlite_schema(db_path, logger):
            try:
                row = run_sqlite_with_retry(
                    _query_payload,
                    max_retries=_LATEST_CLOSE_MAP_SQLITE_RETRY_ATTEMPTS,
                    retry_delay_seconds=_LATEST_CLOSE_MAP_SQLITE_RETRY_DELAY_SECONDS,
                )
            except Exception as retry_error:
                if logger is not None:
                    logger.debug("Failed to load latest-close sqlite cache after schema recovery: %s", retry_error)
                return None
        else:
            if logger is not None:
                logger.debug("Failed to load latest-close sqlite cache: %s", error)
            return None

    try:
        if row is None:
            return None
        loaded = json.loads(str(row[0]))
        if not isinstance(loaded, dict):
            return None
        normalized: dict[str, float] = {}
        for key, value in loaded.items():
            try:
                normalized[str(key)] = float(value or 0)
            except (TypeError, ValueError):
                normalized[str(key)] = 0.0
        return normalized
    except Exception as error:
        if logger is not None:
            logger.debug("Failed to load latest-close sqlite cache: %s", error)
        return None


def _save_latest_close_map_to_sqlite(
    *,
    source_path: str,
    signature: tuple[int, int],
    latest_close_map: dict[str, float],
    logger: logging.Logger | None,
) -> None:
    source_path_key = _normalize_latest_close_source_path(source_path)
    db_path = _resolve_latest_close_map_cache_db_path(source_path_key)
    if not _ensure_latest_close_map_sqlite(db_path, logger):
        return

    normalized_max_rows = max(1, int(_LATEST_CLOSE_MAP_SQLITE_MAX_ROWS))
    should_prune_for_new_path = _mark_latest_close_map_sqlite_source_path_seen(
        db_path=db_path,
        source_path=source_path_key,
    )
    should_force_prune = _should_force_latest_close_map_sqlite_prune()
    should_prune_after_upsert = should_prune_for_new_path or should_force_prune
    try:
        payload_json = json.dumps(latest_close_map, ensure_ascii=False, separators=(",", ":"))
    except Exception as error:
        if logger is not None:
            logger.debug("Failed to serialize latest-close sqlite cache payload: %s", error)
        return

    def _upsert_payload() -> None:
        with connect_sqlite(
            db_path,
            timeout_seconds=5,
            pragmas=_LATEST_CLOSE_MAP_SQLITE_SESSION_PRAGMAS,
        ) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO realtime_latest_close_map_cache (
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
                    source_path_key,
                    int(signature[0]),
                    int(signature[1]),
                    payload_json,
                    datetime.now().isoformat(),
                ),
            )
            if should_prune_after_upsert:
                prune_rows_by_updated_at_if_needed(
                    cursor,
                    table_name="realtime_latest_close_map_cache",
                    max_rows=normalized_max_rows,
                )
            conn.commit()

    try:
        run_sqlite_with_retry(
            _upsert_payload,
            max_retries=_LATEST_CLOSE_MAP_SQLITE_RETRY_ATTEMPTS,
            retry_delay_seconds=_LATEST_CLOSE_MAP_SQLITE_RETRY_DELAY_SECONDS,
        )
    except Exception as error:
        if _is_missing_table_error(error) and _recover_latest_close_map_sqlite_schema(db_path, logger):
            try:
                run_sqlite_with_retry(
                    _upsert_payload,
                    max_retries=_LATEST_CLOSE_MAP_SQLITE_RETRY_ATTEMPTS,
                    retry_delay_seconds=_LATEST_CLOSE_MAP_SQLITE_RETRY_DELAY_SECONDS,
                )
            except Exception as retry_error:
                if logger is not None:
                    logger.debug("Failed to save latest-close sqlite cache after schema recovery: %s", retry_error)
        else:
            if logger is not None:
                logger.debug("Failed to save latest-close sqlite cache: %s", error)


def clear_latest_close_map_cache() -> None:
    with _LATEST_CLOSE_MAP_CACHE_LOCK:
        _LATEST_CLOSE_MAP_CACHE.clear()
    with _LATEST_CLOSE_MAP_SQLITE_KNOWN_PATHS_LOCK:
        _LATEST_CLOSE_MAP_SQLITE_KNOWN_PATHS.clear()
    global _LATEST_CLOSE_MAP_SQLITE_SAVE_COUNTER
    with _LATEST_CLOSE_MAP_SQLITE_SAVE_COUNTER_LOCK:
        _LATEST_CLOSE_MAP_SQLITE_SAVE_COUNTER = 0


def load_cached_latest_close_map(
    *,
    load_csv_file: Callable[[str], pd.DataFrame],
    get_data_path: Callable[[str], str] | None,
    load_csv_readonly: Callable[..., pd.DataFrame],
    build_latest_prices_from_dataframe: Callable[[pd.DataFrame], dict[str, float]],
    logger: logging.Logger | None,
) -> dict[str, float] | None:
    source_path = _resolve_daily_prices_source_path(get_data_path)
    source_path_key = _normalize_latest_close_source_path(source_path) if source_path else None
    if not source_path_key:
        return None

    signature = _file_signature(source_path_key)
    if signature is None:
        return None

    cache_key = (source_path_key, int(signature[0]), int(signature[1]))
    with _LATEST_CLOSE_MAP_CACHE_LOCK:
        cached = _LATEST_CLOSE_MAP_CACHE.get(cache_key)
        if cached is not None:
            _LATEST_CLOSE_MAP_CACHE.move_to_end(cache_key)
    if cached is not None:
        return dict(cached)

    sqlite_cached = _load_latest_close_map_from_sqlite(
        source_path=source_path_key,
        signature=signature,
        logger=logger,
    )
    if sqlite_cached is not None:
        _save_latest_close_memory_entry(
            cache_key=cache_key,
            value=sqlite_cached,
        )
        return dict(sqlite_cached)

    try:
        df_prices = load_csv_readonly(
            load_csv_file,
            "daily_prices.csv",
            usecols=["date", "ticker", "close"],
        )
    except Exception as error:
        if logger is not None:
            logger.debug(f"Failed to load daily_prices for latest-close cache: {error}")
        return None

    if df_prices.empty or "ticker" not in df_prices.columns or "close" not in df_prices.columns:
        return None

    latest_prices = build_latest_prices_from_dataframe(df_prices)
    _save_latest_close_memory_entry(
        cache_key=cache_key,
        value=latest_prices,
    )
    _save_latest_close_map_to_sqlite(
        source_path=source_path_key,
        signature=signature,
        latest_close_map=latest_prices,
        logger=logger,
    )
    return dict(latest_prices)
