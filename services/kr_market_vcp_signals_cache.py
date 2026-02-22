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
from collections import OrderedDict
from datetime import datetime
from typing import Any

from services.sqlite_utils import (
    add_bounded_ready_key,
    build_sqlite_pragmas,
    connect_sqlite,
    is_sqlite_missing_table_error,
    normalize_sqlite_db_key,
    prune_rows_by_updated_at_if_needed,
    run_sqlite_with_retry,
    sqlite_db_path_exists,
)


_VCP_SIGNALS_CACHE_LOCK = threading.Lock()
_VCP_SIGNALS_MEMORY_CACHE: OrderedDict[
    str,
    tuple[tuple[Any, ...], list[dict[str, Any]]],
] = OrderedDict()
_VCP_SIGNALS_MEMORY_MAX_ENTRIES = 16
_VCP_SIGNALS_SQLITE_MAX_ROWS = 64
_VCP_SIGNALS_SQLITE_READY: set[str] = set()
_VCP_SIGNALS_SQLITE_READY_MAX_ENTRIES = 2_048
_VCP_SIGNALS_SQLITE_READY_LOCK = threading.Lock()
_VCP_SIGNALS_SQLITE_READY_CONDITION = threading.Condition(_VCP_SIGNALS_SQLITE_READY_LOCK)
_VCP_SIGNALS_SQLITE_INIT_IN_PROGRESS: set[str] = set()
_VCP_SIGNALS_SQLITE_KNOWN_HASHES: OrderedDict[tuple[str, str], None] = OrderedDict()
_VCP_SIGNALS_SQLITE_KNOWN_HASHES_LOCK = threading.Lock()
_VCP_SIGNALS_SQLITE_KNOWN_HASHES_MAX_ENTRIES = 8_192
_VCP_SIGNALS_SQLITE_PRUNE_FORCE_INTERVAL = 64
_VCP_SIGNALS_SQLITE_SAVE_COUNTER = 0
_VCP_SIGNALS_SQLITE_SAVE_COUNTER_LOCK = threading.Lock()
_VCP_SIGNALS_SQLITE_INIT_PRAGMAS = build_sqlite_pragmas(busy_timeout_ms=30_000)
_VCP_SIGNALS_SQLITE_SESSION_PRAGMAS = build_sqlite_pragmas(
    busy_timeout_ms=30_000,
    base_pragmas=("PRAGMA temp_store=MEMORY", "PRAGMA cache_size=-4000"),
)
_VCP_SIGNALS_SQLITE_RETRY_ATTEMPTS = 2
_VCP_SIGNALS_SQLITE_RETRY_DELAY_SECONDS = 0.03


def _set_vcp_signals_memory_cache_entry(
    digest: str,
    signature: tuple[Any, ...],
    payload: list[dict[str, Any]],
) -> None:
    normalized_max_entries = max(1, int(_VCP_SIGNALS_MEMORY_MAX_ENTRIES))
    with _VCP_SIGNALS_CACHE_LOCK:
        _VCP_SIGNALS_MEMORY_CACHE[digest] = (signature, copy.deepcopy(payload))
        _VCP_SIGNALS_MEMORY_CACHE.move_to_end(digest)
        while len(_VCP_SIGNALS_MEMORY_CACHE) > normalized_max_entries:
            _VCP_SIGNALS_MEMORY_CACHE.popitem(last=False)


def _get_vcp_signals_memory_cache_entry(
    digest: str,
    signature: tuple[Any, ...],
) -> list[dict[str, Any]] | None:
    with _VCP_SIGNALS_CACHE_LOCK:
        cached = _VCP_SIGNALS_MEMORY_CACHE.get(digest)
        if cached:
            if cached[0] == signature:
                _VCP_SIGNALS_MEMORY_CACHE.move_to_end(digest)
                return copy.deepcopy(cached[1])
            _VCP_SIGNALS_MEMORY_CACHE.pop(digest, None)
    return None


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
    with _VCP_SIGNALS_SQLITE_READY_CONDITION:
        _VCP_SIGNALS_SQLITE_READY.discard(db_key)
    with _VCP_SIGNALS_SQLITE_KNOWN_HASHES_LOCK:
        stale_keys = [key for key in _VCP_SIGNALS_SQLITE_KNOWN_HASHES if key[0] == db_key]
        for tracker_key in stale_keys:
            _VCP_SIGNALS_SQLITE_KNOWN_HASHES.pop(tracker_key, None)


def _is_missing_table_error(error: Exception) -> bool:
    return is_sqlite_missing_table_error(error, table_names="vcp_signals_payload_cache")


def _recover_vcp_signals_sqlite_schema(db_path: str, logger: Any) -> bool:
    _invalidate_vcp_signals_sqlite_ready(db_path)
    return _ensure_sqlite_cache(db_path, logger)


