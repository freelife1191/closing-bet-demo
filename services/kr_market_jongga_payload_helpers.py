#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KR Market Jongga Payload Helpers
"""

from __future__ import annotations

import copy
import glob
import hashlib
import json
import os
import sqlite3
import threading
from datetime import datetime
from typing import Any, Callable

from services.kr_market_data_cache_service import (
    atomic_write_text,
    load_json_payload_from_path,
)
from services.sqlite_utils import (
    build_sqlite_pragmas,
    connect_sqlite,
    is_sqlite_missing_table_error,
    normalize_sqlite_db_key,
    prune_rows_by_updated_at_if_needed,
    run_sqlite_with_retry,
    sqlite_db_path_exists,
)


_RECENT_JONGGA_PAYLOAD_CACHE: dict[str, dict[str, Any]] = {}
_RECENT_JONGGA_SQLITE_READY: set[str] = set()
_RECENT_JONGGA_SQLITE_READY_LOCK = threading.Lock()
_RECENT_JONGGA_SQLITE_MAX_ROWS = 64
_RECENT_JONGGA_SQLITE_INIT_PRAGMAS = build_sqlite_pragmas(busy_timeout_ms=30_000)
_RECENT_JONGGA_SQLITE_SESSION_PRAGMAS = build_sqlite_pragmas(busy_timeout_ms=30_000)
_RECENT_JONGGA_SQLITE_RETRY_ATTEMPTS = 2
_RECENT_JONGGA_SQLITE_RETRY_DELAY_SECONDS = 0.03


def _collect_result_files(data_dir: str) -> list[str]:
    pattern = os.path.join(data_dir, "jongga_v2_results_*.json")
    return sorted(glob.glob(pattern), reverse=True)


def _build_result_files_signature(files: list[str]) -> tuple[int, int]:
    """결과 파일 목록의 변경 여부를 나타내는 경량 시그니처."""
    fold = 0
    for idx, file_path in enumerate(files):
        try:
            stat = os.stat(file_path)
            fold ^= int(stat.st_mtime_ns)
            fold ^= int(stat.st_size) << (idx % 11)
        except FileNotFoundError:
            continue
        except Exception:
            continue
    return (len(files), fold)


def _clone_payload(payload: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return None
    return copy.deepcopy(payload)


def _log_debug(logger: Any, message: str) -> None:
    debug_fn = getattr(logger, "debug", None)
    if callable(debug_fn):
        debug_fn(message)


def _runtime_cache_db_path(data_dir: str) -> str:
    return os.path.join(data_dir, "runtime_cache.db")


def _invalidate_recent_payload_sqlite_ready(db_path: str) -> None:
    db_key = normalize_sqlite_db_key(db_path)
    with _RECENT_JONGGA_SQLITE_READY_LOCK:
        _RECENT_JONGGA_SQLITE_READY.discard(db_key)


def _is_missing_table_error(error: Exception) -> bool:
    return is_sqlite_missing_table_error(error, table_names="jongga_recent_valid_payload_cache")


def _recover_recent_payload_sqlite_schema(data_dir: str, logger: Any) -> bool:
    db_path = _runtime_cache_db_path(data_dir)
    _invalidate_recent_payload_sqlite_ready(db_path)
    return _ensure_recent_payload_sqlite(data_dir, logger)


def _signature_digest(signature: tuple[int, int]) -> str:
    raw = f"{int(signature[0])}:{int(signature[1])}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _ensure_recent_payload_sqlite(data_dir: str, logger: Any) -> bool:
    db_path = _runtime_cache_db_path(data_dir)
    db_key = normalize_sqlite_db_key(db_path)
    with _RECENT_JONGGA_SQLITE_READY_LOCK:
        if db_key in _RECENT_JONGGA_SQLITE_READY:
            if sqlite_db_path_exists(db_path):
                return True
            _RECENT_JONGGA_SQLITE_READY.discard(db_key)

        def _initialize_schema() -> None:
            with connect_sqlite(
                db_path,
                timeout_seconds=30,
                pragmas=_RECENT_JONGGA_SQLITE_INIT_PRAGMAS,
            ) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS jongga_recent_valid_payload_cache (
                        cache_key TEXT NOT NULL,
                        signature_hash TEXT NOT NULL,
                        payload_json TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        PRIMARY KEY (cache_key, signature_hash)
                    )
                    """
                )
                cursor.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_jongga_recent_valid_payload_cache_updated_at
                    ON jongga_recent_valid_payload_cache(updated_at DESC)
                    """
                )
                conn.commit()

        try:
            run_sqlite_with_retry(
                _initialize_schema,
                max_retries=_RECENT_JONGGA_SQLITE_RETRY_ATTEMPTS,
                retry_delay_seconds=_RECENT_JONGGA_SQLITE_RETRY_DELAY_SECONDS,
            )
            _RECENT_JONGGA_SQLITE_READY.add(db_key)
            return True
        except Exception as error:
            _log_debug(logger, f"Failed to initialize recent jongga sqlite cache: {error}")
            return False


def _load_recent_payload_from_sqlite(
    *,
    data_dir: str,
    cache_key: str,
    signature: tuple[int, int],
    logger: Any,
) -> dict[str, Any] | None:
    if not _ensure_recent_payload_sqlite(data_dir, logger):
        return None

    db_path = _runtime_cache_db_path(data_dir)
    def _query_row() -> tuple[Any, ...] | None:
        with connect_sqlite(
            db_path,
            timeout_seconds=30,
            pragmas=_RECENT_JONGGA_SQLITE_SESSION_PRAGMAS,
        ) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT payload_json
                FROM jongga_recent_valid_payload_cache
                WHERE cache_key = ?
                  AND signature_hash = ?
                LIMIT 1
                """,
                (cache_key, _signature_digest(signature)),
            )
            return cursor.fetchone()

    try:
        row = run_sqlite_with_retry(
            _query_row,
            max_retries=_RECENT_JONGGA_SQLITE_RETRY_ATTEMPTS,
            retry_delay_seconds=_RECENT_JONGGA_SQLITE_RETRY_DELAY_SECONDS,
        )
    except Exception as error:
        if _is_missing_table_error(error) and _recover_recent_payload_sqlite_schema(data_dir, logger):
            try:
                row = run_sqlite_with_retry(
                    _query_row,
                    max_retries=_RECENT_JONGGA_SQLITE_RETRY_ATTEMPTS,
                    retry_delay_seconds=_RECENT_JONGGA_SQLITE_RETRY_DELAY_SECONDS,
                )
            except Exception as retry_error:
                _log_debug(logger, f"Failed to load recent jongga payload from sqlite after schema recovery: {retry_error}")
                return None
        else:
            _log_debug(logger, f"Failed to load recent jongga payload from sqlite: {error}")
            return None

    try:
        if not row:
            return None
        payload = json.loads(row[0])
        if isinstance(payload, dict):
            return payload
        return None
    except Exception as error:
        _log_debug(logger, f"Failed to load recent jongga payload from sqlite: {error}")
        return None


