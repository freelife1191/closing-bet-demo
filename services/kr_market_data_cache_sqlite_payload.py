#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KR Market Data Cache - SQLite payload snapshot helpers
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
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


_LOGGER = logging.getLogger(__name__)
_PAYLOAD_SQLITE_INIT_PRAGMAS = build_sqlite_pragmas(busy_timeout_ms=30_000)
_PAYLOAD_SQLITE_SESSION_PRAGMAS = build_sqlite_pragmas(
    busy_timeout_ms=30_000,
    base_pragmas=("PRAGMA temp_store=MEMORY", "PRAGMA cache_size=-4000"),
)
_PAYLOAD_SQLITE_RETRY_ATTEMPTS = 2
_PAYLOAD_SQLITE_RETRY_DELAY_SECONDS = 0.03

JSON_PAYLOAD_SQLITE_READY: set[str] = set()
JSON_PAYLOAD_SQLITE_READY_LOCK = threading.Lock()
JSON_PAYLOAD_SQLITE_READY_CONDITION = threading.Condition(JSON_PAYLOAD_SQLITE_READY_LOCK)
JSON_PAYLOAD_SQLITE_IN_PROGRESS: set[str] = set()
JSON_PAYLOAD_SQLITE_READY_MAX_ENTRIES = 2_048
JSON_PAYLOAD_SQLITE_KNOWN_KEYS: OrderedDict[tuple[str, str], None] = OrderedDict()
JSON_PAYLOAD_SQLITE_KNOWN_KEYS_LOCK = threading.Lock()
JSON_PAYLOAD_SQLITE_KNOWN_KEYS_MAX_ENTRIES = 8_192
JSON_PAYLOAD_SQLITE_PRUNE_FORCE_INTERVAL = 64
JSON_PAYLOAD_SQLITE_SAVE_COUNTER = 0
JSON_PAYLOAD_SQLITE_SAVE_COUNTER_LOCK = threading.Lock()
DEFAULT_JSON_PAYLOAD_SQLITE_MAX_ROWS = 256
CSV_PAYLOAD_SQLITE_READY: set[str] = set()
CSV_PAYLOAD_SQLITE_READY_LOCK = threading.Lock()
CSV_PAYLOAD_SQLITE_READY_CONDITION = threading.Condition(CSV_PAYLOAD_SQLITE_READY_LOCK)
CSV_PAYLOAD_SQLITE_IN_PROGRESS: set[str] = set()
CSV_PAYLOAD_SQLITE_READY_MAX_ENTRIES = 2_048
CSV_PAYLOAD_SQLITE_KNOWN_KEYS: OrderedDict[tuple[str, str], None] = OrderedDict()
CSV_PAYLOAD_SQLITE_KNOWN_KEYS_LOCK = threading.Lock()
CSV_PAYLOAD_SQLITE_KNOWN_KEYS_MAX_ENTRIES = 8_192
CSV_PAYLOAD_SQLITE_PRUNE_FORCE_INTERVAL = 64
CSV_PAYLOAD_SQLITE_SAVE_COUNTER = 0
CSV_PAYLOAD_SQLITE_SAVE_COUNTER_LOCK = threading.Lock()
DEFAULT_CSV_PAYLOAD_SQLITE_MAX_ROWS = 256


def _normalize_payload_filepath(path: str) -> str:
    return normalize_sqlite_db_key(path)


def _payload_filepath_lookup_keys(path: str) -> tuple[str, ...]:
    normalized_path = _normalize_payload_filepath(path)
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


def resolve_payload_sqlite_db_path(filepath: str) -> str:
    normalized_filepath = _normalize_payload_filepath(filepath)
    return os.path.join(os.path.dirname(normalized_filepath), "runtime_cache.db")


def _is_missing_table_error(error: Exception, *, table_name: str) -> bool:
    return is_sqlite_missing_table_error(error, table_names=table_name)


