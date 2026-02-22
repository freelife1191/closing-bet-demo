#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KR Market VCP signals payload cache (memory + SQLite)
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import sqlite3
import threading
from datetime import datetime
from typing import Any

from services.sqlite_utils import (
    build_sqlite_pragmas,
    connect_sqlite,
    is_sqlite_missing_table_error,
    normalize_sqlite_db_key,
    prune_rows_by_updated_at_if_needed,
    run_sqlite_with_retry,
    sqlite_db_path_exists,
)


_VCP_SIGNALS_CACHE_LOCK = threading.Lock()
_VCP_SIGNALS_MEMORY_CACHE: dict[str, tuple[tuple[Any, ...], list[dict[str, Any]]]] = {}
_VCP_SIGNALS_MEMORY_MAX_ENTRIES = 16
_VCP_SIGNALS_SQLITE_MAX_ROWS = 64
_VCP_SIGNALS_SQLITE_READY: set[str] = set()
_VCP_SIGNALS_SQLITE_READY_LOCK = threading.Lock()
_VCP_SIGNALS_SQLITE_INIT_PRAGMAS = build_sqlite_pragmas(busy_timeout_ms=30_000)
_VCP_SIGNALS_SQLITE_SESSION_PRAGMAS = build_sqlite_pragmas(busy_timeout_ms=30_000)
_VCP_SIGNALS_SQLITE_RETRY_ATTEMPTS = 2
_VCP_SIGNALS_SQLITE_RETRY_DELAY_SECONDS = 0.03


def _file_signature(path: str) -> tuple[int, int] | None:
    try:
        stat = os.stat(path)
    except OSError:
        return None
    return int(stat.st_mtime_ns), int(stat.st_size)


def _resolve_cache_db_path(data_dir: str) -> str:
    return os.path.join(data_dir, "runtime_cache.db")


def _signature_digest(signature: tuple[Any, ...]) -> tuple[str, str]:
    payload = json.dumps(list(signature), ensure_ascii=False, separators=(",", ":"))
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return digest, payload


def _invalidate_vcp_signals_sqlite_ready(db_path: str) -> None:
    db_key = normalize_sqlite_db_key(db_path)
    with _VCP_SIGNALS_SQLITE_READY_LOCK:
        _VCP_SIGNALS_SQLITE_READY.discard(db_key)


def _is_missing_table_error(error: Exception) -> bool:
    return is_sqlite_missing_table_error(error, table_names="vcp_signals_payload_cache")


def _recover_vcp_signals_sqlite_schema(db_path: str, logger: Any) -> bool:
    _invalidate_vcp_signals_sqlite_ready(db_path)
    return _ensure_sqlite_cache(db_path, logger)


def _ensure_sqlite_cache(db_path: str, logger: Any) -> bool:
    db_key = normalize_sqlite_db_key(db_path)
    with _VCP_SIGNALS_SQLITE_READY_LOCK:
        if db_key in _VCP_SIGNALS_SQLITE_READY:
            if sqlite_db_path_exists(db_path):
                return True
            _VCP_SIGNALS_SQLITE_READY.discard(db_key)

        def _initialize_schema() -> None:
            with connect_sqlite(
                db_path,
                timeout_seconds=30,
                pragmas=_VCP_SIGNALS_SQLITE_INIT_PRAGMAS,
            ) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS vcp_signals_payload_cache (
                        signature_hash TEXT PRIMARY KEY,
                        signature_json TEXT NOT NULL,
                        payload_json TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    )
                    """
                )
                cursor.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_vcp_signals_payload_cache_updated_at
                    ON vcp_signals_payload_cache(updated_at DESC)
                    """
                )
                conn.commit()
        try:
            run_sqlite_with_retry(
                _initialize_schema,
                max_retries=_VCP_SIGNALS_SQLITE_RETRY_ATTEMPTS,
                retry_delay_seconds=_VCP_SIGNALS_SQLITE_RETRY_DELAY_SECONDS,
            )
            _VCP_SIGNALS_SQLITE_READY.add(db_key)
            return True
        except Exception as error:
            if logger:
                logger.debug(f"Failed to initialize vcp signals sqlite cache: {error}")
            return False


def build_vcp_signals_cache_signature(
    *,
    data_dir: str,
    req_date: str | None,
    today: str,
) -> tuple[Any, ...] | None:
    signals_file = os.path.join(data_dir, "signals_log.csv")
    signature = _file_signature(signals_file)
    if signature is None:
        return None
    return ("vcp-signals", req_date or "__latest__", today, signature[0], signature[1])