def _mark_vcp_signals_sqlite_signature_seen(*, db_path: str, signature_hash: str) -> bool:
    """
    (db_path, signature_hash) 조합을 추적한다.
    return True면 신규 key로 간주해 prune을 수행한다.
    """
    db_key = normalize_sqlite_db_key(db_path)
    tracker_key = (db_key, str(signature_hash))
    with _VCP_SIGNALS_SQLITE_KNOWN_HASHES_LOCK:
        if tracker_key in _VCP_SIGNALS_SQLITE_KNOWN_HASHES:
            _VCP_SIGNALS_SQLITE_KNOWN_HASHES.move_to_end(tracker_key)
            return False

        _VCP_SIGNALS_SQLITE_KNOWN_HASHES[tracker_key] = None
        _VCP_SIGNALS_SQLITE_KNOWN_HASHES.move_to_end(tracker_key)
        normalized_max_entries = max(1, int(_VCP_SIGNALS_SQLITE_KNOWN_HASHES_MAX_ENTRIES))
        while len(_VCP_SIGNALS_SQLITE_KNOWN_HASHES) > normalized_max_entries:
            _VCP_SIGNALS_SQLITE_KNOWN_HASHES.popitem(last=False)
        return True


def _should_force_vcp_signals_sqlite_prune() -> bool:
    global _VCP_SIGNALS_SQLITE_SAVE_COUNTER
    with _VCP_SIGNALS_SQLITE_SAVE_COUNTER_LOCK:
        _VCP_SIGNALS_SQLITE_SAVE_COUNTER += 1
        normalized_interval = max(1, int(_VCP_SIGNALS_SQLITE_PRUNE_FORCE_INTERVAL))
        return (_VCP_SIGNALS_SQLITE_SAVE_COUNTER % normalized_interval) == 0


def _ensure_sqlite_cache(db_path: str, logger: Any) -> bool:
    db_key = normalize_sqlite_db_key(db_path)
    with _VCP_SIGNALS_SQLITE_READY_CONDITION:
        if db_key in _VCP_SIGNALS_SQLITE_READY:
            if sqlite_db_path_exists(db_path):
                return True
            _VCP_SIGNALS_SQLITE_READY.discard(db_key)

        while db_key in _VCP_SIGNALS_SQLITE_INIT_IN_PROGRESS:
            _VCP_SIGNALS_SQLITE_READY_CONDITION.wait()
            if db_key in _VCP_SIGNALS_SQLITE_READY:
                if sqlite_db_path_exists(db_path):
                    return True
                _VCP_SIGNALS_SQLITE_READY.discard(db_key)

        _VCP_SIGNALS_SQLITE_INIT_IN_PROGRESS.add(db_key)

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

    initialization_succeeded = False
    try:
        run_sqlite_with_retry(
            _initialize_schema,
            max_retries=_VCP_SIGNALS_SQLITE_RETRY_ATTEMPTS,
            retry_delay_seconds=_VCP_SIGNALS_SQLITE_RETRY_DELAY_SECONDS,
        )
        initialization_succeeded = True
        return True
    except Exception as error:
        if logger:
            logger.debug(f"Failed to initialize vcp signals sqlite cache: {error}")
        return False
    finally:
        with _VCP_SIGNALS_SQLITE_READY_CONDITION:
            _VCP_SIGNALS_SQLITE_INIT_IN_PROGRESS.discard(db_key)
            if initialization_succeeded:
                add_bounded_ready_key(
                    _VCP_SIGNALS_SQLITE_READY,
                    db_key,
                    max_entries=_VCP_SIGNALS_SQLITE_READY_MAX_ENTRIES,
                )
            else:
                _VCP_SIGNALS_SQLITE_READY.discard(db_key)
            _VCP_SIGNALS_SQLITE_READY_CONDITION.notify_all()


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
    memory_cached = _get_vcp_signals_memory_cache_entry(digest, signature)
    if memory_cached is not None:
        return memory_cached

    db_path = _resolve_cache_db_path(data_dir)
    if not _ensure_sqlite_cache(db_path, logger):
        return None

    def _query_payload() -> tuple[Any, ...] | None:
        with connect_sqlite(
            db_path,
            timeout_seconds=30,
            pragmas=_VCP_SIGNALS_SQLITE_SESSION_PRAGMAS,
            read_only=True,
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

    _set_vcp_signals_memory_cache_entry(digest, signature, payload)
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
    _set_vcp_signals_memory_cache_entry(digest, signature, payload)

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
    should_prune_for_new_hash = _mark_vcp_signals_sqlite_signature_seen(
        db_path=db_path,
        signature_hash=digest,
    )
    should_force_prune = _should_force_vcp_signals_sqlite_prune()
    should_prune_after_upsert = should_prune_for_new_hash or should_force_prune

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
            if should_prune_after_upsert:
                prune_rows_by_updated_at_if_needed(
                    cursor,
                    table_name="vcp_signals_payload_cache",
                    max_rows=normalized_max_rows,
                )
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