def _invalidate_json_payload_sqlite_ready(db_path: str) -> None:
    db_key = normalize_sqlite_db_key(db_path)
    with JSON_PAYLOAD_SQLITE_READY_LOCK:
        JSON_PAYLOAD_SQLITE_READY.discard(db_key)
    with JSON_PAYLOAD_SQLITE_KNOWN_KEYS_LOCK:
        stale_keys = [key for key in JSON_PAYLOAD_SQLITE_KNOWN_KEYS if key[0] == db_key]
        for tracker_key in stale_keys:
            JSON_PAYLOAD_SQLITE_KNOWN_KEYS.pop(tracker_key, None)


def _invalidate_csv_payload_sqlite_ready(db_path: str) -> None:
    db_key = normalize_sqlite_db_key(db_path)
    with CSV_PAYLOAD_SQLITE_READY_LOCK:
        CSV_PAYLOAD_SQLITE_READY.discard(db_key)
    with CSV_PAYLOAD_SQLITE_KNOWN_KEYS_LOCK:
        stale_keys = [key for key in CSV_PAYLOAD_SQLITE_KNOWN_KEYS if key[0] == db_key]
        for tracker_key in stale_keys:
            CSV_PAYLOAD_SQLITE_KNOWN_KEYS.pop(tracker_key, None)


def _mark_json_payload_sqlite_snapshot_key_seen(*, db_path: str, snapshot_key: str) -> bool:
    """
    (db_path, snapshot_key) 조합을 추적한다.
    return True면 신규 key로 간주해 prune을 수행한다.
    """
    db_key = normalize_sqlite_db_key(db_path)
    tracker_key = (db_key, str(snapshot_key))
    with JSON_PAYLOAD_SQLITE_KNOWN_KEYS_LOCK:
        if tracker_key in JSON_PAYLOAD_SQLITE_KNOWN_KEYS:
            JSON_PAYLOAD_SQLITE_KNOWN_KEYS.move_to_end(tracker_key)
            return False

        JSON_PAYLOAD_SQLITE_KNOWN_KEYS[tracker_key] = None
        JSON_PAYLOAD_SQLITE_KNOWN_KEYS.move_to_end(tracker_key)
        normalized_max_entries = max(1, int(JSON_PAYLOAD_SQLITE_KNOWN_KEYS_MAX_ENTRIES))
        while len(JSON_PAYLOAD_SQLITE_KNOWN_KEYS) > normalized_max_entries:
            JSON_PAYLOAD_SQLITE_KNOWN_KEYS.popitem(last=False)
        return True


def _should_force_json_payload_sqlite_prune() -> bool:
    global JSON_PAYLOAD_SQLITE_SAVE_COUNTER
    with JSON_PAYLOAD_SQLITE_SAVE_COUNTER_LOCK:
        JSON_PAYLOAD_SQLITE_SAVE_COUNTER += 1
        normalized_interval = max(1, int(JSON_PAYLOAD_SQLITE_PRUNE_FORCE_INTERVAL))
        return (JSON_PAYLOAD_SQLITE_SAVE_COUNTER % normalized_interval) == 0


def _mark_csv_payload_sqlite_snapshot_key_seen(*, db_path: str, snapshot_key: str) -> bool:
    """
    (db_path, snapshot_key) 조합을 추적한다.
    return True면 신규 key로 간주해 prune을 수행한다.
    """
    db_key = normalize_sqlite_db_key(db_path)
    tracker_key = (db_key, str(snapshot_key))
    with CSV_PAYLOAD_SQLITE_KNOWN_KEYS_LOCK:
        if tracker_key in CSV_PAYLOAD_SQLITE_KNOWN_KEYS:
            CSV_PAYLOAD_SQLITE_KNOWN_KEYS.move_to_end(tracker_key)
            return False

        CSV_PAYLOAD_SQLITE_KNOWN_KEYS[tracker_key] = None
        CSV_PAYLOAD_SQLITE_KNOWN_KEYS.move_to_end(tracker_key)
        normalized_max_entries = max(1, int(CSV_PAYLOAD_SQLITE_KNOWN_KEYS_MAX_ENTRIES))
        while len(CSV_PAYLOAD_SQLITE_KNOWN_KEYS) > normalized_max_entries:
            CSV_PAYLOAD_SQLITE_KNOWN_KEYS.popitem(last=False)
        return True


