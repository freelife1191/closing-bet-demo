#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
stock_context 결과 문자열 캐시(SQLite + 메모리).

2단 캐시의 공통 골격은 services/sqlite_ready_gate.py 에 있다. 이 모듈에는
chatbot_stock_context_cache 테이블의 SQL 과 합성 캐시 키 계산만 남는다.
"""

from __future__ import annotations

import logging
import os
from collections import OrderedDict
from datetime import datetime
from pathlib import Path
from threading import Lock

from services.sqlite_ready_gate import (
    SeenKeyTracker,
    SqliteReadyGate,
    run_with_schema_recovery,
    save_bounded_lru_entry,
)
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


LOGGER = logging.getLogger(__name__)

_RESULT_TEXT_CACHE_LOCK = Lock()
_RESULT_TEXT_CACHE: OrderedDict[str, tuple[tuple[int, int], str]] = OrderedDict()
_RESULT_TEXT_MEMORY_MAX_ENTRIES = 2048
_RESULT_TEXT_SQLITE_MAX_ROWS = 1024
_RESULT_TEXT_SQLITE_PRUNE_FORCE_INTERVAL = 64
_RESULT_TEXT_SQLITE_TIMEOUT_SECONDS = 30
_RESULT_TEXT_SQLITE_RETRY_ATTEMPTS = 2
_RESULT_TEXT_SQLITE_RETRY_DELAY_SECONDS = 0.03
_RESULT_TEXT_SQLITE_READY_MAX_ENTRIES = 2_048
_RESULT_TEXT_SQLITE_KNOWN_KEYS_MAX_ENTRIES = 8_192

_RESULT_TEXT_READY_GATE = SqliteReadyGate(
    max_ready_entries=_RESULT_TEXT_SQLITE_READY_MAX_ENTRIES,
)
_RESULT_TEXT_SEEN_TRACKER = SeenKeyTracker(
    max_entries=_RESULT_TEXT_SQLITE_KNOWN_KEYS_MAX_ENTRIES,
)

# 회귀 테스트가 모듈 전역으로 이 셋을 직접 조작한다. 게이트가 가진 객체를 그대로
# 가리키는 별칭이므로 테스트가 clear() 를 부르면 게이트도 함께 비워진다.
# 반대로 재바인딩은 닿지 않는다. monkeypatch.setattr 로 _RESULT_TEXT_SQLITE_READY 에 새 집합을
# 넣으면 이 이름만 갈리고 _RESULT_TEXT_READY_GATE 는 옛 집합을 계속 쓴다. 상태를
# 갈아 끼워야 하면 게이트를 새로 만들어야 한다.
_RESULT_TEXT_SQLITE_READY_CONDITION = _RESULT_TEXT_READY_GATE.condition
_RESULT_TEXT_SQLITE_READY = _RESULT_TEXT_READY_GATE.ready_keys
_RESULT_TEXT_SQLITE_INIT_IN_PROGRESS = _RESULT_TEXT_READY_GATE.in_progress_keys

_RESULT_TEXT_SQLITE_INIT_PRAGMAS = build_sqlite_pragmas(
    busy_timeout_ms=_RESULT_TEXT_SQLITE_TIMEOUT_SECONDS * 1000,
)
_RESULT_TEXT_SQLITE_SESSION_PRAGMAS = build_sqlite_pragmas(
    busy_timeout_ms=_RESULT_TEXT_SQLITE_TIMEOUT_SECONDS * 1000,
    base_pragmas=("PRAGMA temp_store=MEMORY", "PRAGMA cache_size=-4000"),
)


def _build_result_cache_key(path: Path, *, dataset: str, ticker_padded: str) -> str:
    normalized_path = _normalize_result_cache_path(path)
    return f"{normalized_path}::{dataset}::{ticker_padded}"


def _normalize_result_cache_path(path: Path | str) -> str:
    return normalize_sqlite_db_key(str(path))


def _build_result_cache_lookup_keys(path: Path, *, dataset: str, ticker_padded: str) -> tuple[str, ...]:
    normalized_path = _normalize_result_cache_path(path)
    resolved_path = str(path.resolve())
    raw_path = str(path)
    path_keys: list[str] = [normalized_path]
    for candidate in (resolved_path, raw_path):
        if candidate not in path_keys:
            path_keys.append(candidate)
    try:
        relative_path = os.path.relpath(normalized_path, os.getcwd())
        if relative_path not in path_keys:
            path_keys.append(relative_path)
    except Exception:
        pass
    return tuple(f"{path_key}::{dataset}::{ticker_padded}" for path_key in path_keys)


def _resolve_runtime_cache_db_path(data_dir: Path) -> Path:
    normalized_data_dir = Path(normalize_sqlite_db_key(str(data_dir)))
    return normalized_data_dir / "runtime_cache.db"


def _invalidate_result_text_sqlite_ready(db_path: Path) -> None:
    db_path_text = str(db_path)
    _RESULT_TEXT_READY_GATE.invalidate(db_path_text)
    _RESULT_TEXT_SEEN_TRACKER.discard_db(db_path_text)


def _is_missing_table_error(error: Exception) -> bool:
    return is_sqlite_missing_table_error(error, table_names="chatbot_stock_context_cache")


def _recover_result_text_sqlite_schema(db_path: Path) -> bool:
    _invalidate_result_text_sqlite_ready(db_path)
    return _ensure_result_text_sqlite_cache(db_path)


def _create_result_text_schema(db_path_text: str) -> None:
    with connect_sqlite(
        db_path_text,
        timeout_seconds=_RESULT_TEXT_SQLITE_TIMEOUT_SECONDS,
        pragmas=_RESULT_TEXT_SQLITE_INIT_PRAGMAS,
    ) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS chatbot_stock_context_cache (
                cache_key TEXT PRIMARY KEY,
                dataset TEXT NOT NULL,
                ticker TEXT NOT NULL,
                mtime_ns INTEGER NOT NULL,
                size INTEGER NOT NULL,
                payload_text TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_chatbot_stock_context_cache_updated_at
            ON chatbot_stock_context_cache(updated_at DESC)
            """
        )
        conn.commit()


