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
import threading
from datetime import datetime
from typing import Any

from services.sqlite_utils import connect_sqlite


_VCP_SIGNALS_CACHE_LOCK = threading.Lock()
_VCP_SIGNALS_MEMORY_CACHE: dict[str, tuple[tuple[Any, ...], list[dict[str, Any]]]] = {}
_VCP_SIGNALS_MEMORY_MAX_ENTRIES = 16
_VCP_SIGNALS_SQLITE_MAX_ROWS = 64
_VCP_SIGNALS_SQLITE_READY: set[str] = set()


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


def _ensure_sqlite_cache(db_path: str, logger: Any) -> bool:
    if db_path in _VCP_SIGNALS_SQLITE_READY:
        return True
    try:
        with connect_sqlite(
            db_path,
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
        _VCP_SIGNALS_SQLITE_READY.add(db_path)
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

    try:
        with connect_sqlite(db_path, timeout_seconds=30) as conn:
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
            row = cursor.fetchone()
            if not row:
                return None
            payload = json.loads(row[0])
            if not isinstance(payload, list):
                return None
    except Exception as error:
        if logger:
            logger.debug(f"Failed to load cached vcp signals payload: {error}")
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

    try:
        with connect_sqlite(db_path, timeout_seconds=30) as conn:
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
            cursor.execute(
                """
                DELETE FROM vcp_signals_payload_cache
                WHERE signature_hash NOT IN (
                    SELECT signature_hash
                    FROM vcp_signals_payload_cache
                    ORDER BY updated_at DESC
                    LIMIT ?
                )
                """,
                (_VCP_SIGNALS_SQLITE_MAX_ROWS,),
            )
            conn.commit()
    except Exception as error:
        if logger:
            logger.debug(f"Failed to save cached vcp signals payload: {error}")


__all__ = [
    "build_vcp_signals_cache_signature",
    "get_cached_vcp_signals",
    "save_cached_vcp_signals",
]