def _should_force_csv_payload_sqlite_prune() -> bool:
    global CSV_PAYLOAD_SQLITE_SAVE_COUNTER
    with CSV_PAYLOAD_SQLITE_SAVE_COUNTER_LOCK:
        CSV_PAYLOAD_SQLITE_SAVE_COUNTER += 1
        normalized_interval = max(1, int(CSV_PAYLOAD_SQLITE_PRUNE_FORCE_INTERVAL))
        return (CSV_PAYLOAD_SQLITE_SAVE_COUNTER % normalized_interval) == 0


def _ensure_json_payload_sqlite_cache(db_path: str, logger: logging.Logger) -> bool:
    db_key = normalize_sqlite_db_key(db_path)
    with JSON_PAYLOAD_SQLITE_READY_CONDITION:
        if db_key in JSON_PAYLOAD_SQLITE_READY:
            if sqlite_db_path_exists(db_path):
                return True
            JSON_PAYLOAD_SQLITE_READY.discard(db_key)

        while db_key in JSON_PAYLOAD_SQLITE_IN_PROGRESS:
            JSON_PAYLOAD_SQLITE_READY_CONDITION.wait()
            if db_key in JSON_PAYLOAD_SQLITE_READY:
                if sqlite_db_path_exists(db_path):
                    return True
                JSON_PAYLOAD_SQLITE_READY.discard(db_key)

        JSON_PAYLOAD_SQLITE_IN_PROGRESS.add(db_key)

    def _initialize_schema() -> None:
        with connect_sqlite(
            db_path,
            timeout_seconds=30,
            pragmas=_PAYLOAD_SQLITE_INIT_PRAGMAS,
        ) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS json_file_payload_cache (
                    filepath TEXT PRIMARY KEY,
                    mtime_ns INTEGER NOT NULL,
                    size INTEGER NOT NULL,
                    payload_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_json_file_payload_cache_updated_at
                ON json_file_payload_cache(updated_at DESC)
                """
            )
            conn.commit()

    initialization_succeeded = False
    try:
        run_sqlite_with_retry(
            _initialize_schema,
            max_retries=_PAYLOAD_SQLITE_RETRY_ATTEMPTS,
            retry_delay_seconds=_PAYLOAD_SQLITE_RETRY_DELAY_SECONDS,
        )
        initialization_succeeded = True
        return True
    except Exception as error:
        logger.debug(f"Failed to initialize JSON payload SQLite cache: {error}")
        return False
    finally:
        with JSON_PAYLOAD_SQLITE_READY_CONDITION:
            JSON_PAYLOAD_SQLITE_IN_PROGRESS.discard(db_key)
            if initialization_succeeded:
                add_bounded_ready_key(
                    JSON_PAYLOAD_SQLITE_READY,
                    db_key,
                    max_entries=JSON_PAYLOAD_SQLITE_READY_MAX_ENTRIES,
                )
            else:
                JSON_PAYLOAD_SQLITE_READY.discard(db_key)
            JSON_PAYLOAD_SQLITE_READY_CONDITION.notify_all()


def _recover_json_payload_sqlite_schema(db_path: str, logger: logging.Logger) -> bool:
    _invalidate_json_payload_sqlite_ready(db_path)
    return _ensure_json_payload_sqlite_cache(db_path, logger)


def load_json_payload_from_sqlite(
    *,
    filepath: str,
    signature: tuple[int, int],
    logger: logging.Logger | None = None,
) -> tuple[bool, dict[str, Any]]:
    logger = logger or _LOGGER
    lookup_keys = _payload_filepath_lookup_keys(filepath)
    lookup_placeholders = build_sqlite_in_placeholders(lookup_keys)
    order_case_sql = build_sqlite_order_case_sql(
        column_name="filepath",
        lookup_keys=lookup_keys,
    )
    normalized_filepath = lookup_keys[0]
    db_path = resolve_payload_sqlite_db_path(normalized_filepath)
    if not _ensure_json_payload_sqlite_cache(db_path, logger):
        return False, {}

    query_params = (
        *lookup_keys,
        int(signature[0]),
        int(signature[1]),
        *lookup_keys,
    )

    def _query_row() -> tuple[object, ...] | None:
        with connect_sqlite(
            db_path,
            timeout_seconds=30,
            pragmas=_PAYLOAD_SQLITE_SESSION_PRAGMAS,
            read_only=True,
        ) as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"""
                SELECT payload_json
                FROM json_file_payload_cache
                WHERE filepath IN ({lookup_placeholders})
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
            max_retries=_PAYLOAD_SQLITE_RETRY_ATTEMPTS,
            retry_delay_seconds=_PAYLOAD_SQLITE_RETRY_DELAY_SECONDS,
        )
    except Exception as error:
        if _is_missing_table_error(error, table_name="json_file_payload_cache") and _recover_json_payload_sqlite_schema(
            db_path,
            logger,
        ):
            try:
                row = run_sqlite_with_retry(
                    _query_row,
                    max_retries=_PAYLOAD_SQLITE_RETRY_ATTEMPTS,
                    retry_delay_seconds=_PAYLOAD_SQLITE_RETRY_DELAY_SECONDS,
                )
            except Exception as retry_error:
                logger.debug("Failed to load JSON payload SQLite cache after schema recovery (%s): %s", filepath, retry_error)
                return False, {}
        else:
            logger.debug("Failed to load JSON payload SQLite cache (%s): %s", filepath, error)
            return False, {}

    try:
        if not row:
            return False, {}
        payload = json.loads(row[0])
        if isinstance(payload, dict):
            return True, payload

        logger.debug(
            "JSON SQLite cache payload type mismatch for %s: %s",
            filepath,
            type(payload).__name__,
        )
        return False, {}
    except Exception as error:
        logger.debug("Failed to load JSON payload SQLite cache (%s): %s", filepath, error)
        return False, {}