def _ensure_result_text_sqlite_cache(db_path: Path) -> bool:
    db_path_text = str(db_path)
    return _RESULT_TEXT_READY_GATE.ensure(
        db_path_text,
        initialize=lambda: _create_result_text_schema(db_path_text),
        db_path_exists=sqlite_db_path_exists,
        run_with_retry=run_sqlite_with_retry,
        retry_attempts=_RESULT_TEXT_SQLITE_RETRY_ATTEMPTS,
        retry_delay_seconds=_RESULT_TEXT_SQLITE_RETRY_DELAY_SECONDS,
        on_failure=lambda error: LOGGER.debug(
            "Failed to initialize stock context sqlite cache (%s): %s", db_path, error
        ),
    )


def _save_result_text_memory_entry(cache_key: str, signature: tuple[int, int], payload_text: str) -> None:
    with _RESULT_TEXT_CACHE_LOCK:
        save_bounded_lru_entry(
            _RESULT_TEXT_CACHE,
            cache_key,
            (signature, payload_text),
            max_entries=_RESULT_TEXT_MEMORY_MAX_ENTRIES,
        )


def _load_result_text_from_sqlite(
    *,
    data_dir: Path,
    cache_key: str,
    cache_key_lookup_keys: tuple[str, ...] | None,
    signature: tuple[int, int],
) -> str | None:
    db_path = _resolve_runtime_cache_db_path(data_dir)
    if not _ensure_result_text_sqlite_cache(db_path):
        return None
    db_path_text = str(db_path)
    lookup_keys = tuple(cache_key_lookup_keys or (cache_key,))
    lookup_placeholders = build_sqlite_in_placeholders(lookup_keys)
    order_case_sql = build_sqlite_order_case_sql(
        column_name="cache_key",
        lookup_keys=lookup_keys,
    )
    query_params = (
        *lookup_keys,
        int(signature[0]),
        int(signature[1]),
        *lookup_keys,
    )

    def _query_row() -> tuple[object, ...] | None:
        with connect_sqlite(
            db_path_text,
            timeout_seconds=_RESULT_TEXT_SQLITE_TIMEOUT_SECONDS,
            pragmas=_RESULT_TEXT_SQLITE_SESSION_PRAGMAS,
            read_only=True,
        ) as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"""
                SELECT payload_text
                FROM chatbot_stock_context_cache
                WHERE cache_key IN ({lookup_placeholders})
                  AND mtime_ns = ?
                  AND size = ?
                ORDER BY {order_case_sql}
                LIMIT 1
                """,
                query_params,
            )
            return cursor.fetchone()

    try:
        row = run_with_schema_recovery(
            _query_row,
            run_with_retry=run_sqlite_with_retry,
            retry_attempts=_RESULT_TEXT_SQLITE_RETRY_ATTEMPTS,
            retry_delay_seconds=_RESULT_TEXT_SQLITE_RETRY_DELAY_SECONDS,
            is_missing_table=_is_missing_table_error,
            recover=lambda: _recover_result_text_sqlite_schema(db_path),
        )
    except Exception as exc:
        LOGGER.debug("Failed to load stock context sqlite cache (%s): %s", cache_key, exc)
        return None

    try:
        if not row:
            return None
        payload_text = row[0]
        return payload_text if isinstance(payload_text, str) else None
    except Exception as exc:
        LOGGER.debug("Failed to load stock context sqlite cache (%s): %s", cache_key, exc)
        return None