def get_cached_vcp_signals(
    *,
    signature: tuple[Any, ...] | None,
    data_dir: str,
    logger: Any,
) -> list[dict[str, Any]] | None:
    if signature is None:
        return None

    digest, signature_json = _signature_digest(signature)
    with _VCP_SIGNALS_CACHE_LOCK:
        cached = _VCP_SIGNALS_MEMORY_CACHE.get(digest)
        if cached and cached[0] == signature:
            return copy.deepcopy(cached[1])

    db_path = _resolve_cache_db_path(data_dir)
    if not _ensure_sqlite_cache(db_path, logger):
        return None

    def _query_payload() -> tuple[Any, ...] | None:
        with connect_sqlite(
            db_path,
            timeout_seconds=30,
            pragmas=_VCP_SIGNALS_SQLITE_SESSION_PRAGMAS,
        ) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT payload_json
                FROM vcp_signals_payload_cache
                WHERE signature_hash = ?
                  AND signature_json = ?
                LIMIT 1
                """,
                (digest, signature_json),
            )
            return cursor.fetchone()

    try:
        row = run_sqlite_with_retry(
            _query_payload,
            max_retries=_VCP_SIGNALS_SQLITE_RETRY_ATTEMPTS,
            retry_delay_seconds=_VCP_SIGNALS_SQLITE_RETRY_DELAY_SECONDS,
        )
    except Exception as error:
        if _is_missing_table_error(error) and _recover_vcp_signals_sqlite_schema(db_path, logger):
            try:
                row = run_sqlite_with_retry(
                    _query_payload,
                    max_retries=_VCP_SIGNALS_SQLITE_RETRY_ATTEMPTS,
                    retry_delay_seconds=_VCP_SIGNALS_SQLITE_RETRY_DELAY_SECONDS,
                )
            except Exception as retry_error:
                if logger:
                    logger.debug("Failed to load cached vcp signals payload after schema recovery: %s", retry_error)
                return None
        else:
            if logger:
                logger.debug("Failed to load cached vcp signals payload: %s", error)
            return None

    try:
        if not row:
            return None
        payload = json.loads(row[0])
        if not isinstance(payload, list):
            return None
    except Exception as error:
        if logger:
            logger.debug("Failed to load cached vcp signals payload: %s", error)
        return None

    with _VCP_SIGNALS_CACHE_LOCK:
        _VCP_SIGNALS_MEMORY_CACHE[digest] = (signature, copy.deepcopy(payload))
        while len(_VCP_SIGNALS_MEMORY_CACHE) > _VCP_SIGNALS_MEMORY_MAX_ENTRIES:
            _VCP_SIGNALS_MEMORY_CACHE.pop(next(iter(_VCP_SIGNALS_MEMORY_CACHE)))
    return copy.deepcopy(payload)


def save_cached_vcp_signals(
    *,
    signature: tuple[Any, ...] | None,
    payload: list[dict[str, Any]],
    data_dir: str,
    logger: Any,
) -> None:
    if signature is None:
        return
    if not isinstance(payload, list):
        return

    digest, signature_json = _signature_digest(signature)
    with _VCP_SIGNALS_CACHE_LOCK:
        _VCP_SIGNALS_MEMORY_CACHE[digest] = (signature, copy.deepcopy(payload))
        while len(_VCP_SIGNALS_MEMORY_CACHE) > _VCP_SIGNALS_MEMORY_MAX_ENTRIES:
            _VCP_SIGNALS_MEMORY_CACHE.pop(next(iter(_VCP_SIGNALS_MEMORY_CACHE)))

    db_path = _resolve_cache_db_path(data_dir)
    if not _ensure_sqlite_cache(db_path, logger):
        return

    try:
        payload_json = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    except Exception as error:
        if logger:
            logger.debug(f"Failed to serialize vcp signals payload: {error}")
        return

    normalized_max_rows = max(1, int(_VCP_SIGNALS_SQLITE_MAX_ROWS))

    def _prune_rows_if_needed(cursor: sqlite3.Cursor) -> None:
        prune_rows_by_updated_at_if_needed(
            cursor,
            table_name="vcp_signals_payload_cache",
            max_rows=normalized_max_rows,
        )

    def _upsert_payload() -> None:
        with connect_sqlite(
            db_path,
            timeout_seconds=30,
            pragmas=_VCP_SIGNALS_SQLITE_SESSION_PRAGMAS,
        ) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO vcp_signals_payload_cache (
                    signature_hash,
                    signature_json,
                    payload_json,
                    updated_at
                ) VALUES (?, ?, ?, ?)
                ON CONFLICT(signature_hash) DO UPDATE SET
                    signature_json = excluded.signature_json,
                    payload_json = excluded.payload_json,
                    updated_at = excluded.updated_at
                """,
                (digest, signature_json, payload_json, datetime.now().isoformat()),
            )
            _prune_rows_if_needed(cursor)
            conn.commit()

    try:
        run_sqlite_with_retry(
            _upsert_payload,
            max_retries=_VCP_SIGNALS_SQLITE_RETRY_ATTEMPTS,
            retry_delay_seconds=_VCP_SIGNALS_SQLITE_RETRY_DELAY_SECONDS,
        )
    except Exception as error:
        if _is_missing_table_error(error) and _recover_vcp_signals_sqlite_schema(db_path, logger):
            try:
                run_sqlite_with_retry(
                    _upsert_payload,
                    max_retries=_VCP_SIGNALS_SQLITE_RETRY_ATTEMPTS,
                    retry_delay_seconds=_VCP_SIGNALS_SQLITE_RETRY_DELAY_SECONDS,
                )
            except Exception as retry_error:
                if logger:
                    logger.debug("Failed to save cached vcp signals payload after schema recovery: %s", retry_error)
        else:
            if logger:
                logger.debug("Failed to save cached vcp signals payload: %s", error)


__all__ = [
    "build_vcp_signals_cache_signature",
    "get_cached_vcp_signals",
    "save_cached_vcp_signals",
]
