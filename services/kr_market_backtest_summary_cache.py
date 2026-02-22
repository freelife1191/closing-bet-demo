#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KR Market Backtest Summary Cache

백테스트 요약 응답을 파일 시그니처 기반으로 캐시한다.
- 메모리 캐시
- SQLite(runtime_cache.db) 영속 캐시
"""

from __future__ import annotations

import copy
import glob
import hashlib
import heapq
import json
import os
import threading
from datetime import datetime
from typing import Any, Callable

from numpy_json_encoder import NumpyEncoder
from services.file_row_count_cache import file_signature
from services.sqlite_utils import connect_sqlite


_BACKTEST_SUMMARY_CACHE: dict[tuple[Any, ...], dict[str, Any]] = {}
_BACKTEST_SUMMARY_CACHE_LOCK = threading.Lock()
_BACKTEST_SUMMARY_SQLITE_LOCK = threading.Lock()
_BACKTEST_SUMMARY_SQLITE_READY: set[str] = set()

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_BACKTEST_SUMMARY_CACHE_DB_PATH = os.path.join(_BASE_DIR, "data", "runtime_cache.db")
_BACKTEST_SUMMARY_MEMORY_MAX_ENTRIES = 16
_BACKTEST_SUMMARY_SQLITE_MAX_ROWS = 64


def clear_backtest_summary_cache() -> None:
    with _BACKTEST_SUMMARY_CACHE_LOCK:
        _BACKTEST_SUMMARY_CACHE.clear()


def _save_memory_cache_entry(signature: tuple[Any, ...], payload: dict[str, Any]) -> None:
    with _BACKTEST_SUMMARY_CACHE_LOCK:
        if signature not in _BACKTEST_SUMMARY_CACHE and len(_BACKTEST_SUMMARY_CACHE) >= _BACKTEST_SUMMARY_MEMORY_MAX_ENTRIES:
            _BACKTEST_SUMMARY_CACHE.clear()
        _BACKTEST_SUMMARY_CACHE[signature] = copy.deepcopy(payload)


def _normalize_for_json(value: Any) -> Any:
    if isinstance(value, tuple):
        return [_normalize_for_json(item) for item in value]
    if isinstance(value, list):
        return [_normalize_for_json(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _normalize_for_json(item) for key, item in value.items()}
    return value


def _serialize_cache_signature(signature: tuple[Any, ...]) -> str:
    normalized = _normalize_for_json(signature)
    return json.dumps(
        normalized,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _cache_hash(signature: tuple[Any, ...]) -> tuple[str, str]:
    signature_json = _serialize_cache_signature(signature)
    digest = hashlib.sha256(signature_json.encode("utf-8")).hexdigest()
    return digest, signature_json


def _safe_file_signature(path: str | None) -> tuple[int, int] | None:
    if not path:
        return None
    return file_signature(path)


def _resolve_data_dir(
    *,
    get_data_path: Callable[[str], str] | None,
    data_dir_getter: Callable[[], str] | None,
) -> str | None:
    if data_dir_getter is not None:
        try:
            data_dir = data_dir_getter()
            if data_dir:
                return str(data_dir)
        except Exception:
            return None

    if get_data_path is None:
        return None

    try:
        sample_path = get_data_path("daily_prices.csv")
    except Exception:
        return None

    if not sample_path:
        return None
    return os.path.dirname(sample_path)


def _build_recent_jongga_results_signature(
    *,
    data_dir: str | None,
    limit: int,
) -> tuple[tuple[str, int, int], ...]:
    if not data_dir:
        return ()

    pattern = os.path.join(data_dir, "jongga_v2_results_*.json")
    if limit > 0:
        files = heapq.nlargest(limit, glob.iglob(pattern))
    else:
        files = sorted(glob.glob(pattern), reverse=True)

    signature_parts: list[tuple[str, int, int]] = []
    for filepath in files:
        signature = file_signature(filepath)
        if signature is None:
            continue
        signature_parts.append((filepath, int(signature[0]), int(signature[1])))
    return tuple(signature_parts)


def build_backtest_summary_cache_signature(
    *,
    get_data_path: Callable[[str], str] | None = None,
    data_dir_getter: Callable[[], str] | None = None,
    history_limit: int = 30,
) -> tuple[Any, ...] | None:
    data_dir = _resolve_data_dir(
        get_data_path=get_data_path,
        data_dir_getter=data_dir_getter,
    )
    if data_dir is None and get_data_path is None:
        return None

    if get_data_path is not None:
        daily_prices_path = get_data_path("daily_prices.csv")
        signals_path = get_data_path("signals_log.csv")
        latest_jongga_path = get_data_path("jongga_v2_latest.json")
    elif data_dir:
        daily_prices_path = os.path.join(data_dir, "daily_prices.csv")
        signals_path = os.path.join(data_dir, "signals_log.csv")
        latest_jongga_path = os.path.join(data_dir, "jongga_v2_latest.json")
    else:
        daily_prices_path = ""
        signals_path = ""
        latest_jongga_path = ""

    jongga_results_signature = _build_recent_jongga_results_signature(
        data_dir=data_dir,
        limit=history_limit,
    )

    return (
        ("data_dir", str(data_dir or "")),
        ("daily_prices", _safe_file_signature(daily_prices_path)),
        ("signals_log", _safe_file_signature(signals_path)),
        ("jongga_v2_latest", _safe_file_signature(latest_jongga_path)),
        ("jongga_results", jongga_results_signature),
    )


def _ensure_backtest_summary_sqlite(logger: Any) -> bool:
    db_path = _BACKTEST_SUMMARY_CACHE_DB_PATH
    if db_path in _BACKTEST_SUMMARY_SQLITE_READY:
        return True

    with _BACKTEST_SUMMARY_SQLITE_LOCK:
        if db_path in _BACKTEST_SUMMARY_SQLITE_READY:
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
                    CREATE TABLE IF NOT EXISTS backtest_summary_cache (
                        cache_hash TEXT PRIMARY KEY,
                        cache_key_json TEXT NOT NULL,
                        payload_json TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    )
                    """
                )
                cursor.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_backtest_summary_cache_updated_at
                    ON backtest_summary_cache(updated_at DESC)
                    """
                )
                conn.commit()
            _BACKTEST_SUMMARY_SQLITE_READY.add(db_path)
            return True
        except Exception as error:
            logger.debug(f"Failed to initialize backtest summary sqlite cache: {error}")
            return False


def _load_backtest_summary_from_sqlite(
    *,
    signature: tuple[Any, ...],
    logger: Any,
) -> dict[str, Any] | None:
    if not _ensure_backtest_summary_sqlite(logger):
        return None

    cache_hash, signature_json = _cache_hash(signature)
    try:
        with connect_sqlite(
            _BACKTEST_SUMMARY_CACHE_DB_PATH,
            timeout_seconds=5,
            pragmas=("PRAGMA busy_timeout=5000",),
        ) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT cache_key_json, payload_json
                FROM backtest_summary_cache
                WHERE cache_hash = ?
                """,
                (cache_hash,),
            )
            row = cursor.fetchone()
        if row is None:
            return None
        cached_key_json, payload_json = row
        if cached_key_json != signature_json:
            return None
        payload = json.loads(payload_json)
        return payload if isinstance(payload, dict) else None
    except Exception as error:
        logger.debug(f"Failed to load backtest summary sqlite cache: {error}")
        return None