def _save_result_text_to_sqlite(
    *,
    data_dir: Path,
    cache_key: str,
    dataset: str,
    ticker_padded: str,
    signature: tuple[int, int],
    payload_text: str,
) -> None:
    db_path = _resolve_runtime_cache_db_path(data_dir)
    if not _ensure_result_text_sqlite_cache(db_path):
        return
    db_path_text = str(db_path)

    normalized_max_rows = max(1, int(_RESULT_TEXT_SQLITE_MAX_ROWS))
    # 두 판정을 모두 실행한다. or 로 묶어 단축 평가에 맡기면 신규 키일 때 저장 카운터가
    # 올라가지 않아 강제 프루닝 주기가 어긋난다.
    should_prune_for_new_key = _RESULT_TEXT_SEEN_TRACKER.mark_seen(
        db_path_text=db_path_text,
        item_key=cache_key,
    )
    should_force_prune = _RESULT_TEXT_SEEN_TRACKER.should_force_prune(
        _RESULT_TEXT_SQLITE_PRUNE_FORCE_INTERVAL
    )
    should_prune_after_upsert = should_prune_for_new_key or should_force_prune

    def _upsert_payload_text() -> None:
        with connect_sqlite(
            db_path_text,
            timeout_seconds=_RESULT_TEXT_SQLITE_TIMEOUT_SECONDS,
            pragmas=_RESULT_TEXT_SQLITE_SESSION_PRAGMAS,
        ) as conn:
            now_iso = datetime.now().isoformat()
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO chatbot_stock_context_cache (
                    cache_key,
                    dataset,
                    ticker,
                    mtime_ns,
                    size,
                    payload_text,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(cache_key) DO UPDATE SET
                    dataset = excluded.dataset,
                    ticker = excluded.ticker,
                    mtime_ns = excluded.mtime_ns,
                    size = excluded.size,
                    payload_text = excluded.payload_text,
                    updated_at = excluded.updated_at
                """,
                (
                    cache_key,
                    dataset,
                    ticker_padded,
                    int(signature[0]),
                    int(signature[1]),
                    payload_text,
                    now_iso,
                ),
            )
            if should_prune_after_upsert:
                prune_rows_by_updated_at_if_needed(
                    cursor,
                    table_name="chatbot_stock_context_cache",
                    max_rows=normalized_max_rows,
                )
            conn.commit()

    try:
        run_with_schema_recovery(
            _upsert_payload_text,
            run_with_retry=run_sqlite_with_retry,
            retry_attempts=_RESULT_TEXT_SQLITE_RETRY_ATTEMPTS,
            retry_delay_seconds=_RESULT_TEXT_SQLITE_RETRY_DELAY_SECONDS,
            is_missing_table=_is_missing_table_error,
            recover=lambda: _recover_result_text_sqlite_schema(db_path),
        )
    except Exception as exc:
        LOGGER.debug("Failed to save stock context sqlite cache (%s): %s", cache_key, exc)


def load_cached_result_text(
    *,
    data_dir: Path,
    path: Path,
    dataset: str,
    ticker_padded: str,
    signature: tuple[int, int],
) -> str | None:
    cache_key_lookup_keys = _build_result_cache_lookup_keys(path, dataset=dataset, ticker_padded=ticker_padded)
    cache_key = cache_key_lookup_keys[0]
    with _RESULT_TEXT_CACHE_LOCK:
        cached_payload: str | None = None
        matched_key: str | None = None
        stale_keys: list[str] = []
        for lookup_key in cache_key_lookup_keys:
            cached = _RESULT_TEXT_CACHE.get(lookup_key)
            if not cached:
                continue
            if cached[0] == signature:
                _RESULT_TEXT_CACHE.move_to_end(lookup_key)
                cached_payload = cached[1]
                matched_key = lookup_key
                break
            stale_keys.append(lookup_key)

        for stale_key in stale_keys:
            _RESULT_TEXT_CACHE.pop(stale_key, None)

        if cached_payload is not None:
            if matched_key is not None and matched_key != cache_key:
                # 이미 락을 쥐고 있으므로 헬퍼를 그대로 부른다.
                save_bounded_lru_entry(
                    _RESULT_TEXT_CACHE,
                    cache_key,
                    (signature, cached_payload),
                    max_entries=_RESULT_TEXT_MEMORY_MAX_ENTRIES,
                )
            return cached_payload

    sqlite_cached = _load_result_text_from_sqlite(
        data_dir=data_dir,
        cache_key=cache_key,
        cache_key_lookup_keys=cache_key_lookup_keys,
        signature=signature,
    )
    if sqlite_cached is None:
        return None

    _save_result_text_memory_entry(cache_key, signature, sqlite_cached)
    return sqlite_cached


def save_cached_result_text(
    *,
    data_dir: Path,
    path: Path,
    dataset: str,
    ticker_padded: str,
    signature: tuple[int, int],
    payload_text: str,
) -> None:
    cache_key = _build_result_cache_key(path, dataset=dataset, ticker_padded=ticker_padded)
    _save_result_text_memory_entry(cache_key, signature, payload_text)
    _save_result_text_to_sqlite(
        data_dir=data_dir,
        cache_key=cache_key,
        dataset=dataset,
        ticker_padded=ticker_padded,
        signature=signature,
        payload_text=payload_text,
    )


def clear_result_text_cache() -> None:
    with _RESULT_TEXT_CACHE_LOCK:
        _RESULT_TEXT_CACHE.clear()
    _RESULT_TEXT_SEEN_TRACKER.clear()
