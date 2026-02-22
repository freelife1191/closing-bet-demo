#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KR AI 종목정보 캐시(SQLite + 메모리).
"""

from __future__ import annotations

import copy
import json
import os
import threading
from collections import OrderedDict
from datetime import datetime
from typing import Any, Callable

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


_STOCK_INFO_CACHE_LOCK = threading.Lock()
_STOCK_INFO_CACHE: OrderedDict[str, tuple[tuple[int, int], dict[str, object]]] = OrderedDict()
_STOCK_INFO_MEMORY_MAX_ENTRIES = 4_096
_STOCK_INFO_SQLITE_READY_LOCK = threading.Lock()
_STOCK_INFO_SQLITE_READY_CONDITION = threading.Condition(_STOCK_INFO_SQLITE_READY_LOCK)
_STOCK_INFO_SQLITE_INIT_IN_PROGRESS: set[str] = set()
_STOCK_INFO_SQLITE_READY: set[str] = set()
_STOCK_INFO_SQLITE_READY_MAX_ENTRIES = 2_048
_STOCK_INFO_SQLITE_KNOWN_KEYS: OrderedDict[tuple[str, str], None] = OrderedDict()
_STOCK_INFO_SQLITE_KNOWN_KEYS_LOCK = threading.Lock()
_STOCK_INFO_SQLITE_KNOWN_KEYS_MAX_ENTRIES = 8_192
_STOCK_INFO_SQLITE_MAX_ROWS = 512
_STOCK_INFO_SQLITE_PRUNE_FORCE_INTERVAL = 64
_STOCK_INFO_SQLITE_SAVE_COUNTER = 0
_STOCK_INFO_SQLITE_SAVE_COUNTER_LOCK = threading.Lock()
_STOCK_INFO_SQLITE_INIT_PRAGMAS = build_sqlite_pragmas(busy_timeout_ms=30_000)
_STOCK_INFO_SQLITE_SESSION_PRAGMAS = build_sqlite_pragmas(
    busy_timeout_ms=30_000,
    base_pragmas=("PRAGMA temp_store=MEMORY", "PRAGMA cache_size=-4000"),
)
_STOCK_INFO_SQLITE_RETRY_ATTEMPTS = 2
_STOCK_INFO_SQLITE_RETRY_DELAY_SECONDS = 0.03


def _get_stock_info_memory_cache(
    cache_key: str,
) -> tuple[tuple[int, int], dict[str, object]] | None:
    cached = _STOCK_INFO_CACHE.get(cache_key)
    if cached is None:
        return None
    _STOCK_INFO_CACHE.move_to_end(cache_key)
    return cached


def _set_stock_info_memory_cache(
    cache_key: str,
    cache_value: tuple[tuple[int, int], dict[str, object]],
) -> None:
    _STOCK_INFO_CACHE[cache_key] = cache_value
    _STOCK_INFO_CACHE.move_to_end(cache_key)
    normalized_max_entries = max(1, int(_STOCK_INFO_MEMORY_MAX_ENTRIES))
    while len(_STOCK_INFO_CACHE) > normalized_max_entries:
        _STOCK_INFO_CACHE.popitem(last=False)


def _normalize_signals_path(path: str) -> str:
    return normalize_sqlite_db_key(path)


def _signals_path_lookup_keys(path: str) -> tuple[str, ...]:
    normalized_path = _normalize_signals_path(path)
    raw_path = str(path)
    keys: list[str] = [normalized_path]
    if raw_path not in keys:
        keys.append(raw_path)

    try:
        relative_path = os.path.relpath(normalized_path, os.getcwd())
        if relative_path not in keys:
            keys.append(relative_path)
    except Exception:
        pass
    return tuple(keys)


def _stock_info_cache_key(signals_file: str, ticker: str) -> str:
    normalized_signals_path = _normalize_signals_path(signals_file)
    return f"{normalized_signals_path}::{str(ticker)}"


def resolve_stock_info_cache_db_path(signals_file: str) -> str:
    normalized_signals_path = _normalize_signals_path(signals_file)
    return os.path.join(os.path.dirname(normalized_signals_path), "runtime_cache.db")


def _invalidate_stock_info_sqlite_ready(db_path: str) -> None:
    db_key = normalize_sqlite_db_key(db_path)
    with _STOCK_INFO_SQLITE_READY_LOCK:
        _STOCK_INFO_SQLITE_READY.discard(db_key)
    with _STOCK_INFO_SQLITE_KNOWN_KEYS_LOCK:
        stale_keys = [key for key in _STOCK_INFO_SQLITE_KNOWN_KEYS if key[0] == db_key]
        for tracker_key in stale_keys:
            _STOCK_INFO_SQLITE_KNOWN_KEYS.pop(tracker_key, None)


def _is_missing_table_error(error: Exception) -> bool:
    return is_sqlite_missing_table_error(error, table_names="kr_ai_stock_info_cache")


def _recover_stock_info_sqlite_schema(db_path: str, logger: Any) -> bool:
    _invalidate_stock_info_sqlite_ready(db_path)
    return _ensure_stock_info_sqlite(db_path, logger)


def _mark_stock_info_sqlite_snapshot_key_seen(*, db_path: str, snapshot_key: str) -> bool:
    """
    (db_path, snapshot_key) 조합을 추적한다.
    return True면 신규 key로 간주해 prune을 수행한다.
    """
    db_key = normalize_sqlite_db_key(db_path)
    tracker_key = (db_key, str(snapshot_key))
    with _STOCK_INFO_SQLITE_KNOWN_KEYS_LOCK:
        if tracker_key in _STOCK_INFO_SQLITE_KNOWN_KEYS:
            _STOCK_INFO_SQLITE_KNOWN_KEYS.move_to_end(tracker_key)
            return False

        _STOCK_INFO_SQLITE_KNOWN_KEYS[tracker_key] = None
        _STOCK_INFO_SQLITE_KNOWN_KEYS.move_to_end(tracker_key)
        normalized_max_entries = max(1, int(_STOCK_INFO_SQLITE_KNOWN_KEYS_MAX_ENTRIES))
        while len(_STOCK_INFO_SQLITE_KNOWN_KEYS) > normalized_max_entries:
            _STOCK_INFO_SQLITE_KNOWN_KEYS.popitem(last=False)
        return True


def _should_force_stock_info_sqlite_prune() -> bool:
    global _STOCK_INFO_SQLITE_SAVE_COUNTER
    with _STOCK_INFO_SQLITE_SAVE_COUNTER_LOCK:
        _STOCK_INFO_SQLITE_SAVE_COUNTER += 1
        normalized_interval = max(1, int(_STOCK_INFO_SQLITE_PRUNE_FORCE_INTERVAL))
        return (_STOCK_INFO_SQLITE_SAVE_COUNTER % normalized_interval) == 0


def _ensure_stock_info_sqlite(db_path: str, logger: Any) -> bool:
    db_key = normalize_sqlite_db_key(db_path)
    with _STOCK_INFO_SQLITE_READY_CONDITION:
        if db_key in _STOCK_INFO_SQLITE_READY:
            if sqlite_db_path_exists(db_path):
                return True
            _STOCK_INFO_SQLITE_READY.discard(db_key)

        while db_key in _STOCK_INFO_SQLITE_INIT_IN_PROGRESS:
            _STOCK_INFO_SQLITE_READY_CONDITION.wait()
            if db_key in _STOCK_INFO_SQLITE_READY:
                if sqlite_db_path_exists(db_path):
                    return True
                _STOCK_INFO_SQLITE_READY.discard(db_key)

        _STOCK_INFO_SQLITE_INIT_IN_PROGRESS.add(db_key)

    def _initialize_schema() -> None:
        with connect_sqlite(
            db_path,
            timeout_seconds=30,
            pragmas=_STOCK_INFO_SQLITE_INIT_PRAGMAS,
        ) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS kr_ai_stock_info_cache (
                    signals_path TEXT NOT NULL,
                    ticker TEXT NOT NULL,
                    mtime_ns INTEGER NOT NULL,
                    size INTEGER NOT NULL,
                    payload_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (signals_path, ticker)
                )
                """
            )
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_kr_ai_stock_info_cache_updated_at
                ON kr_ai_stock_info_cache(updated_at DESC)
                """
            )
            conn.commit()

    initialization_succeeded = False
    try:
        run_sqlite_with_retry(
            _initialize_schema,
            max_retries=_STOCK_INFO_SQLITE_RETRY_ATTEMPTS,
            retry_delay_seconds=_STOCK_INFO_SQLITE_RETRY_DELAY_SECONDS,
        )
        initialization_succeeded = True
        return True
    except Exception as error:
        logger.debug("Failed to initialize KR AI stock info sqlite cache: %s", error)
        return False
    finally:
        with _STOCK_INFO_SQLITE_READY_CONDITION:
            _STOCK_INFO_SQLITE_INIT_IN_PROGRESS.discard(db_key)
            if initialization_succeeded:
                add_bounded_ready_key(
                    _STOCK_INFO_SQLITE_READY,
                    db_key,
                    max_entries=_STOCK_INFO_SQLITE_READY_MAX_ENTRIES,
                )
            else:
                _STOCK_INFO_SQLITE_READY.discard(db_key)
            _STOCK_INFO_SQLITE_READY_CONDITION.notify_all()


def _load_stock_info_from_sqlite(
    *,
    signals_file: str,
    ticker: str,
    signature: tuple[int, int],
    logger: Any,
    resolve_db_path_fn: Callable[[str], str],
) -> dict[str, object] | None:
    lookup_keys = _signals_path_lookup_keys(signals_file)
    lookup_placeholders = build_sqlite_in_placeholders(lookup_keys)
    order_case_sql = build_sqlite_order_case_sql(
        column_name="signals_path",
        lookup_keys=lookup_keys,
    )
    normalized_signals_path = lookup_keys[0]
    db_path = resolve_db_path_fn(normalized_signals_path)
    if not _ensure_stock_info_sqlite(db_path, logger):
        return None
    normalized_ticker = str(ticker)
    query_params = (
        *lookup_keys,
        normalized_ticker,
        int(signature[0]),
        int(signature[1]),
        *lookup_keys,
    )

    def _query_payload() -> tuple[Any, ...] | None:
        with connect_sqlite(
            db_path,
            timeout_seconds=30,
            pragmas=_STOCK_INFO_SQLITE_SESSION_PRAGMAS,
            read_only=True,
        ) as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"""
                SELECT payload_json
                FROM kr_ai_stock_info_cache
                WHERE signals_path IN ({lookup_placeholders})
                  AND ticker = ?
                  AND mtime_ns = ?
                  AND size = ?
                ORDER BY {order_case_sql}
                LIMIT 1
                """,
                query_params,
            )
            return cursor.fetchone()

    try:
        row = run_sqlite_with_retry(
            _query_payload,
            max_retries=_STOCK_INFO_SQLITE_RETRY_ATTEMPTS,
            retry_delay_seconds=_STOCK_INFO_SQLITE_RETRY_DELAY_SECONDS,
        )
    except Exception as error:
        if _is_missing_table_error(error) and _recover_stock_info_sqlite_schema(db_path, logger):
            try:
                row = run_sqlite_with_retry(
                    _query_payload,
                    max_retries=_STOCK_INFO_SQLITE_RETRY_ATTEMPTS,
                    retry_delay_seconds=_STOCK_INFO_SQLITE_RETRY_DELAY_SECONDS,
                )
            except Exception as retry_error:
                logger.debug("Failed to load KR AI stock info sqlite cache after schema recovery: %s", retry_error)
                return None
        else:
            logger.debug("Failed to load KR AI stock info sqlite cache: %s", error)
            return None

    try:
        if not row:
            return None
        payload = json.loads(row[0])
        return payload if isinstance(payload, dict) else None
    except Exception as error:
        logger.debug("Failed to load KR AI stock info sqlite cache: %s", error)
        return None


def _save_stock_info_to_sqlite(
    *,
    signals_file: str,
    ticker: str,
    signature: tuple[int, int],
    payload: dict[str, object],
    logger: Any,
    resolve_db_path_fn: Callable[[str], str],
) -> None:
    normalized_signals_path = _normalize_signals_path(signals_file)
    db_path = resolve_db_path_fn(normalized_signals_path)
    if not _ensure_stock_info_sqlite(db_path, logger):
        return
    normalized_ticker = str(ticker)

    try:
        payload_json = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    except Exception as error:
        logger.debug("Failed to serialize KR AI stock info cache: %s", error)
        return

    normalized_max_rows = max(1, int(_STOCK_INFO_SQLITE_MAX_ROWS))
    snapshot_key = f"{normalized_signals_path}::{normalized_ticker}"
    should_prune_for_new_key = _mark_stock_info_sqlite_snapshot_key_seen(
        db_path=db_path,
        snapshot_key=snapshot_key,
    )
    should_force_prune = _should_force_stock_info_sqlite_prune()
    should_prune_after_upsert = should_prune_for_new_key or should_force_prune

    def _upsert_payload() -> None:
        with connect_sqlite(
            db_path,
            timeout_seconds=30,
            pragmas=_STOCK_INFO_SQLITE_SESSION_PRAGMAS,
        ) as conn:
            now_iso = datetime.now().isoformat()
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO kr_ai_stock_info_cache (
                    signals_path,
                    ticker,
                    mtime_ns,
                    size,
                    payload_json,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(signals_path, ticker) DO UPDATE SET
                    mtime_ns = excluded.mtime_ns,
                    size = excluded.size,
                    payload_json = excluded.payload_json,
                    updated_at = excluded.updated_at
                """,
                (
                    normalized_signals_path,
                    normalized_ticker,
                    int(signature[0]),
                    int(signature[1]),
                    payload_json,
                    now_iso,
                ),
            )
            if should_prune_after_upsert:
                prune_rows_by_updated_at_if_needed(
                    cursor,
                    table_name="kr_ai_stock_info_cache",
                    max_rows=normalized_max_rows,
                )
            conn.commit()

    try:
        run_sqlite_with_retry(
            _upsert_payload,
            max_retries=_STOCK_INFO_SQLITE_RETRY_ATTEMPTS,
            retry_delay_seconds=_STOCK_INFO_SQLITE_RETRY_DELAY_SECONDS,
        )
    except Exception as error:
        if _is_missing_table_error(error) and _recover_stock_info_sqlite_schema(db_path, logger):
            try:
                run_sqlite_with_retry(
                    _upsert_payload,
                    max_retries=_STOCK_INFO_SQLITE_RETRY_ATTEMPTS,
                    retry_delay_seconds=_STOCK_INFO_SQLITE_RETRY_DELAY_SECONDS,
                )
            except Exception as retry_error:
                logger.debug("Failed to save KR AI stock info sqlite cache after schema recovery: %s", retry_error)
        else:
            logger.debug("Failed to save KR AI stock info sqlite cache: %s", error)


