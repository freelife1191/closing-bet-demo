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
from collections import OrderedDict
from datetime import datetime
from typing import Callable

import pandas as pd

from services.kr_market_csv_utils import load_csv_readonly as _load_csv_readonly
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


_MARKET_MAP_CACHE_LOCK = threading.Lock()
_MARKET_MAP_CACHE: OrderedDict[tuple[str, int, int], dict[str, str]] = OrderedDict()
_MARKET_MAP_MEMORY_MAX_ENTRIES = 16
_MARKET_MAP_SQLITE_READY: set[str] = set()
_MARKET_MAP_SQLITE_LOCK = threading.Lock()
_MARKET_MAP_SQLITE_CONDITION = threading.Condition(_MARKET_MAP_SQLITE_LOCK)
_MARKET_MAP_SQLITE_INIT_IN_PROGRESS: set[str] = set()
_MARKET_MAP_SQLITE_READY_MAX_ENTRIES = 2_048
_MARKET_MAP_SQLITE_KNOWN_PATHS: OrderedDict[tuple[str, str], None] = OrderedDict()
_MARKET_MAP_SQLITE_KNOWN_PATHS_LOCK = threading.Lock()
_MARKET_MAP_SQLITE_KNOWN_PATHS_MAX_ENTRIES = 4_096
_MARKET_MAP_SQLITE_MAX_ROWS = 200
_MARKET_MAP_SQLITE_PRUNE_FORCE_INTERVAL = 64
_MARKET_MAP_SQLITE_SAVE_COUNTER = 0
_MARKET_MAP_SQLITE_SAVE_COUNTER_LOCK = threading.Lock()
_MARKET_MAP_SQLITE_INIT_PRAGMAS = build_sqlite_pragmas(busy_timeout_ms=5_000)
_MARKET_MAP_SQLITE_SESSION_PRAGMAS = build_sqlite_pragmas(
    busy_timeout_ms=5_000,
    base_pragmas=("PRAGMA temp_store=MEMORY", "PRAGMA cache_size=-4000"),
)
_MARKET_MAP_SQLITE_RETRY_ATTEMPTS = 2
_MARKET_MAP_SQLITE_RETRY_DELAY_SECONDS = 0.03


def _save_market_map_memory_entry(
    *,
    cache_key: tuple[str, int, int],
    value: dict[str, str],
) -> None:
    normalized_max_entries = max(1, int(_MARKET_MAP_MEMORY_MAX_ENTRIES))
    with _MARKET_MAP_CACHE_LOCK:
        _MARKET_MAP_CACHE[cache_key] = dict(value)
        _MARKET_MAP_CACHE.move_to_end(cache_key)
        while len(_MARKET_MAP_CACHE) > normalized_max_entries:
            _MARKET_MAP_CACHE.popitem(last=False)


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


def _normalize_market_map_source_path(path: str) -> str:
    return normalize_sqlite_db_key(path)


def _market_map_source_lookup_keys(path: str) -> tuple[str, ...]:
    normalized_path = _normalize_market_map_source_path(path)
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


def _invalidate_market_map_sqlite_ready(db_path: str) -> None:
    db_key = normalize_sqlite_db_key(db_path)
    with _MARKET_MAP_SQLITE_CONDITION:
        _MARKET_MAP_SQLITE_READY.discard(db_key)
    with _MARKET_MAP_SQLITE_KNOWN_PATHS_LOCK:
        stale_keys = [key for key in _MARKET_MAP_SQLITE_KNOWN_PATHS if key[0] == db_key]
        for tracker_key in stale_keys:
            _MARKET_MAP_SQLITE_KNOWN_PATHS.pop(tracker_key, None)


def _is_missing_table_error(error: Exception) -> bool:
    return is_sqlite_missing_table_error(error, table_names="realtime_market_map_cache")


def _recover_market_map_sqlite_schema(db_path: str, logger: logging.Logger | None) -> bool:
    _invalidate_market_map_sqlite_ready(db_path)
    return _ensure_market_map_sqlite(db_path, logger)


def _mark_market_map_sqlite_source_path_seen(*, db_path: str, source_path: str) -> bool:
    """
    (db_path, source_path) 조합을 추적한다.
    return True면 신규 key로 간주해 prune을 수행한다.
    """
    db_key = normalize_sqlite_db_key(db_path)
    source_path_key = _normalize_market_map_source_path(source_path)
    tracker_key = (db_key, source_path_key)
    with _MARKET_MAP_SQLITE_KNOWN_PATHS_LOCK:
        if tracker_key in _MARKET_MAP_SQLITE_KNOWN_PATHS:
            _MARKET_MAP_SQLITE_KNOWN_PATHS.move_to_end(tracker_key)
            return False

        _MARKET_MAP_SQLITE_KNOWN_PATHS[tracker_key] = None
        _MARKET_MAP_SQLITE_KNOWN_PATHS.move_to_end(tracker_key)
        normalized_max_entries = max(1, int(_MARKET_MAP_SQLITE_KNOWN_PATHS_MAX_ENTRIES))
        while len(_MARKET_MAP_SQLITE_KNOWN_PATHS) > normalized_max_entries:
            _MARKET_MAP_SQLITE_KNOWN_PATHS.popitem(last=False)
        return True


