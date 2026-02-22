#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KR Market Cumulative Performance Cache

누적 성과 응답 payload(kpi + trades)를 파일 시그니처 기반으로 캐시한다.
- 메모리 캐시
- SQLite(runtime_cache.db) 영속 캐시
"""

from __future__ import annotations

import copy
import glob
import hashlib
import json
import os
import threading
from datetime import datetime
from typing import Any, Callable

from numpy_json_encoder import NumpyEncoder
from services.file_row_count_cache import file_signature
from services.sqlite_utils import connect_sqlite


_CUMULATIVE_CACHE: dict[tuple[Any, ...], dict[str, Any]] = {}
_CUMULATIVE_CACHE_LOCK = threading.Lock()
_CUMULATIVE_SQLITE_LOCK = threading.Lock()
_CUMULATIVE_SQLITE_READY: set[str] = set()

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_CUMULATIVE_CACHE_DB_PATH = os.path.join(_BASE_DIR, "data", "runtime_cache.db")
_CUMULATIVE_MEMORY_MAX_ENTRIES = 8
_CUMULATIVE_SQLITE_MAX_ROWS = 16


def clear_cumulative_cache() -> None:
    with _CUMULATIVE_CACHE_LOCK:
        _CUMULATIVE_CACHE.clear()


def _save_memory_cache_entry(signature: tuple[Any, ...], payload: dict[str, Any]) -> None:
    with _CUMULATIVE_CACHE_LOCK:
        if signature not in _CUMULATIVE_CACHE and len(_CUMULATIVE_CACHE) >= _CUMULATIVE_MEMORY_MAX_ENTRIES:
            _CUMULATIVE_CACHE.clear()
        _CUMULATIVE_CACHE[signature] = copy.deepcopy(payload)


def _resolve_data_dir(
    *,
    get_data_path: Callable[[str], str] | None,
    data_dir_getter: Callable[[], str] | None,
) -> str | None:
    if data_dir_getter is not None:
        try:
            value = data_dir_getter()
            if value:
                return str(value)
        except Exception:
            return None

    if get_data_path is None:
        return None
    try:
        sample = get_data_path("daily_prices.csv")
    except Exception:
        return None
    if not sample:
        return None
    return os.path.dirname(sample)


def _collect_jongga_signatures(data_dir: str) -> tuple[tuple[str, int, int], ...]:
    pattern = os.path.join(data_dir, "jongga_v2_results_*.json")
    parts: list[tuple[str, int, int]] = []
    for filepath in sorted(glob.glob(pattern), reverse=True):
        sig = file_signature(filepath)
        if sig is None:
            continue
        parts.append((filepath, int(sig[0]), int(sig[1])))
    return tuple(parts)


def build_cumulative_cache_signature(
    *,
    get_data_path: Callable[[str], str] | None = None,
    data_dir_getter: Callable[[], str] | None = None,
) -> tuple[Any, ...] | None:
    data_dir = _resolve_data_dir(get_data_path=get_data_path, data_dir_getter=data_dir_getter)
    if data_dir is None and get_data_path is None:
        return None

    if get_data_path is not None:
        daily_prices_path = get_data_path("daily_prices.csv")
    elif data_dir:
        daily_prices_path = os.path.join(data_dir, "daily_prices.csv")
    else:
        daily_prices_path = ""

    jongga_sigs = _collect_jongga_signatures(data_dir or "")
    return (
        ("data_dir", str(data_dir or "")),
        ("daily_prices", file_signature(daily_prices_path) if daily_prices_path else None),
        ("jongga_results", jongga_sigs),
    )


def _signature_hash(signature: tuple[Any, ...]) -> str:
    serialized = json.dumps(signature, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _ensure_cumulative_sqlite(logger: Any) -> bool:
    db_path = _CUMULATIVE_CACHE_DB_PATH
    if db_path in _CUMULATIVE_SQLITE_READY:
        return True

    with _CUMULATIVE_SQLITE_LOCK:
        if db_path in _CUMULATIVE_SQLITE_READY:
            return True
        try:
            os.makedirs(os.path.dirname(db_path), exist_ok=True)
            with connect_sqlite(
                db_path,
                timeout_seconds=5,
                pragmas=(
                    "PRAGMA journal_mode=WAL",
                    "PRAGMA synchronous=NORMAL",
                    "PRAGMA temp_store=MEMORY",
                    "PRAGMA busy_timeout=5000",
                ),
            ) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS cumulative_performance_cache (
                        cache_hash TEXT PRIMARY KEY,
                        payload_json TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    )
                    """
                )
                cursor.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_cumulative_performance_cache_updated_at
                    ON cumulative_performance_cache(updated_at DESC)
                    """
                )
                conn.commit()
            _CUMULATIVE_SQLITE_READY.add(db_path)
            return True
        except Exception as error:
            logger.debug(f"Failed to initialize cumulative sqlite cache: {error}")
            return False


def _load_from_sqlite(signature: tuple[Any, ...], logger: Any) -> dict[str, Any] | None:
    if not _ensure_cumulative_sqlite(logger):
        return None

    cache_hash = _signature_hash(signature)
    try:
        with connect_sqlite(
            _CUMULATIVE_CACHE_DB_PATH,
            timeout_seconds=5,
            pragmas=("PRAGMA busy_timeout=5000",),
        ) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT payload_json
                FROM cumulative_performance_cache
                WHERE cache_hash = ?
                """,
                (cache_hash,),
            )
            row = cursor.fetchone()
        if row is None:
            return None
        payload = json.loads(row[0])
        if not isinstance(payload, dict):
            return None
        if not isinstance(payload.get("trades"), list):
            return None
        return payload
    except Exception as error:
        logger.debug(f"Failed to load cumulative sqlite cache: {error}")
        return None


