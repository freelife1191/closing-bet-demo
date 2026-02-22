#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KR Market Data Cache - SQLite payload snapshot helpers
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from io import StringIO
from typing import Any

import pandas as pd

from services.sqlite_utils import connect_sqlite


_LOGGER = logging.getLogger(__name__)
_PAYLOAD_SQLITE_PRAGMAS = (
    "PRAGMA journal_mode=WAL",
    "PRAGMA synchronous=NORMAL",
    "PRAGMA temp_store=MEMORY",
    "PRAGMA busy_timeout=30000",
)

JSON_PAYLOAD_SQLITE_READY: set[str] = set()
DEFAULT_JSON_PAYLOAD_SQLITE_MAX_ROWS = 256
CSV_PAYLOAD_SQLITE_READY: set[str] = set()
DEFAULT_CSV_PAYLOAD_SQLITE_MAX_ROWS = 256


def resolve_payload_sqlite_db_path(filepath: str) -> str:
    return os.path.join(os.path.dirname(filepath), "runtime_cache.db")


def _ensure_parent_directory(path: str) -> None:
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)


def _ensure_json_payload_sqlite_cache(db_path: str, logger: logging.Logger) -> bool:
    if db_path in JSON_PAYLOAD_SQLITE_READY:
        return True
    try:
        _ensure_parent_directory(db_path)
        with connect_sqlite(
            db_path,
            timeout_seconds=30,
            pragmas=_PAYLOAD_SQLITE_PRAGMAS,
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
        JSON_PAYLOAD_SQLITE_READY.add(db_path)
        return True
    except Exception as error:
        logger.debug(f"Failed to initialize JSON payload SQLite cache: {error}")
        return False


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

    try:
        with connect_sqlite(db_path, timeout_seconds=30) as conn:
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
            row = cursor.fetchone()
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
        logger.debug(f"Failed to load JSON payload SQLite cache ({filepath}): {error}")
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
        serialized = json.dumps(payload, ensure_ascii=False)
    except Exception as error:
        logger.debug(f"Failed to serialize JSON payload cache ({filepath}): {error}")
        return

    try:
        now_iso = datetime.now().isoformat()
        with connect_sqlite(db_path, timeout_seconds=30) as conn:
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
            cursor.execute(
                """
                DELETE FROM json_file_payload_cache
                WHERE filepath NOT IN (
                    SELECT filepath
                    FROM json_file_payload_cache
                    ORDER BY updated_at DESC
                    LIMIT ?
                )
                """,
                (max_rows,),
            )
            conn.commit()
    except Exception as error:
        logger.debug(f"Failed to save JSON payload SQLite cache ({filepath}): {error}")


def delete_json_payload_from_sqlite(filepath: str, logger: logging.Logger | None = None) -> None:
    logger = logger or _LOGGER
    db_path = resolve_payload_sqlite_db_path(filepath)
    if not _ensure_json_payload_sqlite_cache(db_path, logger):
        return
    try:
        with connect_sqlite(db_path, timeout_seconds=10) as conn:
            conn.execute(
                """
                DELETE FROM json_file_payload_cache
                WHERE filepath = ?
                """,
                (filepath,),
            )
            conn.commit()
    except Exception as error:
        logger.debug(f"Failed to delete JSON payload SQLite cache ({filepath}): {error}")


def serialize_usecols_signature(usecols: tuple[str, ...] | None) -> str:
    if usecols is None:
        return "[]"
    return json.dumps([str(column) for column in usecols], ensure_ascii=False)


def _ensure_csv_payload_sqlite_cache(db_path: str, logger: logging.Logger) -> bool:
    if db_path in CSV_PAYLOAD_SQLITE_READY:
        return True
    try:
        _ensure_parent_directory(db_path)
        with connect_sqlite(
            db_path,
            timeout_seconds=30,
            pragmas=_PAYLOAD_SQLITE_PRAGMAS,
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
        CSV_PAYLOAD_SQLITE_READY.add(db_path)
        return True
    except Exception as error:
        logger.debug(f"Failed to initialize CSV payload SQLite cache: {error}")
        return False


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
    try:
        with connect_sqlite(db_path, timeout_seconds=30) as conn:
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
            row = cursor.fetchone()
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
    try:
        now_iso = datetime.now().isoformat()
        with connect_sqlite(db_path, timeout_seconds=30) as conn:
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
            cursor.execute(
                """
                DELETE FROM csv_file_payload_cache
                WHERE (filepath, usecols_signature) NOT IN (
                    SELECT filepath, usecols_signature
                    FROM csv_file_payload_cache
                    ORDER BY updated_at DESC
                    LIMIT ?
                )
                """,
                (max_rows,),
            )
            conn.commit()
    except Exception as error:
        logger.debug(f"Failed to save CSV payload SQLite cache ({filepath}): {error}")


def delete_csv_payload_from_sqlite(filepath: str, logger: logging.Logger | None = None) -> None:
    logger = logger or _LOGGER
    db_path = resolve_payload_sqlite_db_path(filepath)
    if not _ensure_csv_payload_sqlite_cache(db_path, logger):
        return
    try:
        with connect_sqlite(db_path, timeout_seconds=10) as conn:
            conn.execute(
                """
                DELETE FROM csv_file_payload_cache
                WHERE filepath = ?
                """,
                (filepath,),
            )
            conn.commit()
    except Exception as error:
        logger.debug(f"Failed to delete CSV payload SQLite cache ({filepath}): {error}")
