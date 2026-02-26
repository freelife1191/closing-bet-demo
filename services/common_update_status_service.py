#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
공통 업데이트 상태 파일/전이 관리 서비스.
"""

from __future__ import annotations

import copy
import json
import os
import sqlite3
import threading
from collections import OrderedDict
from datetime import datetime
from typing import Any, Dict

from numpy_json_encoder import NumpyEncoder
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


_UPDATE_STATUS_CACHE: OrderedDict[str, tuple[tuple[int, int], Dict[str, Any]]] = OrderedDict()
_UPDATE_STATUS_CACHE_LOCK = threading.Lock()
_UPDATE_STATUS_CACHE_MAX_ENTRIES = 2_048
_UPDATE_STATUS_DB_INIT_LOCK = threading.Lock()
_UPDATE_STATUS_DB_INIT_CONDITION = threading.Condition(_UPDATE_STATUS_DB_INIT_LOCK)
_UPDATE_STATUS_DB_INIT_IN_PROGRESS: set[str] = set()
_UPDATE_STATUS_DB_READY: set[str] = set()
_UPDATE_STATUS_DB_READY_MAX_ENTRIES = 2_048
_UPDATE_STATUS_SQLITE_KNOWN_SNAPSHOT_KEYS: OrderedDict[tuple[str, str], None] = OrderedDict()
_UPDATE_STATUS_SQLITE_KNOWN_SNAPSHOT_KEYS_LOCK = threading.Lock()
_UPDATE_STATUS_SQLITE_KNOWN_SNAPSHOT_KEYS_MAX_ENTRIES = 4_096
_UPDATE_STATUS_SQLITE_PRUNE_FORCE_INTERVAL = 64
_UPDATE_STATUS_SQLITE_SAVE_COUNTER = 0
_UPDATE_STATUS_SQLITE_SAVE_COUNTER_LOCK = threading.Lock()
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_UPDATE_STATUS_CACHE_DB_PATH = os.path.join(_BASE_DIR, "data", "runtime_cache.db")
_UPDATE_STATUS_SQLITE_TIMEOUT_SECONDS = 5
_UPDATE_STATUS_SQLITE_MAX_ROWS = 256
_UPDATE_STATUS_SQLITE_RETRY_ATTEMPTS = 2
_UPDATE_STATUS_SQLITE_RETRY_DELAY_SECONDS = 0.03
_UPDATE_STATUS_INIT_PRAGMAS = build_sqlite_pragmas(
    busy_timeout_ms=_UPDATE_STATUS_SQLITE_TIMEOUT_SECONDS * 1000,
)
_UPDATE_STATUS_SESSION_PRAGMAS = build_sqlite_pragmas(
    busy_timeout_ms=_UPDATE_STATUS_SQLITE_TIMEOUT_SECONDS * 1000,
    base_pragmas=("PRAGMA temp_store=MEMORY", "PRAGMA cache_size=-4000"),
)


def _prune_update_status_cache_locked() -> None:
    normalized_max_entries = max(1, int(_UPDATE_STATUS_CACHE_MAX_ENTRIES))
    while len(_UPDATE_STATUS_CACHE) > normalized_max_entries:
        _UPDATE_STATUS_CACHE.popitem(last=False)


def _ensure_parent_dir(path: str) -> None:
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)


def _status_file_signature(update_status_file: str) -> tuple[int, int] | None:
    try:
        stat = os.stat(update_status_file)
    except OSError:
        return None
    return int(stat.st_mtime_ns), int(stat.st_size)


def _normalize_db_key(path: str) -> str:
    return normalize_sqlite_db_key(path)


def _normalize_update_status_file_key(path: str) -> str:
    return normalize_sqlite_db_key(path)


def _update_status_file_lookup_keys(path: str) -> tuple[str, ...]:
    normalized_key = _normalize_update_status_file_key(path)
    legacy_key = str(path)
    keys: list[str] = [normalized_key]
    if legacy_key not in keys:
        keys.append(legacy_key)
    try:
        relative_key = os.path.relpath(normalized_key, os.getcwd())
        if relative_key not in keys:
            keys.append(relative_key)
    except Exception:
        pass
    return tuple(keys)


def _invalidate_update_status_sqlite_ready(db_path: str) -> None:
    db_key = _normalize_db_key(db_path)
    with _UPDATE_STATUS_DB_INIT_CONDITION:
        _UPDATE_STATUS_DB_READY.discard(db_key)


def _is_missing_table_error(error: Exception) -> bool:
    return is_sqlite_missing_table_error(error, table_names="update_status_snapshot")


def _ensure_update_status_snapshot_columns(cursor: sqlite3.Cursor, logger) -> None:
    rows = cursor.execute("PRAGMA table_info(update_status_snapshot)").fetchall()
    existing_columns = {str(row[1]) for row in rows if len(row) > 1}

    if "mtime_ns" not in existing_columns:
        try:
            cursor.execute("ALTER TABLE update_status_snapshot ADD COLUMN mtime_ns INTEGER")
        except sqlite3.OperationalError as error:
            if "duplicate column name" not in str(error).lower():
                logger.error(f"Failed to add update_status_snapshot.mtime_ns column: {error}")
                raise
    if "size_bytes" not in existing_columns:
        try:
            cursor.execute("ALTER TABLE update_status_snapshot ADD COLUMN size_bytes INTEGER")
        except sqlite3.OperationalError as error:
            if "duplicate column name" not in str(error).lower():
                logger.error(f"Failed to add update_status_snapshot.size_bytes column: {error}")
                raise


def _mark_update_status_snapshot_key_seen(*, db_path: str, file_path: str) -> bool:
    """
    (db_path, file_path) 조합의 SQLite snapshot key를 추적한다.
    return True면 신규 key로 간주해 prune을 수행한다.
    """
    db_key = _normalize_db_key(db_path)
    tracker_key = (db_key, str(file_path))
    with _UPDATE_STATUS_SQLITE_KNOWN_SNAPSHOT_KEYS_LOCK:
        if tracker_key in _UPDATE_STATUS_SQLITE_KNOWN_SNAPSHOT_KEYS:
            _UPDATE_STATUS_SQLITE_KNOWN_SNAPSHOT_KEYS.move_to_end(tracker_key)
            return False

        _UPDATE_STATUS_SQLITE_KNOWN_SNAPSHOT_KEYS[tracker_key] = None
        _UPDATE_STATUS_SQLITE_KNOWN_SNAPSHOT_KEYS.move_to_end(tracker_key)
        normalized_max_entries = max(1, int(_UPDATE_STATUS_SQLITE_KNOWN_SNAPSHOT_KEYS_MAX_ENTRIES))
        while len(_UPDATE_STATUS_SQLITE_KNOWN_SNAPSHOT_KEYS) > normalized_max_entries:
            _UPDATE_STATUS_SQLITE_KNOWN_SNAPSHOT_KEYS.popitem(last=False)
        return True


def _recover_update_status_sqlite(logger) -> bool:
    db_path = _UPDATE_STATUS_CACHE_DB_PATH
    _invalidate_update_status_sqlite_ready(db_path)
    return _ensure_update_status_sqlite(logger)


def _should_force_update_status_snapshot_prune() -> bool:
    global _UPDATE_STATUS_SQLITE_SAVE_COUNTER
    with _UPDATE_STATUS_SQLITE_SAVE_COUNTER_LOCK:
        _UPDATE_STATUS_SQLITE_SAVE_COUNTER += 1
        normalized_interval = max(1, int(_UPDATE_STATUS_SQLITE_PRUNE_FORCE_INTERVAL))
        return (_UPDATE_STATUS_SQLITE_SAVE_COUNTER % normalized_interval) == 0


def _ensure_update_status_sqlite(logger) -> bool:
    db_path = _UPDATE_STATUS_CACHE_DB_PATH
    db_key = _normalize_db_key(db_path)

    with _UPDATE_STATUS_DB_INIT_CONDITION:
        if db_key in _UPDATE_STATUS_DB_READY:
            if sqlite_db_path_exists(db_path):
                return True
            _UPDATE_STATUS_DB_READY.discard(db_key)

        while db_key in _UPDATE_STATUS_DB_INIT_IN_PROGRESS:
            _UPDATE_STATUS_DB_INIT_CONDITION.wait()
            if db_key in _UPDATE_STATUS_DB_READY:
                if sqlite_db_path_exists(db_path):
                    return True
                _UPDATE_STATUS_DB_READY.discard(db_key)

        _UPDATE_STATUS_DB_INIT_IN_PROGRESS.add(db_key)

    def _initialize_schema() -> None:
        with connect_sqlite(
            db_path,
            timeout_seconds=_UPDATE_STATUS_SQLITE_TIMEOUT_SECONDS,
            pragmas=_UPDATE_STATUS_INIT_PRAGMAS,
        ) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS update_status_snapshot (
                    file_path TEXT PRIMARY KEY,
                    payload_json TEXT NOT NULL,
                    mtime_ns INTEGER,
                    size_bytes INTEGER,
                    updated_at TEXT NOT NULL
                )
                """
            )
            _ensure_update_status_snapshot_columns(cursor, logger)
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_update_status_snapshot_updated_at
                ON update_status_snapshot(updated_at DESC)
                """
            )
            conn.commit()

    initialization_succeeded = False
    try:
        run_sqlite_with_retry(
            _initialize_schema,
            max_retries=_UPDATE_STATUS_SQLITE_RETRY_ATTEMPTS,
            retry_delay_seconds=_UPDATE_STATUS_SQLITE_RETRY_DELAY_SECONDS,
        )
        initialization_succeeded = True
        return True
    except Exception as error:
        logger.error(f"Failed to initialize update status sqlite cache: {error}")
        return False
    finally:
        with _UPDATE_STATUS_DB_INIT_CONDITION:
            _UPDATE_STATUS_DB_INIT_IN_PROGRESS.discard(db_key)
            if initialization_succeeded:
                add_bounded_ready_key(
                    _UPDATE_STATUS_DB_READY,
                    db_key,
                    max_entries=_UPDATE_STATUS_DB_READY_MAX_ENTRIES,
                )
            else:
                _UPDATE_STATUS_DB_READY.discard(db_key)
            _UPDATE_STATUS_DB_INIT_CONDITION.notify_all()


def _load_update_status_from_sqlite(
    *,
    update_status_file: str,
    logger,
    expected_signature: tuple[int, int] | None = None,
    _retried: bool = False,
) -> Dict[str, Any] | None:
    if not _ensure_update_status_sqlite(logger):
        return None
    lookup_keys = _update_status_file_lookup_keys(update_status_file)
    lookup_placeholders = build_sqlite_in_placeholders(lookup_keys)
    order_case_sql = build_sqlite_order_case_sql(
        column_name="file_path",
        lookup_keys=lookup_keys,
    )
    if expected_signature is None:
        query_sql = f"""
            SELECT payload_json
            FROM update_status_snapshot
            WHERE file_path IN ({lookup_placeholders})
            ORDER BY {order_case_sql}
            LIMIT 1
        """
        lookup_params: tuple[Any, ...] = (*lookup_keys, *lookup_keys)
    else:
        query_sql = f"""
            SELECT payload_json
            FROM update_status_snapshot
            WHERE file_path IN ({lookup_placeholders})
              AND mtime_ns = ?
              AND size_bytes = ?
            ORDER BY {order_case_sql}
            LIMIT 1
        """
        lookup_params = (
            *lookup_keys,
            int(expected_signature[0]),
            int(expected_signature[1]),
            *lookup_keys,
        )

    def _query_snapshot() -> tuple[Any, ...] | None:
        with connect_sqlite(
            _UPDATE_STATUS_CACHE_DB_PATH,
            timeout_seconds=_UPDATE_STATUS_SQLITE_TIMEOUT_SECONDS,
            pragmas=_UPDATE_STATUS_SESSION_PRAGMAS,
            read_only=True,
        ) as conn:
            cursor = conn.cursor()
            cursor.execute(
                query_sql,
                lookup_params,
            )
            return cursor.fetchone()

    try:
        row = run_sqlite_with_retry(
            _query_snapshot,
            max_retries=_UPDATE_STATUS_SQLITE_RETRY_ATTEMPTS,
            retry_delay_seconds=_UPDATE_STATUS_SQLITE_RETRY_DELAY_SECONDS,
        )
        if row is None:
            return None
        payload = json.loads(row[0])
        return payload if isinstance(payload, dict) else None
    except Exception as error:
        if (not _retried) and _is_missing_table_error(error):
            if _recover_update_status_sqlite(logger):
                return _load_update_status_from_sqlite(
                    update_status_file=update_status_file,
                    logger=logger,
                    _retried=True,
                )
        logger.error(f"Failed to load update status sqlite snapshot: {error}")
        return None


def _prune_update_status_snapshot_if_needed(
    cursor: sqlite3.Cursor,
    *,
    max_rows: int,
) -> None:
    normalized_max_rows = max(1, int(max_rows))
    prune_rows_by_updated_at_if_needed(
        cursor,
        table_name="update_status_snapshot",
        max_rows=normalized_max_rows,
    )


def _save_update_status_to_sqlite(
    *,
    update_status_file: str,
    status: Dict[str, Any],
    logger,
    file_signature: tuple[int, int] | None = None,
    _retried: bool = False,
) -> None:
    if not _ensure_update_status_sqlite(logger):
        return

    file_key = _normalize_update_status_file_key(update_status_file)
    normalized_max_rows = max(1, int(_UPDATE_STATUS_SQLITE_MAX_ROWS))
    should_prune_for_new_key = _mark_update_status_snapshot_key_seen(
        db_path=_UPDATE_STATUS_CACHE_DB_PATH,
        file_path=file_key,
    )
    should_force_prune = _should_force_update_status_snapshot_prune()
    should_prune_after_upsert = should_prune_for_new_key or should_force_prune
    try:
        payload_json = json.dumps(
            status,
            ensure_ascii=False,
            separators=(",", ":"),
            cls=NumpyEncoder,
        )

        def _upsert_snapshot() -> None:
            with connect_sqlite(
                _UPDATE_STATUS_CACHE_DB_PATH,
                timeout_seconds=_UPDATE_STATUS_SQLITE_TIMEOUT_SECONDS,
                pragmas=_UPDATE_STATUS_SESSION_PRAGMAS,
            ) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO update_status_snapshot (
                        file_path,
                        payload_json,
                        mtime_ns,
                        size_bytes,
                        updated_at
                    )
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(file_path) DO UPDATE SET
                        payload_json = excluded.payload_json,
                        mtime_ns = excluded.mtime_ns,
                        size_bytes = excluded.size_bytes,
                        updated_at = excluded.updated_at
                    """,
                    (
                        file_key,
                        payload_json,
                        int(file_signature[0]) if file_signature is not None else None,
                        int(file_signature[1]) if file_signature is not None else None,
                        datetime.now().isoformat(),
                    ),
                )
                if should_prune_after_upsert:
                    _prune_update_status_snapshot_if_needed(
                        cursor,
                        max_rows=normalized_max_rows,
                    )
                conn.commit()

        run_sqlite_with_retry(
            _upsert_snapshot,
            max_retries=_UPDATE_STATUS_SQLITE_RETRY_ATTEMPTS,
            retry_delay_seconds=_UPDATE_STATUS_SQLITE_RETRY_DELAY_SECONDS,
        )
    except Exception as error:
        if (not _retried) and _is_missing_table_error(error):
            if _recover_update_status_sqlite(logger):
                _save_update_status_to_sqlite(
                    update_status_file=update_status_file,
                    status=status,
                    logger=logger,
                    file_signature=file_signature,
                    _retried=True,
                )
                return
        logger.error(f"Failed to save update status sqlite snapshot: {error}")


