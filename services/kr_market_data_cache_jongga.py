#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KR Market Data Cache - Jongga result payload loaders
"""

from __future__ import annotations

import hashlib
import glob
import heapq
import json
import os
import threading
from datetime import datetime
from typing import Any

from numpy_json_encoder import NumpyEncoder
from services.kr_market_data_cache_core import (
    FILE_CACHE_LOCK,
    JONGGA_RESULT_PAYLOADS_CACHE,
    _load_json_payload_from_path,
    file_signature,
)
from services.sqlite_utils import connect_sqlite


_JONGGA_PAYLOAD_SQLITE_LOCK = threading.Lock()
_JONGGA_PAYLOAD_SQLITE_READY: set[str] = set()
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_JONGGA_PAYLOAD_SQLITE_DB_PATH = os.path.join(_BASE_DIR, "data", "runtime_cache.db")
_JONGGA_PAYLOAD_SQLITE_MAX_ROWS = 64


def _collect_jongga_result_files(data_dir: str, *, limit: int = 0) -> list[str]:
    pattern = os.path.join(data_dir, "jongga_v2_results_*.json")
    if limit > 0:
        # 파일명 끝의 YYYYMMDD 정렬 특성을 이용해 상위 N개만 선택한다.
        return heapq.nlargest(limit, glob.iglob(pattern))
    return sorted(glob.glob(pattern), reverse=True)


def _build_jongga_results_signature(files: list[str]) -> tuple[Any, ...]:
    signature_parts: list[Any] = []
    for filepath in files:
        signature = file_signature(filepath)
        if signature is None:
            continue
        signature_parts.append((filepath, signature[0], signature[1]))
    return tuple(signature_parts)


def _serialize_signature(signature: tuple[Any, ...]) -> str:
    return json.dumps(signature, ensure_ascii=False, separators=(",", ":"))


def _signature_hash(signature: tuple[Any, ...]) -> tuple[str, str]:
    signature_json = _serialize_signature(signature)
    digest = hashlib.sha256(signature_json.encode("utf-8")).hexdigest()
    return digest, signature_json


def _ensure_jongga_payload_sqlite(logger: Any | None) -> bool:
    db_path = _JONGGA_PAYLOAD_SQLITE_DB_PATH
    if db_path in _JONGGA_PAYLOAD_SQLITE_READY:
        return True

    with _JONGGA_PAYLOAD_SQLITE_LOCK:
        if db_path in _JONGGA_PAYLOAD_SQLITE_READY:
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
                    CREATE TABLE IF NOT EXISTS jongga_results_payload_cache (
                        cache_hash TEXT PRIMARY KEY,
                        cache_key_json TEXT NOT NULL,
                        payload_json TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    )
                    """
                )
                cursor.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_jongga_results_payload_cache_updated_at
                    ON jongga_results_payload_cache(updated_at DESC)
                    """
                )
                conn.commit()
            _JONGGA_PAYLOAD_SQLITE_READY.add(db_path)
            return True
        except Exception as error:
            if logger is not None:
                logger.debug(f"Failed to initialize jongga payload sqlite cache: {error}")
            return False


def _normalize_payload_rows(rows: Any) -> list[tuple[str, dict[str, Any]]]:
    if not isinstance(rows, list):
        return []
    normalized: list[tuple[str, dict[str, Any]]] = []
    for row in rows:
        if not isinstance(row, list) or len(row) != 2:
            continue
        filepath, payload = row
        if not isinstance(filepath, str) or not isinstance(payload, dict):
            continue
        normalized.append((filepath, payload))
    return normalized


def _load_payloads_from_sqlite(
    *,
    signature: tuple[Any, ...],
    logger: Any | None,
) -> list[tuple[str, dict[str, Any]]] | None:
    if not _ensure_jongga_payload_sqlite(logger):
        return None

    cache_hash, signature_json = _signature_hash(signature)
    try:
        with connect_sqlite(
            _JONGGA_PAYLOAD_SQLITE_DB_PATH,
            timeout_seconds=5,
            pragmas=("PRAGMA busy_timeout=5000",),
        ) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT cache_key_json, payload_json
                FROM jongga_results_payload_cache
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
        rows = json.loads(payload_json)
        if isinstance(rows, list) and not rows:
            return []
        normalized = _normalize_payload_rows(rows)
        if not normalized:
            return None
        return normalized
    except Exception as error:
        if logger is not None:
            logger.debug(f"Failed to load jongga payload sqlite cache: {error}")
        return None


def _save_payloads_to_sqlite(
    *,
    signature: tuple[Any, ...],
    payloads: list[tuple[str, dict[str, Any]]],
    logger: Any | None,
) -> None:
    if not _ensure_jongga_payload_sqlite(logger):
        return

    cache_hash, signature_json = _signature_hash(signature)
    try:
        payload_json = json.dumps(payloads, ensure_ascii=False, cls=NumpyEncoder)
        with connect_sqlite(
            _JONGGA_PAYLOAD_SQLITE_DB_PATH,
            timeout_seconds=5,
            pragmas=("PRAGMA busy_timeout=5000",),
        ) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO jongga_results_payload_cache (cache_hash, cache_key_json, payload_json, updated_at)
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
                DELETE FROM jongga_results_payload_cache
                WHERE cache_hash NOT IN (
                    SELECT cache_hash
                    FROM jongga_results_payload_cache
                    ORDER BY updated_at DESC
                    LIMIT ?
                )
                """,
                (_JONGGA_PAYLOAD_SQLITE_MAX_ROWS,),
            )
            conn.commit()
    except Exception as error:
        if logger is not None:
            logger.debug(f"Failed to save jongga payload sqlite cache: {error}")