def save_json_payload_to_sqlite(
    *,
    filepath: str,
    signature: tuple[int, int],
    payload: dict[str, Any],
    max_rows: int = DEFAULT_JSON_PAYLOAD_SQLITE_MAX_ROWS,
    logger: logging.Logger | None = None,
) -> None:
    logger = logger or _LOGGER
    normalized_filepath = _normalize_payload_filepath(filepath)
    db_path = resolve_payload_sqlite_db_path(normalized_filepath)
    if not _ensure_json_payload_sqlite_cache(db_path, logger):
        return

    try:
        serialized = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    except Exception as error:
        logger.debug(f"Failed to serialize JSON payload cache ({filepath}): {error}")
        return

    normalized_max_rows = max(1, int(max_rows))
    should_prune_for_new_key = _mark_json_payload_sqlite_snapshot_key_seen(
        db_path=db_path,
        snapshot_key=normalized_filepath,
    )
    should_force_prune = _should_force_json_payload_sqlite_prune()
    should_prune_after_upsert = should_prune_for_new_key or should_force_prune
    def _upsert_json_payload() -> None:
        now_iso = datetime.now().isoformat()
        with connect_sqlite(
            db_path,
            timeout_seconds=30,
            pragmas=_PAYLOAD_SQLITE_SESSION_PRAGMAS,
        ) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO json_file_payload_cache (
                    filepath,
                    mtime_ns,
                    size,
                    payload_json,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(filepath) DO UPDATE SET
                    mtime_ns = excluded.mtime_ns,
                    size = excluded.size,
                    payload_json = excluded.payload_json,
                    updated_at = excluded.updated_at
                """,
                (
                    normalized_filepath,
                    int(signature[0]),
                    int(signature[1]),
                    serialized,
                    now_iso,
                ),
            )
            if should_prune_after_upsert:
                _prune_payload_cache_rows_if_needed(
                    cursor,
                    table_name="json_file_payload_cache",
                    max_rows=normalized_max_rows,
                )
            conn.commit()

    try:
        run_sqlite_with_retry(
            _upsert_json_payload,
            max_retries=_PAYLOAD_SQLITE_RETRY_ATTEMPTS,
            retry_delay_seconds=_PAYLOAD_SQLITE_RETRY_DELAY_SECONDS,
        )
    except Exception as error:
        if _is_missing_table_error(error, table_name="json_file_payload_cache") and _recover_json_payload_sqlite_schema(
            db_path,
            logger,
        ):
            try:
                run_sqlite_with_retry(
                    _upsert_json_payload,
                    max_retries=_PAYLOAD_SQLITE_RETRY_ATTEMPTS,
                    retry_delay_seconds=_PAYLOAD_SQLITE_RETRY_DELAY_SECONDS,
                )
            except Exception as retry_error:
                logger.debug(
                    "Failed to save JSON payload SQLite cache after schema recovery (%s): %s",
                    filepath,
                    retry_error,
                )
        else:
            logger.debug(f"Failed to save JSON payload SQLite cache ({filepath}): {error}")


def delete_json_payload_from_sqlite(filepath: str, logger: logging.Logger | None = None) -> None:
    logger = logger or _LOGGER
    lookup_keys = _payload_filepath_lookup_keys(filepath)
    lookup_placeholders = build_sqlite_in_placeholders(lookup_keys)
    normalized_filepath = lookup_keys[0]
    db_path = resolve_payload_sqlite_db_path(normalized_filepath)
    if not _ensure_json_payload_sqlite_cache(db_path, logger):
        return
    def _delete_payload() -> None:
        with connect_sqlite(
            db_path,
            timeout_seconds=10,
            pragmas=_PAYLOAD_SQLITE_SESSION_PRAGMAS,
        ) as conn:
            conn.execute(
                f"""
                DELETE FROM json_file_payload_cache
                WHERE filepath IN ({lookup_placeholders})
                """,
                lookup_keys,
            )
            conn.commit()

    try:
        run_sqlite_with_retry(
            _delete_payload,
            max_retries=_PAYLOAD_SQLITE_RETRY_ATTEMPTS,
            retry_delay_seconds=_PAYLOAD_SQLITE_RETRY_DELAY_SECONDS,
        )
    except Exception as error:
        if _is_missing_table_error(error, table_name="json_file_payload_cache") and _recover_json_payload_sqlite_schema(
            db_path,
            logger,
        ):
            try:
                run_sqlite_with_retry(
                    _delete_payload,
                    max_retries=_PAYLOAD_SQLITE_RETRY_ATTEMPTS,
                    retry_delay_seconds=_PAYLOAD_SQLITE_RETRY_DELAY_SECONDS,
                )
            except Exception as retry_error:
                logger.debug(
                    "Failed to delete JSON payload SQLite cache after schema recovery (%s): %s",
                    filepath,
                    retry_error,
                )
        else:
            logger.debug(f"Failed to delete JSON payload SQLite cache ({filepath}): {error}")


def serialize_usecols_signature(usecols: tuple[str, ...] | None) -> str:
    if usecols is None:
        return "[]"
    return json.dumps([str(column) for column in usecols], ensure_ascii=False, separators=(",", ":"))


def _project_existing_usecols_columns(
    frame: pd.DataFrame,
    usecols: tuple[str, ...] | None,
) -> pd.DataFrame | None:
    """
    usecols 서명이 있는 CSV payload를 로드할 때 요청 컬럼만 유지한다.

    과거 fallback 버전이 전체 payload를 저장했어도, 로드시 투영해 메모리/캐시 비용을 줄인다.
    요청 컬럼이 하나도 없으면 None을 반환해 호출부가 파일 원본 fallback을 수행하도록 한다.
    """
    if usecols is None:
        return frame

    requested_columns = [str(column) for column in usecols]
    existing_columns = [column for column in requested_columns if column in frame.columns]
    if not existing_columns:
        return None
    return frame.loc[:, existing_columns]


def _ensure_csv_payload_sqlite_cache(db_path: str, logger: logging.Logger) -> bool:
    db_key = normalize_sqlite_db_key(db_path)
    with CSV_PAYLOAD_SQLITE_READY_CONDITION:
        if db_key in CSV_PAYLOAD_SQLITE_READY:
            if sqlite_db_path_exists(db_path):
                return True
            CSV_PAYLOAD_SQLITE_READY.discard(db_key)

        while db_key in CSV_PAYLOAD_SQLITE_IN_PROGRESS:
            CSV_PAYLOAD_SQLITE_READY_CONDITION.wait()
            if db_key in CSV_PAYLOAD_SQLITE_READY:
                if sqlite_db_path_exists(db_path):
                    return True
                CSV_PAYLOAD_SQLITE_READY.discard(db_key)

        CSV_PAYLOAD_SQLITE_IN_PROGRESS.add(db_key)

    def _initialize_schema() -> None:
        with connect_sqlite(
            db_path,
            timeout_seconds=30,
            pragmas=_PAYLOAD_SQLITE_INIT_PRAGMAS,
        ) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS csv_file_payload_cache (
                    filepath TEXT NOT NULL,
                    usecols_signature TEXT NOT NULL,
                    mtime_ns INTEGER NOT NULL,
                    size INTEGER NOT NULL,
                    payload_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY(filepath, usecols_signature)
                )
                """
            )
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_csv_file_payload_cache_updated_at
                ON csv_file_payload_cache(updated_at DESC)
                """
            )
            conn.commit()

    initialization_succeeded = False
    try:
        run_sqlite_with_retry(
            _initialize_schema,
            max_retries=_PAYLOAD_SQLITE_RETRY_ATTEMPTS,
            retry_delay_seconds=_PAYLOAD_SQLITE_RETRY_DELAY_SECONDS,
        )
        initialization_succeeded = True
        return True
    except Exception as error:
        logger.debug(f"Failed to initialize CSV payload SQLite cache: {error}")
        return False
    finally:
        with CSV_PAYLOAD_SQLITE_READY_CONDITION:
            CSV_PAYLOAD_SQLITE_IN_PROGRESS.discard(db_key)
            if initialization_succeeded:
                add_bounded_ready_key(
                    CSV_PAYLOAD_SQLITE_READY,
                    db_key,
                    max_entries=CSV_PAYLOAD_SQLITE_READY_MAX_ENTRIES,
                )
            else:
                CSV_PAYLOAD_SQLITE_READY.discard(db_key)
            CSV_PAYLOAD_SQLITE_READY_CONDITION.notify_all()


def _recover_csv_payload_sqlite_schema(db_path: str, logger: logging.Logger) -> bool:
    _invalidate_csv_payload_sqlite_ready(db_path)
    return _ensure_csv_payload_sqlite_cache(db_path, logger)


def _prune_payload_cache_rows_if_needed(
    cursor: sqlite3.Cursor,
    *,
    table_name: str,
    max_rows: int,
) -> None:
    normalized_max_rows = max(1, int(max_rows))
    if table_name not in {"json_file_payload_cache", "csv_file_payload_cache"}:
        raise ValueError(f"Unsupported table for payload prune: {table_name}")
    prune_rows_by_updated_at_if_needed(
        cursor,
        table_name=table_name,
        max_rows=normalized_max_rows,
    )


def load_csv_payload_from_sqlite(
    *,
    filepath: str,
    signature: tuple[int, int],
    usecols: tuple[str, ...] | None,
    logger: logging.Logger | None = None,
) -> pd.DataFrame | None:
    logger = logger or _LOGGER
    lookup_keys = _payload_filepath_lookup_keys(filepath)
    lookup_placeholders = build_sqlite_in_placeholders(lookup_keys)
    order_case_sql = build_sqlite_order_case_sql(
        column_name="filepath",
        lookup_keys=lookup_keys,
    )
    normalized_filepath = lookup_keys[0]
    db_path = resolve_payload_sqlite_db_path(normalized_filepath)
    if not _ensure_csv_payload_sqlite_cache(db_path, logger):
        return None

    usecols_signature = serialize_usecols_signature(usecols)
    query_params = (
        *lookup_keys,
        usecols_signature,
        int(signature[0]),
        int(signature[1]),
        *lookup_keys,
    )
    def _query_row() -> tuple[object, ...] | None:
        with connect_sqlite(
            db_path,
            timeout_seconds=30,
            pragmas=_PAYLOAD_SQLITE_SESSION_PRAGMAS,
            read_only=True,
        ) as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"""
                SELECT payload_json
                FROM csv_file_payload_cache
                WHERE filepath IN ({lookup_placeholders})
                  AND usecols_signature = ?
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
            max_retries=_PAYLOAD_SQLITE_RETRY_ATTEMPTS,
            retry_delay_seconds=_PAYLOAD_SQLITE_RETRY_DELAY_SECONDS,
        )
    except Exception as error:
        if _is_missing_table_error(error, table_name="csv_file_payload_cache") and _recover_csv_payload_sqlite_schema(
            db_path,
            logger,
        ):
            try:
                row = run_sqlite_with_retry(
                    _query_row,
                    max_retries=_PAYLOAD_SQLITE_RETRY_ATTEMPTS,
                    retry_delay_seconds=_PAYLOAD_SQLITE_RETRY_DELAY_SECONDS,
                )
            except Exception as retry_error:
                logger.debug("Failed to load CSV payload SQLite cache after schema recovery (%s): %s", filepath, retry_error)
                return None
        else:
            logger.debug(f"Failed to load CSV payload SQLite cache ({filepath}): {error}")
            return None

    try:
        if not row:
            return None
        payload_json = row[0]
        if not isinstance(payload_json, str) or not payload_json:
            return None
        loaded = pd.read_json(StringIO(payload_json), orient="split")
        if isinstance(loaded, pd.DataFrame):
            return _project_existing_usecols_columns(loaded, usecols)
        return None
    except Exception as error:
        logger.debug(f"Failed to load CSV payload SQLite cache ({filepath}): {error}")
        return None


