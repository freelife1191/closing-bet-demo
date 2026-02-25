#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Signal Tracker 분석용 CSV source cache helper.
"""

from __future__ import annotations

import json
import logging
import os
import threading
from collections import OrderedDict
from datetime import datetime
from io import StringIO
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


logger = logging.getLogger(__name__)

SUPPLY_SOURCE_CACHE: OrderedDict[str, tuple[tuple[int, int, int], pd.DataFrame]] = OrderedDict()
PERFORMANCE_SOURCE_CACHE: OrderedDict[str, tuple[tuple[int, int, int], pd.DataFrame]] = OrderedDict()
SIGNALS_LOG_SOURCE_CACHE: OrderedDict[str, tuple[tuple[int, int, int], pd.DataFrame]] = OrderedDict()
CSV_SOURCE_MEMORY_CACHE_MAX_ENTRIES = 64
CSV_SOURCE_SQLITE_READY_LOCK = threading.Lock()
CSV_SOURCE_SQLITE_READY_CONDITION = threading.Condition(CSV_SOURCE_SQLITE_READY_LOCK)
CSV_SOURCE_SQLITE_INIT_IN_PROGRESS: set[str] = set()
CSV_SOURCE_SQLITE_READY: set[str] = set()
CSV_SOURCE_SQLITE_READY_MAX_ENTRIES = 2_048
CSV_SOURCE_SQLITE_KNOWN_KEYS: OrderedDict[tuple[str, str], None] = OrderedDict()
CSV_SOURCE_SQLITE_KNOWN_KEYS_LOCK = threading.Lock()
CSV_SOURCE_SQLITE_KNOWN_KEYS_MAX_ENTRIES = 8_192
CSV_SOURCE_SQLITE_MAX_ROWS = 128
CSV_SOURCE_SQLITE_PRUNE_FORCE_INTERVAL = 64
CSV_SOURCE_SQLITE_SAVE_COUNTER = 0
CSV_SOURCE_SQLITE_SAVE_COUNTER_LOCK = threading.Lock()
CSV_SOURCE_SQLITE_INIT_PRAGMAS = build_sqlite_pragmas(busy_timeout_ms=30_000)
CSV_SOURCE_SQLITE_SESSION_PRAGMAS = build_sqlite_pragmas(
    busy_timeout_ms=30_000,
    base_pragmas=("PRAGMA temp_store=MEMORY", "PRAGMA cache_size=-4000"),
)
CSV_SOURCE_SQLITE_RETRY_ATTEMPTS = 2
CSV_SOURCE_SQLITE_RETRY_DELAY_SECONDS = 0.03


def _get_source_cache_entry(
    cache: dict[str, tuple[tuple[int, int, int], pd.DataFrame]],
    key: str,
) -> tuple[tuple[int, int, int], pd.DataFrame] | None:
    if key not in cache:
        return None
    value = cache.pop(key)
    cache[key] = value
    return value


def _set_bounded_source_cache_entry(
    cache: dict[str, tuple[tuple[int, int, int], pd.DataFrame]],
    key: str,
    value: tuple[tuple[int, int, int], pd.DataFrame],
) -> None:
    if key in cache:
        cache.pop(key)
    cache[key] = value
    normalized_max_entries = max(1, int(CSV_SOURCE_MEMORY_CACHE_MAX_ENTRIES))
    while len(cache) > normalized_max_entries:
        oldest_key = next(iter(cache))
        cache.pop(oldest_key, None)


def get_file_signature(path: str) -> tuple[int, int, int] | None:
    try:
        stat = os.stat(path)
        return (int(stat.st_ino), int(stat.st_mtime_ns), int(stat.st_size))
    except FileNotFoundError:
        return None
    except Exception:
        return None


def _source_cache_db_path(path: str) -> str:
    return os.path.join(os.path.dirname(path), "runtime_cache.db")


def _normalize_source_path(path: str) -> str:
    return normalize_sqlite_db_key(path)


def _csv_source_lookup_keys(path: str) -> tuple[str, ...]:
    normalized_path = _normalize_source_path(path)
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


def _invalidate_csv_source_sqlite_ready(db_path: str) -> None:
    db_key = normalize_sqlite_db_key(db_path)
    with CSV_SOURCE_SQLITE_READY_LOCK:
        CSV_SOURCE_SQLITE_READY.discard(db_key)
    with CSV_SOURCE_SQLITE_KNOWN_KEYS_LOCK:
        stale_keys = [key for key in CSV_SOURCE_SQLITE_KNOWN_KEYS if key[0] == db_key]
        for tracker_key in stale_keys:
            CSV_SOURCE_SQLITE_KNOWN_KEYS.pop(tracker_key, None)


def _is_missing_table_error(error: Exception) -> bool:
    return is_sqlite_missing_table_error(error, table_names="signal_tracker_csv_source_cache")


def _recover_csv_source_sqlite_schema(db_path: str) -> bool:
    _invalidate_csv_source_sqlite_ready(db_path)
    return _ensure_csv_source_sqlite_cache(db_path)


def _mark_csv_source_sqlite_snapshot_key_seen(*, db_path: str, snapshot_key: str) -> bool:
    """
    (db_path, snapshot_key) 조합을 추적한다.
    return True면 신규 key로 간주해 prune을 수행한다.
    """
    db_key = normalize_sqlite_db_key(db_path)
    tracker_key = (db_key, str(snapshot_key))
    with CSV_SOURCE_SQLITE_KNOWN_KEYS_LOCK:
        if tracker_key in CSV_SOURCE_SQLITE_KNOWN_KEYS:
            CSV_SOURCE_SQLITE_KNOWN_KEYS.move_to_end(tracker_key)
            return False

        CSV_SOURCE_SQLITE_KNOWN_KEYS[tracker_key] = None
        CSV_SOURCE_SQLITE_KNOWN_KEYS.move_to_end(tracker_key)
        normalized_max_entries = max(1, int(CSV_SOURCE_SQLITE_KNOWN_KEYS_MAX_ENTRIES))
        while len(CSV_SOURCE_SQLITE_KNOWN_KEYS) > normalized_max_entries:
            CSV_SOURCE_SQLITE_KNOWN_KEYS.popitem(last=False)
        return True


def _should_force_csv_source_sqlite_prune() -> bool:
    global CSV_SOURCE_SQLITE_SAVE_COUNTER
    with CSV_SOURCE_SQLITE_SAVE_COUNTER_LOCK:
        CSV_SOURCE_SQLITE_SAVE_COUNTER += 1
        normalized_interval = max(1, int(CSV_SOURCE_SQLITE_PRUNE_FORCE_INTERVAL))
        return (CSV_SOURCE_SQLITE_SAVE_COUNTER % normalized_interval) == 0


def _usecols_signature(usecols_filter: set[str] | None) -> str:
    if usecols_filter is None:
        return "__ALL_COLUMNS__"
    return json.dumps(
        sorted(str(column) for column in usecols_filter),
        ensure_ascii=False,
        separators=(",", ":"),
    )


def _ensure_csv_source_sqlite_cache(db_path: str) -> bool:
    db_key = normalize_sqlite_db_key(db_path)
    with CSV_SOURCE_SQLITE_READY_CONDITION:
        if db_key in CSV_SOURCE_SQLITE_READY:
            if sqlite_db_path_exists(db_path):
                return True
            CSV_SOURCE_SQLITE_READY.discard(db_key)

        while db_key in CSV_SOURCE_SQLITE_INIT_IN_PROGRESS:
            CSV_SOURCE_SQLITE_READY_CONDITION.wait()
            if db_key in CSV_SOURCE_SQLITE_READY:
                if sqlite_db_path_exists(db_path):
                    return True
                CSV_SOURCE_SQLITE_READY.discard(db_key)

        CSV_SOURCE_SQLITE_INIT_IN_PROGRESS.add(db_key)

    def _initialize_schema() -> None:
        with connect_sqlite(
            db_path,
            timeout_seconds=30,
            pragmas=CSV_SOURCE_SQLITE_INIT_PRAGMAS,
        ) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS signal_tracker_csv_source_cache (
                    source_path TEXT NOT NULL,
                    cache_kind TEXT NOT NULL,
                    usecols_signature TEXT NOT NULL,
                    inode INTEGER NOT NULL,
                    mtime_ns INTEGER NOT NULL,
                    size INTEGER NOT NULL,
                    payload_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (source_path, cache_kind, usecols_signature)
                )
                """
            )
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_signal_tracker_csv_source_cache_updated_at
                ON signal_tracker_csv_source_cache(updated_at DESC)
                """
            )
            conn.commit()

    initialization_succeeded = False
    try:
        run_sqlite_with_retry(
            _initialize_schema,
            max_retries=CSV_SOURCE_SQLITE_RETRY_ATTEMPTS,
            retry_delay_seconds=CSV_SOURCE_SQLITE_RETRY_DELAY_SECONDS,
        )
        initialization_succeeded = True
        return True
    except Exception as error:
        logger.debug("Failed to initialize signal tracker sqlite cache: %s", error)
        return False
    finally:
        with CSV_SOURCE_SQLITE_READY_CONDITION:
            CSV_SOURCE_SQLITE_INIT_IN_PROGRESS.discard(db_key)
            if initialization_succeeded:
                add_bounded_ready_key(
                    CSV_SOURCE_SQLITE_READY,
                    db_key,
                    max_entries=CSV_SOURCE_SQLITE_READY_MAX_ENTRIES,
                )
            else:
                CSV_SOURCE_SQLITE_READY.discard(db_key)
            CSV_SOURCE_SQLITE_READY_CONDITION.notify_all()


def _load_csv_source_from_sqlite(
    *,
    path: str,
    signature: tuple[int, int, int],
    usecols_filter: set[str] | None,
    cache_kind: str,
) -> pd.DataFrame | None:
    lookup_keys = _csv_source_lookup_keys(path)
    lookup_placeholders = build_sqlite_in_placeholders(lookup_keys)
    order_case_sql = build_sqlite_order_case_sql(
        column_name="source_path",
        lookup_keys=lookup_keys,
    )
    normalized_source_path = lookup_keys[0]
    db_path = _source_cache_db_path(normalized_source_path)
    if not _ensure_csv_source_sqlite_cache(db_path):
        return None
    usecols_signature = _usecols_signature(usecols_filter)
    query_params = (
        *lookup_keys,
        cache_kind,
        usecols_signature,
        int(signature[0]),
        int(signature[1]),
        int(signature[2]),
        *lookup_keys,
    )

    def _query_row() -> tuple[Any, ...] | None:
        with connect_sqlite(
            db_path,
            timeout_seconds=30,
            pragmas=CSV_SOURCE_SQLITE_SESSION_PRAGMAS,
            read_only=True,
        ) as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"""
                SELECT payload_json
                FROM signal_tracker_csv_source_cache
                WHERE source_path IN ({lookup_placeholders})
                  AND cache_kind = ?
                  AND usecols_signature = ?
                  AND inode = ?
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
            max_retries=CSV_SOURCE_SQLITE_RETRY_ATTEMPTS,
            retry_delay_seconds=CSV_SOURCE_SQLITE_RETRY_DELAY_SECONDS,
        )
    except Exception as error:
        if _is_missing_table_error(error) and _recover_csv_source_sqlite_schema(db_path):
            try:
                row = run_sqlite_with_retry(
                    _query_row,
                    max_retries=CSV_SOURCE_SQLITE_RETRY_ATTEMPTS,
                    retry_delay_seconds=CSV_SOURCE_SQLITE_RETRY_DELAY_SECONDS,
                )
            except Exception as retry_error:
                logger.debug(
                    "Failed to load signal tracker sqlite cache after schema recovery: %s",
                    retry_error,
                )
                return None
        else:
            logger.debug("Failed to load signal tracker sqlite cache: %s", error)
            return None

    try:
        if not row:
            return None
        payload_json = row[0]
        if not isinstance(payload_json, str) or not payload_json:
            return None
        return pd.read_json(StringIO(payload_json), orient="records")
    except Exception as error:
        logger.debug("Failed to load signal tracker sqlite cache: %s", error)
        return None