def _save_backtest_summary_to_sqlite(
    *,
    signature: tuple[Any, ...],
    payload: dict[str, Any],
    logger: Any,
) -> None:
    if not _ensure_backtest_summary_sqlite(logger):
        return

    cache_hash, signature_json = _cache_hash(signature)
    try:
        payload_json = json.dumps(payload, ensure_ascii=False, cls=NumpyEncoder)
        with connect_sqlite(
            _BACKTEST_SUMMARY_CACHE_DB_PATH,
            timeout_seconds=5,
            pragmas=("PRAGMA busy_timeout=5000",),
        ) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO backtest_summary_cache (cache_hash, cache_key_json, payload_json, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(cache_hash) DO UPDATE SET
                    cache_key_json = excluded.cache_key_json,
                    payload_json = excluded.payload_json,
                    updated_at = excluded.updated_at
                """,
                (
                    cache_hash,
                    signature_json,
                    payload_json,
                    datetime.now().isoformat(),
                ),
            )
            cursor.execute(
                """
                DELETE FROM backtest_summary_cache
                WHERE cache_hash NOT IN (
                    SELECT cache_hash
                    FROM backtest_summary_cache
                    ORDER BY updated_at DESC
                    LIMIT ?
                )
                """,
                (_BACKTEST_SUMMARY_SQLITE_MAX_ROWS,),
            )
            conn.commit()
    except Exception as error:
        logger.debug(f"Failed to save backtest summary sqlite cache: {error}")


def get_cached_backtest_summary(
    *,
    signature: tuple[Any, ...] | None,
    logger: Any,
) -> dict[str, Any] | None:
    if signature is None:
        return None

    with _BACKTEST_SUMMARY_CACHE_LOCK:
        cached = _BACKTEST_SUMMARY_CACHE.get(signature)
        if cached is not None:
            return copy.deepcopy(cached)

    sqlite_cached = _load_backtest_summary_from_sqlite(signature=signature, logger=logger)
    if sqlite_cached is None:
        return None

    with _BACKTEST_SUMMARY_CACHE_LOCK:
        _BACKTEST_SUMMARY_CACHE[signature] = copy.deepcopy(sqlite_cached)
    return sqlite_cached


def save_cached_backtest_summary(
    *,
    signature: tuple[Any, ...] | None,
    payload: dict[str, Any],
    logger: Any,
) -> None:
    if signature is None:
        return

    _save_memory_cache_entry(signature, payload)
    _save_backtest_summary_to_sqlite(
        signature=signature,
        payload=payload,
        logger=logger,
    )


__all__ = [
    "build_backtest_summary_cache_signature",
    "clear_backtest_summary_cache",
    "get_cached_backtest_summary",
    "save_cached_backtest_summary",
]