def clear_update_status_cache() -> None:
    """상태 파일 시그니처 캐시를 초기화한다."""
    with _UPDATE_STATUS_CACHE_LOCK:
        _UPDATE_STATUS_CACHE.clear()
    with _UPDATE_STATUS_SQLITE_KNOWN_SNAPSHOT_KEYS_LOCK:
        _UPDATE_STATUS_SQLITE_KNOWN_SNAPSHOT_KEYS.clear()
    global _UPDATE_STATUS_SQLITE_SAVE_COUNTER
    with _UPDATE_STATUS_SQLITE_SAVE_COUNTER_LOCK:
        _UPDATE_STATUS_SQLITE_SAVE_COUNTER = 0


def default_update_status() -> Dict[str, Any]:
    """업데이트 상태 기본값."""
    return {
        "isRunning": False,
        "startTime": None,
        "currentItem": None,
        "items": [],
    }


def load_update_status(
    *,
    update_status_file: str,
    logger,
    deep_copy: bool = True,
) -> Dict[str, Any]:
    """상태 파일 로드."""
    default_status = default_update_status()
    cache_key = _normalize_update_status_file_key(update_status_file)
    signature = _status_file_signature(update_status_file)
    if signature is None:
        sqlite_status = _load_update_status_from_sqlite(
            update_status_file=update_status_file,
            logger=logger,
        )
        if sqlite_status is None:
            return default_status
        if deep_copy:
            return copy.deepcopy(sqlite_status)
        return sqlite_status

    with _UPDATE_STATUS_CACHE_LOCK:
        cached = _UPDATE_STATUS_CACHE.get(cache_key)
        if cached is not None and cached[0] == signature:
            _UPDATE_STATUS_CACHE.move_to_end(cache_key)
            if deep_copy:
                return copy.deepcopy(cached[1])
            return cached[1]

    sqlite_status = _load_update_status_from_sqlite(
        update_status_file=update_status_file,
        logger=logger,
        expected_signature=signature,
    )
    if sqlite_status is not None:
        with _UPDATE_STATUS_CACHE_LOCK:
            _UPDATE_STATUS_CACHE[cache_key] = (signature, copy.deepcopy(sqlite_status))
            _UPDATE_STATUS_CACHE.move_to_end(cache_key)
            _prune_update_status_cache_locked()
        if deep_copy:
            return copy.deepcopy(sqlite_status)
        return sqlite_status

    try:
        with open(update_status_file, "r", encoding="utf-8") as handle:
            loaded = json.load(handle)
    except Exception as error:
        logger.error(f"Failed to load update status: {error}")
        sqlite_status = _load_update_status_from_sqlite(
            update_status_file=update_status_file,
            logger=logger,
        )
        if sqlite_status is None:
            return default_status
        if deep_copy:
            return copy.deepcopy(sqlite_status)
        return sqlite_status

    loaded_status = loaded if isinstance(loaded, dict) else default_status
    with _UPDATE_STATUS_CACHE_LOCK:
        _UPDATE_STATUS_CACHE[cache_key] = (signature, copy.deepcopy(loaded_status))
        _UPDATE_STATUS_CACHE.move_to_end(cache_key)
        _prune_update_status_cache_locked()
    _save_update_status_to_sqlite(
        update_status_file=update_status_file,
        status=loaded_status,
        logger=logger,
        file_signature=signature,
    )
    if deep_copy:
        return copy.deepcopy(loaded_status)
    return loaded_status