def _save_csv_source_to_sqlite(
    *,
    path: str,
    signature: tuple[int, int, int],
    usecols_filter: set[str] | None,
    cache_kind: str,
    payload: pd.DataFrame,
) -> None:
    normalized_source_path = _normalize_source_path(path)
    db_path = _source_cache_db_path(normalized_source_path)
    if not _ensure_csv_source_sqlite_cache(db_path):
        return
    usecols_signature = _usecols_signature(usecols_filter)

    try:
        payload_json = payload.to_json(orient="records", force_ascii=False, date_format="iso")
    except Exception as error:
        logger.debug("Failed to serialize signal tracker cache payload: %s", error)
        return

    normalized_max_rows = max(1, int(CSV_SOURCE_SQLITE_MAX_ROWS))
    snapshot_key = f"{normalized_source_path}::{cache_kind}::{usecols_signature}"
    should_prune_for_new_key = _mark_csv_source_sqlite_snapshot_key_seen(
        db_path=db_path,
        snapshot_key=snapshot_key,
    )
    should_force_prune = _should_force_csv_source_sqlite_prune()
    should_prune_after_upsert = should_prune_for_new_key or should_force_prune

    def _upsert_payload() -> None:
        with connect_sqlite(
            db_path,
            timeout_seconds=30,
            pragmas=CSV_SOURCE_SQLITE_SESSION_PRAGMAS,
        ) as conn:
            now_iso = datetime.now().isoformat()
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO signal_tracker_csv_source_cache (
                    source_path,
                    cache_kind,
                    usecols_signature,
                    inode,
                    mtime_ns,
                    size,
                    payload_json,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(source_path, cache_kind, usecols_signature) DO UPDATE SET
                    inode = excluded.inode,
                    mtime_ns = excluded.mtime_ns,
                    size = excluded.size,
                    payload_json = excluded.payload_json,
                    updated_at = excluded.updated_at
                """,
                (
                    normalized_source_path,
                    cache_kind,
                    usecols_signature,
                    int(signature[0]),
                    int(signature[1]),
                    int(signature[2]),
                    payload_json,
                    now_iso,
                ),
            )
            if should_prune_after_upsert:
                prune_rows_by_updated_at_if_needed(
                    cursor,
                    table_name="signal_tracker_csv_source_cache",
                    max_rows=normalized_max_rows,
                )
            conn.commit()

    try:
        run_sqlite_with_retry(
            _upsert_payload,
            max_retries=CSV_SOURCE_SQLITE_RETRY_ATTEMPTS,
            retry_delay_seconds=CSV_SOURCE_SQLITE_RETRY_DELAY_SECONDS,
        )
    except Exception as error:
        if _is_missing_table_error(error) and _recover_csv_source_sqlite_schema(db_path):
            try:
                run_sqlite_with_retry(
                    _upsert_payload,
                    max_retries=CSV_SOURCE_SQLITE_RETRY_ATTEMPTS,
                    retry_delay_seconds=CSV_SOURCE_SQLITE_RETRY_DELAY_SECONDS,
                )
            except Exception as retry_error:
                logger.debug(
                    "Failed to save signal tracker sqlite cache after schema recovery: %s",
                    retry_error,
                )
        else:
            logger.debug("Failed to save signal tracker sqlite cache: %s", error)


def load_csv_with_signature_cache(
    *,
    path: str,
    usecols_filter: set[str] | None,
    cache: dict[str, tuple[tuple[int, int, int], pd.DataFrame]],
    sqlite_cache_kind: str | None = None,
    dtype: dict[str, Any] | None = None,
) -> pd.DataFrame:
    normalized_path = _normalize_source_path(path)
    signature = get_file_signature(normalized_path)
    if signature is not None:
        cached = _get_source_cache_entry(cache, normalized_path)
        if cached and cached[0] == signature:
            return cached[1]

        if sqlite_cache_kind:
            sqlite_cached = _load_csv_source_from_sqlite(
                path=normalized_path,
                signature=signature,
                usecols_filter=usecols_filter,
                cache_kind=sqlite_cache_kind,
            )
            if sqlite_cached is not None:
                _set_bounded_source_cache_entry(
                    cache,
                    normalized_path,
                    (signature, sqlite_cached),
                )
                return sqlite_cached
    else:
        cache.pop(normalized_path, None)

    read_kwargs: dict[str, Any] = {
        "encoding": "utf-8-sig",
        "low_memory": False,
    }
    if usecols_filter is not None:
        read_kwargs["usecols"] = lambda column: column in usecols_filter
    if dtype is not None:
        read_kwargs["dtype"] = dtype

    loaded = pd.read_csv(normalized_path, **read_kwargs)
    refreshed_signature = get_file_signature(normalized_path)
    if refreshed_signature is not None:
        _set_bounded_source_cache_entry(
            cache,
            normalized_path,
            (refreshed_signature, loaded),
        )
        if sqlite_cache_kind:
            _save_csv_source_to_sqlite(
                path=normalized_path,
                signature=refreshed_signature,
                usecols_filter=usecols_filter,
                cache_kind=sqlite_cache_kind,
                payload=loaded,
            )
    else:
        cache.pop(normalized_path, None)
    return loaded


def refresh_csv_signature_cache_snapshot(
    *,
    path: str,
    frame: pd.DataFrame,
    cache: dict[str, tuple[tuple[int, int, int], pd.DataFrame]],
    sqlite_cache_kind: str | None = None,
    usecols_filter: set[str] | None = None,
) -> tuple[int, int, int] | None:
    """
    파일 저장 직후 in-memory/SQLite source cache를 최신 스냅샷으로 갱신한다.
    """
    normalized_path = _normalize_source_path(path)
    if not isinstance(frame, pd.DataFrame):
        cache.pop(normalized_path, None)
        return None

    signature = get_file_signature(normalized_path)
    if signature is None:
        cache.pop(normalized_path, None)
        return None

    normalized_frame = frame.copy()
    if usecols_filter is not None:
        selected_columns = [column for column in normalized_frame.columns if column in usecols_filter]
        normalized_frame = normalized_frame.loc[:, selected_columns]

    _set_bounded_source_cache_entry(
        cache,
        normalized_path,
        (signature, normalized_frame),
    )
    if sqlite_cache_kind:
        _save_csv_source_to_sqlite(
            path=normalized_path,
            signature=signature,
            usecols_filter=usecols_filter,
            cache_kind=sqlite_cache_kind,
            payload=normalized_frame,
        )
    return signature
