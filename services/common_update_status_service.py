#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
공통 업데이트 상태 파일/전이 관리 서비스.
"""

from __future__ import annotations

import copy
import fcntl
import json
import os
import sqlite3
import threading
from collections import OrderedDict
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Dict

from numpy_json_encoder import NumpyEncoder
from services.sqlite_utils import (
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
from services.sqlite_ready_gate import SqliteReadyGate


_UPDATE_STATUS_CACHE: OrderedDict[str, tuple[tuple[int, int], Dict[str, Any]]] = OrderedDict()
_UPDATE_STATUS_CACHE_LOCK = threading.Lock()
_UPDATE_STATUS_CACHE_MAX_ENTRIES = 2_048
_UPDATE_STATUS_DB_READY_GATE = SqliteReadyGate()
_UPDATE_STATUS_DB_INIT_LOCK = _UPDATE_STATUS_DB_READY_GATE.lock
_UPDATE_STATUS_DB_INIT_CONDITION = _UPDATE_STATUS_DB_READY_GATE.condition
_UPDATE_STATUS_DB_INIT_IN_PROGRESS = _UPDATE_STATUS_DB_READY_GATE.in_progress_keys
_UPDATE_STATUS_DB_READY = _UPDATE_STATUS_DB_READY_GATE.ready_keys
_UPDATE_STATUS_DB_READY_MAX_ENTRIES = 2_048
_UPDATE_STATUS_SQLITE_KNOWN_SNAPSHOT_KEYS: OrderedDict[tuple[str, str], None] = OrderedDict()
_UPDATE_STATUS_SQLITE_KNOWN_SNAPSHOT_KEYS_LOCK = threading.Lock()
_UPDATE_STATUS_SQLITE_KNOWN_SNAPSHOT_KEYS_MAX_ENTRIES = 4_096
_UPDATE_STATUS_SQLITE_PRUNE_FORCE_INTERVAL = 64
_UPDATE_STATUS_SQLITE_SAVE_COUNTER = 0
_UPDATE_STATUS_SQLITE_SAVE_COUNTER_LOCK = threading.Lock()
# 데이터 파일(DATA_DIR = "data")과 같은 cwd 기준 data/ 를 따라야 격리 실행이 원본에 쓰지 않는다.
_UPDATE_STATUS_CACHE_DB_PATH = os.path.join("data", "runtime_cache.db")
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

    def _on_failure(error: Exception) -> None:
        logger.error(f"Failed to initialize update status sqlite cache: {error}")

    return _UPDATE_STATUS_DB_READY_GATE.ensure(
        db_path,
        initialize=_initialize_schema,
        db_path_exists=sqlite_db_path_exists,
        run_with_retry=run_sqlite_with_retry,
        retry_attempts=_UPDATE_STATUS_SQLITE_RETRY_ATTEMPTS,
        retry_delay_seconds=_UPDATE_STATUS_SQLITE_RETRY_DELAY_SECONDS,
        on_failure=_on_failure,
        max_ready_entries=_UPDATE_STATUS_DB_READY_MAX_ENTRIES,
    )


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


@contextmanager
def _status_file_lock(update_status_file: str, logger):
    """[INFRA-098] update_lock 은 워커 안에서만 듣는다. 상태를 읽고-수정-쓰는 동안 워커 사이도 막는다."""
    try:
        _ensure_parent_dir(update_status_file)
        lock_fp = open(update_status_file + ".lock", "a+")
    except OSError as error:
        # ponytail: 잠금 파일을 못 열면(권한 등) 종전처럼 워커 안 잠금만으로 진행한다. 여기서 예외를 내면
        # 중단·완료 요청이 500 이 되고 isRunning 이 재기동 전까지 고착된다
        logger.error(f"Update status file lock unavailable, continuing without it: {error}")
        lock_fp = None
    if lock_fp is None:
        yield
        return
    with lock_fp:
        fcntl.flock(lock_fp.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock_fp.fileno(), fcntl.LOCK_UN)


def _read_status_file(update_status_file: str, logger) -> Dict[str, Any]:
    """잠금 안에서 쓰는 읽기. (mtime, size) 캐시는 같은 틱의 다른 워커 저장을 놓치므로 파일을 직접 읽는다."""
    try:
        with open(update_status_file, "r", encoding="utf-8") as handle:
            loaded = json.load(handle)
        if isinstance(loaded, dict):
            return loaded
    except FileNotFoundError:
        pass
    except Exception as error:
        logger.error(f"Failed to load update status: {error}")
    # 파일이 없거나 깨졌으면 load_update_status 처럼 스냅샷을 쓴다. 기본값(startTime 없음)에서 출발하면
    # 실행 중인 워커의 감시가 중단을 자기 실행의 것으로 알아보지 못한다
    snapshot = _load_update_status_from_sqlite(update_status_file=update_status_file, logger=logger)
    return snapshot if snapshot is not None else default_update_status()


def start_update(
    *,
    items_list: list[str],
    update_lock,
    update_status_file: str,
    shared_state,
    logger,
) -> bool:
    """업데이트 시작. 이 워커에서 앞 실행이 아직 돌면 상태를 바꾸지 않고 False 를 돌려준다."""
    with update_lock, _status_file_lock(update_status_file, logger):
        if getattr(shared_state, "LOCAL_PIPELINE_ACTIVE", False):
            # [INFRA-099] 중단된 앞 실행이 끝나기 전이다. 플래그가 워커에 하나뿐이라 받으면 둘이 함께 돈다.
            # 상태를 그대로 두면 남은 stopRequested 를 앞 실행의 감시가 읽고 멈춘다
            logger.warning("Update start refused: a previous update is still running in this worker")
            return False
        shared_state.STOP_REQUESTED = False
        status = _read_status_file(update_status_file, logger)
        status["isRunning"] = True
        status["stopRequested"] = False
        status["startTime"] = datetime.now().isoformat()
        # [INFRA-107] 기동 초기화가 소유 워커 생존을 판정한다. 마스터 pid 는 재부팅 뒤 pid 재사용을 거른다
        status["ownerPid"] = os.getpid()
        status["ownerPpid"] = os.getppid()
        shared_state.LOCAL_RUN_START_TIME = status["startTime"]
        # [INFRA-104] 스레드가 파이프라인에 들어가기 전에도 같은 워커의 재시작을 거부하도록 여기서 켠다.
        # 파이프라인의 finally 가 끈다. ponytail: thread.start() 가 실패하면 이 워커는 재기동까지 시작을 거부한다
        shared_state.LOCAL_PIPELINE_ACTIVE = True
        status["items"] = [{"name": name, "status": "pending"} for name in items_list]
        status["currentItem"] = None
        save_update_status(status=status, update_status_file=update_status_file, logger=logger)
        return True


def _owner_process_alive(pid: Any) -> bool:
    """[INFRA-107] 상태를 연 워커가 아직 살아 있는가. 자기 pid 는 방금 뜬 워커이므로 옛 실행의 주인이 아니다."""
    if type(pid) is not int or pid <= 0 or pid == os.getpid():
        return False
    try:
        os.kill(pid, 0)
    except PermissionError:
        return True
    except (OSError, OverflowError):
        return False
    return True


def owned_by_live_sibling(status: Any) -> bool:
    """[INFRA-114] 상태를 쓴 워커가 같은 마스터 아래 살아 있는 다른 워커인가. 전체 재기동은 마스터가 바뀌어 항상 거짓이다."""
    # ponytail: 같은 마스터 안의 pid 재사용과 graceful 재기동(HUP)의 옛 워커는 살아 있다고 본다. 그때 update 는 관리자 중단 요청, V2 는 다음 전체 재기동(그때까지 17시 체인도 30분 기다린 뒤 종가베팅을 건너뛴다 [INFRA-116]), 스케줄러 플래그는 다음 잡의 finally 가 푼다
    return (
        isinstance(status, dict)
        and status.get("ownerPpid") == os.getppid()
        and _owner_process_alive(status.get("ownerPid"))
    )


def reset_orphaned_update_status(*, update_status_file: str, logger) -> bool:
    """기동 때 주인이 사라진 실행 상태만 내린다. 다른 워커가 살아서 돌리는 실행은 그대로 둔다."""
    with _status_file_lock(update_status_file, logger):
        status = _read_status_file(update_status_file, logger)
        if not status.get("isRunning", False):
            return False
        if owned_by_live_sibling(status):
            logger.info(f"Startup reset skipped: update owned by live worker {status.get('ownerPid')}")
            return False
        status["isRunning"] = False
        status["items"] = []
        save_update_status(status=status, update_status_file=update_status_file, logger=logger)
        return True


def update_item_status(
    *,
    name: str,
    status_code: str,
    update_lock,
    update_status_file: str,
    logger,
    start_time: str | None = None,
) -> None:
    """아이템 상태 업데이트. start_time 이 주어지면 그 실행이 아직 상태의 주인일 때만 쓴다."""
    with update_lock, _status_file_lock(update_status_file, logger):
        status = _read_status_file(update_status_file, logger)
        if start_time is not None and status.get("startTime") != start_time:
            # [INFRA-101] 다른 워커의 새 실행에 대체된 옛 실행이다. 이름이 같은 새 실행 항목에 쓰지 않는다
            logger.info(f"Item status skipped for replaced run: {name} -> {status_code}")
            return
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
    logger,
) -> None:
    """업데이트 중단."""
    with update_lock, _status_file_lock(update_status_file, logger):
        # [INFRA-097] 작업은 다른 워커에서 돌 수 있으므로 이 워커의 플래그가 아니라 공유 상태에 남긴다.
        # 작업을 돌리는 워커의 감시 스레드(run_background_update_pipeline)가 그 워커의 플래그를 켠다
        status = _read_status_file(update_status_file, logger)
        status["isRunning"] = False
        status["stopRequested"] = True
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
    start_time: str | None = None,
) -> None:
    """업데이트 완료. start_time 이 주어지면 그 실행이 아직 상태의 주인일 때만 끝낸다."""
    with update_lock, _status_file_lock(update_status_file, logger):
        status = _read_status_file(update_status_file, logger)
        if start_time is not None and status.get("startTime") not in (None, start_time):
            # [INFRA-098] 중단된 사이 다른 워커에서 새 실행이 시작됐다. 그 상태를 끝내는 것은 새 실행의 몫이다
            logger.info("Finish skipped for replaced run")
            return
        status["isRunning"] = False
        status["currentItem"] = None
        save_update_status(status=status, update_status_file=update_status_file, logger=logger)