def save_update_status(*, status: Dict[str, Any], update_status_file: str, logger) -> None:
    """상태 파일 저장 (Atomic Write)."""
    try:
        _ensure_parent_dir(update_status_file)
        tmp_file = update_status_file + ".tmp"
        with open(tmp_file, "w", encoding="utf-8") as handle:
            json.dump(status, handle, indent=2, ensure_ascii=False, cls=NumpyEncoder)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_file, update_status_file)
        cache_key = _normalize_update_status_file_key(update_status_file)
        signature = _status_file_signature(update_status_file)
        if signature is not None:
            with _UPDATE_STATUS_CACHE_LOCK:
                _UPDATE_STATUS_CACHE[cache_key] = (signature, copy.deepcopy(status))
                _UPDATE_STATUS_CACHE.move_to_end(cache_key)
                _prune_update_status_cache_locked()
        _save_update_status_to_sqlite(
            update_status_file=update_status_file,
            status=status,
            logger=logger,
            file_signature=signature,
        )
    except Exception as error:
        logger.error(f"Failed to save update status: {error}")


def start_update(
    *,
    items_list: list[str],
    update_lock,
    update_status_file: str,
    shared_state,
    logger,
) -> None:
    """업데이트 시작."""
    with update_lock:
        shared_state.STOP_REQUESTED = False
        status = load_update_status(update_status_file=update_status_file, logger=logger)
        status["isRunning"] = True
        status["startTime"] = datetime.now().isoformat()
        status["items"] = [{"name": name, "status": "pending"} for name in items_list]
        status["currentItem"] = None
        save_update_status(status=status, update_status_file=update_status_file, logger=logger)