def _should_force_market_map_sqlite_prune() -> bool:
    global _MARKET_MAP_SQLITE_SAVE_COUNTER
    with _MARKET_MAP_SQLITE_SAVE_COUNTER_LOCK:
        _MARKET_MAP_SQLITE_SAVE_COUNTER += 1
        normalized_interval = max(1, int(_MARKET_MAP_SQLITE_PRUNE_FORCE_INTERVAL))
        return (_MARKET_MAP_SQLITE_SAVE_COUNTER % normalized_interval) == 0


def _ensure_market_map_sqlite(db_path: str, logger: logging.Logger | None) -> bool:
    db_key = normalize_sqlite_db_key(db_path)
    with _MARKET_MAP_SQLITE_CONDITION:
        if db_key in _MARKET_MAP_SQLITE_READY:
            if sqlite_db_path_exists(db_path):
                return True
            _MARKET_MAP_SQLITE_READY.discard(db_key)

        while db_key in _MARKET_MAP_SQLITE_INIT_IN_PROGRESS:
            _MARKET_MAP_SQLITE_CONDITION.wait()
            if db_key in _MARKET_MAP_SQLITE_READY:
                if sqlite_db_path_exists(db_path):
                    return True
                _MARKET_MAP_SQLITE_READY.discard(db_key)

        _MARKET_MAP_SQLITE_INIT_IN_PROGRESS.add(db_key)

    def _initialize_schema() -> None:
        with connect_sqlite(
            db_path,
            timeout_seconds=5,
            pragmas=_MARKET_MAP_SQLITE_INIT_PRAGMAS,
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

    initialization_succeeded = False
    try:
        run_sqlite_with_retry(
            _initialize_schema,
            max_retries=_MARKET_MAP_SQLITE_RETRY_ATTEMPTS,
            retry_delay_seconds=_MARKET_MAP_SQLITE_RETRY_DELAY_SECONDS,
        )
        initialization_succeeded = True
        return True
    except Exception as error:
        if logger is not None:
            logger.debug(f"Failed to initialize market map sqlite cache: {error}")
        return False
    finally:
        with _MARKET_MAP_SQLITE_CONDITION:
            _MARKET_MAP_SQLITE_INIT_IN_PROGRESS.discard(db_key)
            if initialization_succeeded:
                add_bounded_ready_key(
                    _MARKET_MAP_SQLITE_READY,
                    db_key,
                    max_entries=_MARKET_MAP_SQLITE_READY_MAX_ENTRIES,
                )
            else:
                _MARKET_MAP_SQLITE_READY.discard(db_key)
            _MARKET_MAP_SQLITE_CONDITION.notify_all()


def _load_market_map_from_sqlite(
    *,
    source_path: str,
    signature: tuple[int, int],
    logger: logging.Logger | None,
) -> dict[str, str] | None:
    lookup_keys = _market_map_source_lookup_keys(source_path)
    lookup_placeholders = build_sqlite_in_placeholders(lookup_keys)
    order_case_sql = build_sqlite_order_case_sql(
        column_name="source_path",
        lookup_keys=lookup_keys,
    )
    source_path_key = lookup_keys[0]
    db_path = _resolve_market_map_cache_db_path(source_path_key)
    if not _ensure_market_map_sqlite(db_path, logger):
        return None

    query_params = (
        *lookup_keys,
        int(signature[0]),
        int(signature[1]),
        *lookup_keys,
    )

    def _query_payload() -> tuple[object, ...] | None:
        with connect_sqlite(
            db_path,
            timeout_seconds=5,
            pragmas=_MARKET_MAP_SQLITE_SESSION_PRAGMAS,
            read_only=True,
        ) as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"""
                SELECT payload_json
                FROM realtime_market_map_cache
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
            max_retries=_MARKET_MAP_SQLITE_RETRY_ATTEMPTS,
            retry_delay_seconds=_MARKET_MAP_SQLITE_RETRY_DELAY_SECONDS,
        )
    except Exception as error:
        if _is_missing_table_error(error) and _recover_market_map_sqlite_schema(db_path, logger):
            try:
                row = run_sqlite_with_retry(
                    _query_payload,
                    max_retries=_MARKET_MAP_SQLITE_RETRY_ATTEMPTS,
                    retry_delay_seconds=_MARKET_MAP_SQLITE_RETRY_DELAY_SECONDS,
                )
            except Exception as retry_error:
                if logger is not None:
                    logger.debug("Failed to load market map sqlite cache after schema recovery: %s", retry_error)
                return None
        else:
            if logger is not None:
                logger.debug("Failed to load market map sqlite cache: %s", error)
            return None

    try:
        if row is None:
            return None
        loaded = json.loads(str(row[0]))
        if not isinstance(loaded, dict):
            return None
        return {str(key): str(value) for key, value in loaded.items()}
    except Exception as error:
        if logger is not None:
            logger.debug("Failed to load market map sqlite cache: %s", error)
        return None


def _save_market_map_to_sqlite(
    *,
    source_path: str,
    signature: tuple[int, int],
    market_map: dict[str, str],
    logger: logging.Logger | None,
) -> None:
    source_path_key = _normalize_market_map_source_path(source_path)
    db_path = _resolve_market_map_cache_db_path(source_path_key)
    if not _ensure_market_map_sqlite(db_path, logger):
        return

    normalized_max_rows = max(1, int(_MARKET_MAP_SQLITE_MAX_ROWS))
    should_prune_for_new_path = _mark_market_map_sqlite_source_path_seen(
        db_path=db_path,
        source_path=source_path_key,
    )
    should_force_prune = _should_force_market_map_sqlite_prune()
    should_prune_after_upsert = should_prune_for_new_path or should_force_prune
    try:
        payload_json = json.dumps(market_map, ensure_ascii=False, separators=(",", ":"))
    except Exception as error:
        if logger is not None:
            logger.debug("Failed to serialize market map sqlite cache payload: %s", error)
        return

    def _upsert_payload() -> None:
        with connect_sqlite(
            db_path,
            timeout_seconds=5,
            pragmas=_MARKET_MAP_SQLITE_SESSION_PRAGMAS,
        ) as conn:
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
                    table_name="realtime_market_map_cache",
                    max_rows=normalized_max_rows,
                )
            conn.commit()

    try:
        run_sqlite_with_retry(
            _upsert_payload,
            max_retries=_MARKET_MAP_SQLITE_RETRY_ATTEMPTS,
            retry_delay_seconds=_MARKET_MAP_SQLITE_RETRY_DELAY_SECONDS,
        )
    except Exception as error:
        if _is_missing_table_error(error) and _recover_market_map_sqlite_schema(db_path, logger):
            try:
                run_sqlite_with_retry(
                    _upsert_payload,
                    max_retries=_MARKET_MAP_SQLITE_RETRY_ATTEMPTS,
                    retry_delay_seconds=_MARKET_MAP_SQLITE_RETRY_DELAY_SECONDS,
                )
            except Exception as retry_error:
                if logger is not None:
                    logger.debug("Failed to save market map sqlite cache after schema recovery: %s", retry_error)
        else:
            if logger is not None:
                logger.debug("Failed to save market map sqlite cache: %s", error)


def clear_market_map_cache() -> None:
    with _MARKET_MAP_CACHE_LOCK:
        _MARKET_MAP_CACHE.clear()
    with _MARKET_MAP_SQLITE_KNOWN_PATHS_LOCK:
        _MARKET_MAP_SQLITE_KNOWN_PATHS.clear()
    global _MARKET_MAP_SQLITE_SAVE_COUNTER
    with _MARKET_MAP_SQLITE_SAVE_COUNTER_LOCK:
        _MARKET_MAP_SQLITE_SAVE_COUNTER = 0


def build_market_map(
    load_csv_file: Callable[[str], pd.DataFrame],
    logger: logging.Logger | None = None,
    get_data_path: Callable[[str], str] | None = None,
) -> dict[str, str]:
    source_path = _resolve_market_map_source_path(get_data_path)
    source_path_key = _normalize_market_map_source_path(source_path) if source_path else None
    signature = _file_signature(source_path_key) if source_path_key else None

    cache_key: tuple[str, int, int] | None = None
    if source_path_key and signature is not None:
        cache_key = (source_path_key, int(signature[0]), int(signature[1]))
        with _MARKET_MAP_CACHE_LOCK:
            cached = _MARKET_MAP_CACHE.get(cache_key)
            if cached is not None:
                _MARKET_MAP_CACHE.move_to_end(cache_key)
        if cached is not None:
            return dict(cached)

        sqlite_cached = _load_market_map_from_sqlite(
            source_path=source_path_key,
            signature=signature,
            logger=logger,
        )
        if sqlite_cached is not None:
            _save_market_map_memory_entry(
                cache_key=cache_key,
                value=sqlite_cached,
            )
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

    if cache_key is not None and signature is not None and source_path_key:
        _save_market_map_memory_entry(
            cache_key=cache_key,
            value=result,
        )
        _save_market_map_to_sqlite(
            source_path=source_path_key,
            signature=signature,
            market_map=result,
            logger=logger,
        )

    return result