def load_cached_stock_info(
    *,
    signals_file: str,
    ticker: str,
    signature: tuple[int, int],
    logger: Any,
    resolve_db_path_fn: Callable[[str], str] = resolve_stock_info_cache_db_path,
) -> dict[str, object] | None:
    cache_key = _stock_info_cache_key(signals_file, ticker)
    with _STOCK_INFO_CACHE_LOCK:
        cached = _get_stock_info_memory_cache(cache_key)
        if cached and cached[0] == signature:
            return copy.deepcopy(cached[1])

    sqlite_cached = _load_stock_info_from_sqlite(
        signals_file=signals_file,
        ticker=ticker,
        signature=signature,
        logger=logger,
        resolve_db_path_fn=resolve_db_path_fn,
    )
    if sqlite_cached is None:
        return None

    with _STOCK_INFO_CACHE_LOCK:
        _set_stock_info_memory_cache(
            cache_key,
            (signature, dict(sqlite_cached)),
        )
    return copy.deepcopy(sqlite_cached)


def save_cached_stock_info(
    *,
    signals_file: str,
    ticker: str,
    signature: tuple[int, int],
    payload: dict[str, object],
    logger: Any,
    resolve_db_path_fn: Callable[[str], str] = resolve_stock_info_cache_db_path,
) -> None:
    cache_key = _stock_info_cache_key(signals_file, ticker)
    with _STOCK_INFO_CACHE_LOCK:
        _set_stock_info_memory_cache(
            cache_key,
            (signature, dict(payload)),
        )

    _save_stock_info_to_sqlite(
        signals_file=signals_file,
        ticker=ticker,
        signature=signature,
        payload=payload,
        logger=logger,
        resolve_db_path_fn=resolve_db_path_fn,
    )


def clear_stock_info_cache() -> None:
    with _STOCK_INFO_CACHE_LOCK:
        _STOCK_INFO_CACHE.clear()
    with _STOCK_INFO_SQLITE_KNOWN_KEYS_LOCK:
        _STOCK_INFO_SQLITE_KNOWN_KEYS.clear()
    global _STOCK_INFO_SQLITE_SAVE_COUNTER
    with _STOCK_INFO_SQLITE_SAVE_COUNTER_LOCK:
        _STOCK_INFO_SQLITE_SAVE_COUNTER = 0