def update_item_status(
    *,
    name: str,
    status_code: str,
    update_lock,
    update_status_file: str,
    logger,
) -> None:
    """아이템 상태 업데이트."""
    with update_lock:
        status = load_update_status(update_status_file=update_status_file, logger=logger)
        for item in status["items"]:
            if item["name"] == name:
                item["status"] = status_code
                if status_code == "running":
                    status["currentItem"] = name
                break
        save_update_status(status=status, update_status_file=update_status_file, logger=logger)


def stop_update(
    *,
    update_lock,
    update_status_file: str,
    shared_state,
    logger,
) -> None:
    """업데이트 중단."""
    with update_lock:
        shared_state.STOP_REQUESTED = True
        status = load_update_status(update_status_file=update_status_file, logger=logger)
        status["isRunning"] = False
        status["currentItem"] = None

        for item in status["items"]:
            if item["status"] == "running":
                item["status"] = "error"
            elif item["status"] == "pending":
                item["status"] = "cancelled"

        save_update_status(status=status, update_status_file=update_status_file, logger=logger)


def finish_update(
    *,
    update_lock,
    update_status_file: str,
    logger,
) -> None:
    """업데이트 완료."""
    with update_lock:
        status = load_update_status(update_status_file=update_status_file, logger=logger)
        status["isRunning"] = False
        status["currentItem"] = None
        save_update_status(status=status, update_status_file=update_status_file, logger=logger)