def _save_to_sqlite(signature: tuple[Any, ...], payload: dict[str, Any], logger: Any) -> None:
    if not _ensure_cumulative_sqlite(logger):
        return

    cache_hash = _signature_hash(signature)
    try:
        payload_json = json.dumps(payload, ensure_ascii=False, cls=NumpyEncoder)
        with connect_sqlite(
            _CUMULATIVE_CACHE_DB_PATH,
            timeout_seconds=5,
            pragmas=("PRAGMA busy_timeout=5000",),
        ) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO cumulative_performance_cache (cache_hash, payload_json, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(cache_hash) DO UPDATE SET
                    payload_json = excluded.payload_json,
                    updated_at = excluded.updated_at
                """,
                (cache_hash, payload_json, datetime.now().isoformat()),
            )
            cursor.execute(
                """
                DELETE FROM cumulative_performance_cache
                WHERE cache_hash NOT IN (
                    SELECT cache_hash
                    FROM cumulative_performance_cache
                    ORDER BY updated_at DESC
                    LIMIT ?
                )
                """,
                (_CUMULATIVE_SQLITE_MAX_ROWS,),
            )
            conn.commit()
    except Exception as error:
        logger.debug(f"Failed to save cumulative sqlite cache: {error}")


def get_cached_cumulative_payload(
    *,
    signature: tuple[Any, ...] | None,
    logger: Any,
) -> dict[str, Any] | None:
    if signature is None:
        return None

    with _CUMULATIVE_CACHE_LOCK:
        cached = _CUMULATIVE_CACHE.get(signature)
        if cached is not None:
            return copy.deepcopy(cached)

    sqlite_cached = _load_from_sqlite(signature, logger)
    if sqlite_cached is None:
        return None

    _save_memory_cache_entry(signature, sqlite_cached)
    return sqlite_cached


def save_cached_cumulative_payload(
    *,
    signature: tuple[Any, ...] | None,
    payload: dict[str, Any],
    logger: Any,
) -> None:
    if signature is None:
        return
    _save_memory_cache_entry(signature, payload)
    _save_to_sqlite(signature, payload, logger)


__all__ = [
    "build_cumulative_cache_signature",
    "clear_cumulative_cache",
    "get_cached_cumulative_payload",
    "save_cached_cumulative_payload",
]