def _prune_recent_payload_cache_if_needed(
    cursor: sqlite3.Cursor,
    *,
    max_rows: int,
) -> None:
    normalized_max_rows = max(1, int(max_rows))
    prune_rows_by_updated_at_if_needed(
        cursor,
        table_name="jongga_recent_valid_payload_cache",
        max_rows=normalized_max_rows,
    )


def _save_recent_payload_to_sqlite(
    *,
    data_dir: str,
    cache_key: str,
    signature: tuple[int, int],
    payload: dict[str, Any],
    logger: Any,
) -> None:
    if not _ensure_recent_payload_sqlite(data_dir, logger):
        return
    if not isinstance(payload, dict):
        return

    db_path = _runtime_cache_db_path(data_dir)
    try:
        payload_json = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    except Exception as error:
        _log_debug(logger, f"Failed to serialize recent jongga payload: {error}")
        return

    normalized_max_rows = max(1, int(_RECENT_JONGGA_SQLITE_MAX_ROWS))
    def _upsert_payload() -> None:
        with connect_sqlite(
            db_path,
            timeout_seconds=30,
            pragmas=_RECENT_JONGGA_SQLITE_SESSION_PRAGMAS,
        ) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO jongga_recent_valid_payload_cache (
                    cache_key,
                    signature_hash,
                    payload_json,
                    updated_at
                ) VALUES (?, ?, ?, ?)
                ON CONFLICT(cache_key, signature_hash) DO UPDATE SET
                    payload_json = excluded.payload_json,
                    updated_at = excluded.updated_at
                """,
                (
                    cache_key,
                    _signature_digest(signature),
                    payload_json,
                    datetime.now().isoformat(),
                ),
            )
            _prune_recent_payload_cache_if_needed(
                cursor,
                max_rows=normalized_max_rows,
            )
            conn.commit()

    try:
        run_sqlite_with_retry(
            _upsert_payload,
            max_retries=_RECENT_JONGGA_SQLITE_RETRY_ATTEMPTS,
            retry_delay_seconds=_RECENT_JONGGA_SQLITE_RETRY_DELAY_SECONDS,
        )
    except Exception as error:
        if _is_missing_table_error(error) and _recover_recent_payload_sqlite_schema(data_dir, logger):
            try:
                run_sqlite_with_retry(
                    _upsert_payload,
                    max_retries=_RECENT_JONGGA_SQLITE_RETRY_ATTEMPTS,
                    retry_delay_seconds=_RECENT_JONGGA_SQLITE_RETRY_DELAY_SECONDS,
                )
            except Exception as retry_error:
                _log_debug(logger, f"Failed to save recent jongga payload into sqlite after schema recovery: {retry_error}")
        else:
            _log_debug(logger, f"Failed to save recent jongga payload into sqlite: {error}")


def has_non_empty_signals(payload: dict[str, Any] | None) -> bool:
    if not isinstance(payload, dict):
        return False
    signals = payload.get("signals", [])
    return isinstance(signals, list) and len(signals) > 0


def load_json_from_path(file_path: str, logger: Any) -> dict[str, Any] | None:
    try:
        data = load_json_payload_from_path(file_path)
        return data if isinstance(data, dict) else None
    except Exception as error:
        logger.warning(f"파일 읽기 실패: {file_path} - {error}")
        return None


def write_json_to_path(file_path: str, payload: dict[str, Any], logger: Any) -> None:
    try:
        content = json.dumps(payload, ensure_ascii=False, indent=2)
        atomic_write_text(file_path, content)
    except Exception as error:
        logger.warning(f"파일 저장 실패: {file_path} - {error}")


def find_recent_valid_jongga_payload(
    *,
    data_dir: str,
    recalculate_jongga_grades: Callable[[dict[str, Any]], bool],
    logger: Any,
) -> dict[str, Any] | None:
    cache_key = os.path.abspath(data_dir)
    files = _collect_result_files(data_dir)
    signature = _build_result_files_signature(files)
    cached = _RECENT_JONGGA_PAYLOAD_CACHE.get(cache_key)
    if cached and cached.get("signature") == signature:
        return _clone_payload(cached.get("payload"))

    sqlite_cached_payload = _load_recent_payload_from_sqlite(
        data_dir=data_dir,
        cache_key=cache_key,
        signature=signature,
        logger=logger,
    )
    if sqlite_cached_payload is not None:
        _RECENT_JONGGA_PAYLOAD_CACHE[cache_key] = {
            "signature": signature,
            "payload": _clone_payload(sqlite_cached_payload),
        }
        return _clone_payload(sqlite_cached_payload)

    resolved_payload: dict[str, Any] | None = None
    for file_path in files:
        candidate = load_json_from_path(file_path, logger)
        if not has_non_empty_signals(candidate):
            continue

        if recalculate_jongga_grades(candidate):
            write_json_to_path(file_path, candidate, logger)

        candidate["message"] = f"주말/휴일로 인해 {candidate.get('date', '')} 거래일 데이터를 표시합니다."
        logger.info(f"[Jongga V2] 최근 유효 데이터 사용: {file_path}")
        resolved_payload = candidate
        break

    _RECENT_JONGGA_PAYLOAD_CACHE[cache_key] = {
        "signature": signature,
        "payload": _clone_payload(resolved_payload),
    }
    if resolved_payload is not None:
        _save_recent_payload_to_sqlite(
            data_dir=data_dir,
            cache_key=cache_key,
            signature=signature,
            payload=resolved_payload,
            logger=logger,
        )
    return _clone_payload(resolved_payload)


def build_no_jongga_data_payload(current_time: datetime) -> dict[str, Any]:
    return {
        "date": current_time.date().isoformat(),
        "signals": [],
        "filtered_count": 0,
        "status": "no_data",
        "message": "현재 종가베팅 데이터가 없습니다. [업데이트] 버튼을 눌러 분석을 실행해주세요.",
    }
