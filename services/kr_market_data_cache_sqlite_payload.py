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
from datetime import datetime
from io import StringIO
from typing import Any

import pandas as pd

from services.sqlite_utils import (
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
_PAYLOAD_SQLITE_SESSION_PRAGMAS = build_sqlite_pragmas(busy_timeout_ms=30_000)
_PAYLOAD_SQLITE_RETRY_ATTEMPTS = 2
_PAYLOAD_SQLITE_RETRY_DELAY_SECONDS = 0.03

JSON_PAYLOAD_SQLITE_READY: set[str] = set()
JSON_PAYLOAD_SQLITE_READY_LOCK = threading.Lock()
JSON_PAYLOAD_SQLITE_READY_CONDITION = threading.Condition(JSON_PAYLOAD_SQLITE_READY_LOCK)
JSON_PAYLOAD_SQLITE_IN_PROGRESS: set[str] = set()
DEFAULT_JSON_PAYLOAD_SQLITE_MAX_ROWS = 256
CSV_PAYLOAD_SQLITE_READY: set[str] = set()
CSV_PAYLOAD_SQLITE_READY_LOCK = threading.Lock()
CSV_PAYLOAD_SQLITE_READY_CONDITION = threading.Condition(CSV_PAYLOAD_SQLITE_READY_LOCK)
CSV_PAYLOAD_SQLITE_IN_PROGRESS: set[str] = set()
DEFAULT_CSV_PAYLOAD_SQLITE_MAX_ROWS = 256


def resolve_payload_sqlite_db_path(filepath: str) -> str:
    return os.path.join(os.path.dirname(filepath), "runtime_cache.db")


def _is_missing_table_error(error: Exception, *, table_name: str) -> bool:
    return is_sqlite_missing_table_error(error, table_names=table_name)


def _invalidate_json_payload_sqlite_ready(db_path: str) -> None:
    db_key = normalize_sqlite_db_key(db_path)
    with JSON_PAYLOAD_SQLITE_READY_LOCK:
        JSON_PAYLOAD_SQLITE_READY.discard(db_key)


def _invalidate_csv_payload_sqlite_ready(db_path: str) -> None:
    db_key = normalize_sqlite_db_key(db_path)
    with CSV_PAYLOAD_SQLITE_READY_LOCK:
        CSV_PAYLOAD_SQLITE_READY.discard(db_key)


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
                JSON_PAYLOAD_SQLITE_READY.add(db_key)
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
    db_path = resolve_payload_sqlite_db_path(filepath)
    if not _ensure_json_payload_sqlite_cache(db_path, logger):
        return False, {}

    def _query_row() -> tuple[object, ...] | None:
        with connect_sqlite(
            db_path,
            timeout_seconds=30,
            pragmas=_PAYLOAD_SQLITE_SESSION_PRAGMAS,
        ) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT payload_json
                FROM json_file_payload_cache
                WHERE filepath = ?
                  AND mtime_ns = ?
                  AND size = ?
                LIMIT 1
                """,
                (filepath, int(signature[0]), int(signature[1])),
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
    db_path = resolve_payload_sqlite_db_path(filepath)
    if not _ensure_json_payload_sqlite_cache(db_path, logger):
        return

    try:
        serialized = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    except Exception as error:
        logger.debug(f"Failed to serialize JSON payload cache ({filepath}): {error}")
        return

    normalized_max_rows = max(1, int(max_rows))
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
                    filepath,
                    int(signature[0]),
                    int(signature[1]),
                    serialized,
                    now_iso,
                ),
            )
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
    db_path = resolve_payload_sqlite_db_path(filepath)
    if not _ensure_json_payload_sqlite_cache(db_path, logger):
        return
    def _delete_payload() -> None:
        with connect_sqlite(
            db_path,
            timeout_seconds=10,
            pragmas=_PAYLOAD_SQLITE_SESSION_PRAGMAS,
        ) as conn:
            conn.execute(
                """
                DELETE FROM json_file_payload_cache
                WHERE filepath = ?
                """,
                (filepath,),
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
                CSV_PAYLOAD_SQLITE_READY.add(db_key)
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
    db_path = resolve_payload_sqlite_db_path(filepath)
    if not _ensure_csv_payload_sqlite_cache(db_path, logger):
        return None

    usecols_signature = serialize_usecols_signature(usecols)
    def _query_row() -> tuple[object, ...] | None:
        with connect_sqlite(
            db_path,
            timeout_seconds=30,
            pragmas=_PAYLOAD_SQLITE_SESSION_PRAGMAS,
        ) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT payload_json
                FROM csv_file_payload_cache
                WHERE filepath = ?
                  AND usecols_signature = ?
                  AND mtime_ns = ?
                  AND size = ?
                LIMIT 1
                """,
                (filepath, usecols_signature, int(signature[0]), int(signature[1])),
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
            return loaded
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
    db_path = resolve_payload_sqlite_db_path(filepath)
    if not _ensure_csv_payload_sqlite_cache(db_path, logger):
        return

    try:
        serialized = payload.to_json(orient="split", force_ascii=False, date_format="iso")
    except Exception as error:
        logger.debug(f"Failed to serialize CSV payload cache ({filepath}): {error}")
        return

    usecols_signature = serialize_usecols_signature(usecols)
    normalized_max_rows = max(1, int(max_rows))
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
                    filepath,
                    usecols_signature,
                    int(signature[0]),
                    int(signature[1]),
                    serialized,
                    now_iso,
                ),
            )
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
    db_path = resolve_payload_sqlite_db_path(filepath)
    if not _ensure_csv_payload_sqlite_cache(db_path, logger):
        return
    def _delete_payload() -> None:
        with connect_sqlite(
            db_path,
            timeout_seconds=10,
            pragmas=_PAYLOAD_SQLITE_SESSION_PRAGMAS,
        ) as conn:
            conn.execute(
                """
                DELETE FROM csv_file_payload_cache
                WHERE filepath = ?
                """,
                (filepath,),
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