def save_csv_payload_to_sqlite(
    *,
    filepath: str,
    signature: tuple[int, int],
    usecols: tuple[str, ...] | None,
    payload: pd.DataFrame,
    max_rows: int = DEFAULT_CSV_PAYLOAD_SQLITE_MAX_ROWS,
    logger: logging.Logger | None = None,
) -> None:
    logger = logger or _LOGGER
    normalized_filepath = _normalize_payload_filepath(filepath)
    db_path = resolve_payload_sqlite_db_path(normalized_filepath)
    if not _ensure_csv_payload_sqlite_cache(db_path, logger):
        return

    payload_to_store = _project_existing_usecols_columns(payload, usecols)
    if payload_to_store is None:
        logger.debug(
            "Skip saving CSV payload SQLite cache because requested usecols are all missing (%s, usecols=%s)",
            filepath,
            usecols,
        )
        return

    try:
        serialized = payload_to_store.to_json(orient="split", force_ascii=False, date_format="iso")
    except Exception as error:
        logger.debug(f"Failed to serialize CSV payload cache ({filepath}): {error}")
        return

    usecols_signature = serialize_usecols_signature(usecols)
    normalized_max_rows = max(1, int(max_rows))
    snapshot_key = f"{normalized_filepath}::{usecols_signature}"
    should_prune_for_new_key = _mark_csv_payload_sqlite_snapshot_key_seen(
        db_path=db_path,
        snapshot_key=snapshot_key,
    )
    should_force_prune = _should_force_csv_payload_sqlite_prune()
    should_prune_after_upsert = should_prune_for_new_key or should_force_prune
    def _upsert_csv_payload() -> None:
        now_iso = datetime.now().isoformat()
        with connect_sqlite(
            db_path,
            timeout_seconds=30,
            pragmas=_PAYLOAD_SQLITE_SESSION_PRAGMAS,
        ) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO csv_file_payload_cache (
                    filepath,
                    usecols_signature,
                    mtime_ns,
                    size,
                    payload_json,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(filepath, usecols_signature) DO UPDATE SET
                    mtime_ns = excluded.mtime_ns,
                    size = excluded.size,
                    payload_json = excluded.payload_json,
                    updated_at = excluded.updated_at
                """,
                (
                    normalized_filepath,
                    usecols_signature,
                    int(signature[0]),
                    int(signature[1]),
                    serialized,
                    now_iso,
                ),
            )
            if should_prune_after_upsert:
                _prune_payload_cache_rows_if_needed(
                    cursor,
                    table_name="csv_file_payload_cache",
                    max_rows=normalized_max_rows,
                )
            conn.commit()

    try:
        run_sqlite_with_retry(
            _upsert_csv_payload,
            max_retries=_PAYLOAD_SQLITE_RETRY_ATTEMPTS,
            retry_delay_seconds=_PAYLOAD_SQLITE_RETRY_DELAY_SECONDS,
        )
    except Exception as error:
        if _is_missing_table_error(error, table_name="csv_file_payload_cache") and _recover_csv_payload_sqlite_schema(
            db_path,
            logger,
        ):
            try:
                run_sqlite_with_retry(
                    _upsert_csv_payload,
                    max_retries=_PAYLOAD_SQLITE_RETRY_ATTEMPTS,
                    retry_delay_seconds=_PAYLOAD_SQLITE_RETRY_DELAY_SECONDS,
                )
            except Exception as retry_error:
                logger.debug(
                    "Failed to save CSV payload SQLite cache after schema recovery (%s): %s",
                    filepath,
                    retry_error,
                )
        else:
            logger.debug(f"Failed to save CSV payload SQLite cache ({filepath}): {error}")


def delete_csv_payload_from_sqlite(filepath: str, logger: logging.Logger | None = None) -> None:
    logger = logger or _LOGGER
    lookup_keys = _payload_filepath_lookup_keys(filepath)
    lookup_placeholders = build_sqlite_in_placeholders(lookup_keys)
    normalized_filepath = lookup_keys[0]
    db_path = resolve_payload_sqlite_db_path(normalized_filepath)
    if not _ensure_csv_payload_sqlite_cache(db_path, logger):
        return
    def _delete_payload() -> None:
        with connect_sqlite(
            db_path,
            timeout_seconds=10,
            pragmas=_PAYLOAD_SQLITE_SESSION_PRAGMAS,
        ) as conn:
            conn.execute(
                f"""
                DELETE FROM csv_file_payload_cache
                WHERE filepath IN ({lookup_placeholders})
                """,
                lookup_keys,
            )
            conn.commit()

    try:
        run_sqlite_with_retry(
            _delete_payload,
            max_retries=_PAYLOAD_SQLITE_RETRY_ATTEMPTS,
            retry_delay_seconds=_PAYLOAD_SQLITE_RETRY_DELAY_SECONDS,
        )
    except Exception as error:
        if _is_missing_table_error(error, table_name="csv_file_payload_cache") and _recover_csv_payload_sqlite_schema(
            db_path,
            logger,
        ):
            try:
                run_sqlite_with_retry(
                    _delete_payload,
                    max_retries=_PAYLOAD_SQLITE_RETRY_ATTEMPTS,
                    retry_delay_seconds=_PAYLOAD_SQLITE_RETRY_DELAY_SECONDS,
                )
            except Exception as retry_error:
                logger.debug(
                    "Failed to delete CSV payload SQLite cache after schema recovery (%s): %s",
                    filepath,
                    retry_error,
                )
        else:
            logger.debug(f"Failed to delete CSV payload SQLite cache ({filepath}): {error}")