def load_jongga_result_payloads(
    data_dir: str,
    *,
    limit: int = 0,
    logger: Any | None = None,
) -> list[tuple[str, dict[str, Any]]]:
    """
    jongga_v2_results 파일들을 최신순으로 캐시 로드한다.
    반환값: [(filepath, payload), ...]
    """
    files = _collect_jongga_result_files(data_dir, limit=limit)
    signature = _build_jongga_results_signature(files)
    signature_map: dict[str, tuple[int, int]] = {
        filepath: (mtime_ns, size)
        for filepath, mtime_ns, size in signature
    }

    with FILE_CACHE_LOCK:
        cached_signature = JONGGA_RESULT_PAYLOADS_CACHE.get("signature")
        cached_payloads = JONGGA_RESULT_PAYLOADS_CACHE.get("payloads", [])
        if cached_signature == signature and isinstance(cached_payloads, list):
            payloads = cached_payloads
        else:
            payloads = None

    if payloads is None:
        sqlite_payloads = _load_payloads_from_sqlite(signature=signature, logger=logger)
        if sqlite_payloads is not None:
            with FILE_CACHE_LOCK:
                JONGGA_RESULT_PAYLOADS_CACHE["signature"] = signature
                JONGGA_RESULT_PAYLOADS_CACHE["payloads"] = sqlite_payloads
            payloads = sqlite_payloads

    if payloads is None:
        loaded_payloads: list[tuple[str, dict[str, Any]]] = []
        for filepath in files:
            try:
                payload = _load_json_payload_from_path(
                    filepath,
                    signature=signature_map.get(filepath),
                )
                if isinstance(payload, dict):
                    loaded_payloads.append((filepath, payload))
            except Exception as e:
                if logger is not None:
                    logger.error(f"Error processing file {filepath}: {e}")

        with FILE_CACHE_LOCK:
            JONGGA_RESULT_PAYLOADS_CACHE["signature"] = signature
            JONGGA_RESULT_PAYLOADS_CACHE["payloads"] = loaded_payloads
        _save_payloads_to_sqlite(
            signature=signature,
            payloads=loaded_payloads,
            logger=logger,
        )
        payloads = loaded_payloads

    if limit > 0:
        return list(payloads[:limit])
    return list(payloads)
