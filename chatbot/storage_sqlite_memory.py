#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
챗봇 메모리 SQLite 저장 헬퍼
"""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict

from services.sqlite_utils import (
    connect_sqlite,
    is_sqlite_missing_table_error,
    run_sqlite_with_retry,
)

from .storage_sqlite_common import _SQLITE_SESSION_PRAGMAS, ensure_chatbot_storage_schema

_SQLITE_TIMEOUT_SECONDS = 30
_SQLITE_RETRY_ATTEMPTS = 2
_SQLITE_RETRY_DELAY_SECONDS = 0.03
_DAILY_SUGGESTIONS_PREFIX = "daily_suggestions_"
_DAILY_SUGGESTIONS_CACHE_TTL = timedelta(hours=1)
_DAILY_SUGGESTIONS_CACHE_MAX_ENTRIES = 500


def _is_missing_table_error(error: Exception, *, table_name: str) -> bool:
    return is_sqlite_missing_table_error(error, table_names=table_name)


def _parse_daily_suggestions_updated_at(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except (TypeError, ValueError):
        logging.getLogger(__name__).debug("Invalid daily suggestion cache timestamp")
        return None
    return parsed if parsed.tzinfo is None else None


def _daily_suggestions_keys_to_delete(
    rows: list[tuple[str, object]],
    now: datetime,
) -> list[str]:
    cutoff = now - _DAILY_SUGGESTIONS_CACHE_TTL
    valid_rows: list[tuple[str, datetime]] = []
    keys_to_delete: list[str] = []
    for key, updated_at in rows:
        parsed_updated_at = _parse_daily_suggestions_updated_at(updated_at)
        if (
            parsed_updated_at is None
            or parsed_updated_at <= cutoff
            or parsed_updated_at > now
        ):
            keys_to_delete.append(key)
            continue
        valid_rows.append((key, parsed_updated_at))

    valid_rows.sort(key=lambda row: (row[1], row[0]), reverse=True)
    keys_to_delete.extend(key for key, _ in valid_rows[_DAILY_SUGGESTIONS_CACHE_MAX_ENTRIES:])
    return keys_to_delete


def _prune_daily_suggestions_cursor(cursor: sqlite3.Cursor, now: datetime) -> None:
    rows = cursor.execute(
        """
        SELECT memory_key, updated_at
        FROM chatbot_memories
        WHERE owner_id = ? AND substr(memory_key, 1, ?) = ?
        """,
        ("", len(_DAILY_SUGGESTIONS_PREFIX), _DAILY_SUGGESTIONS_PREFIX),
    ).fetchall()
    keys_to_delete = _daily_suggestions_keys_to_delete(
        [(str(row[0]), row[1]) for row in rows],
        now,
    )
    if keys_to_delete:
        cursor.executemany(
            """
            DELETE FROM chatbot_memories
            WHERE owner_id = ? AND memory_key = ?
            """,
            [("", key) for key in keys_to_delete],
        )


def _load_daily_suggestions_rows_read_only(db_path_text: str) -> list[tuple[str, object]]:
    with connect_sqlite(
        db_path_text,
        timeout_seconds=_SQLITE_TIMEOUT_SECONDS,
        pragmas=_SQLITE_SESSION_PRAGMAS,
        read_only=True,
    ) as conn:
        rows = conn.execute(
            """
            SELECT memory_key, updated_at
            FROM chatbot_memories
            WHERE owner_id = ? AND substr(memory_key, 1, ?) = ?
            """,
            ("", len(_DAILY_SUGGESTIONS_PREFIX), _DAILY_SUGGESTIONS_PREFIX),
        ).fetchall()
    return [(str(row[0]), row[1]) for row in rows]


def normalize_daily_suggestions_memories(
    memories: Dict[str, Any],
) -> Dict[str, Any]:
    """JSON 스냅샷의 공용 추천 캐시를 SQLite와 같은 기준으로 정리한다."""
    public_memories = memories.get("")
    if not isinstance(public_memories, dict):
        return memories

    normalized = dict(memories)
    normalized_public_memories = dict(public_memories)
    rows = [
        (
            key,
            value.get("updated_at") if isinstance(value, dict) else None,
        )
        for key, value in normalized_public_memories.items()
        if isinstance(key, str) and key.startswith(_DAILY_SUGGESTIONS_PREFIX)
    ]
    # JSON을 읽은 뒤 시각을 잡아, 읽는 사이 새로 쓰인 캐시를 future로 오인하지 않는다.
    for key in _daily_suggestions_keys_to_delete(rows, datetime.now()):
        normalized_public_memories.pop(key, None)
    normalized[""] = normalized_public_memories
    return normalized


def _prune_daily_suggestions_in_sqlite(
    db_path: Path,
    logger: logging.Logger,
    *,
    _retried: bool = False,
) -> bool:
    """공용의 재생성 가능한 일일 추천 캐시만 정리한다."""
    if not ensure_chatbot_storage_schema(db_path, logger):
        return False
    db_path_text = str(db_path)
    try:
        probe_rows = run_sqlite_with_retry(
            lambda: _load_daily_suggestions_rows_read_only(db_path_text),
            max_retries=_SQLITE_RETRY_ATTEMPTS,
            retry_delay_seconds=_SQLITE_RETRY_DELAY_SECONDS,
        )
        # probe 결과를 받은 직후의 시각으로만 삭제 필요성을 판정한다.
        if not _daily_suggestions_keys_to_delete(probe_rows, datetime.now()):
            return True

        def _prune_rows() -> None:
            with connect_sqlite(
                db_path_text,
                timeout_seconds=_SQLITE_TIMEOUT_SECONDS,
                pragmas=_SQLITE_SESSION_PRAGMAS,
            ) as conn:
                cursor = conn.cursor()
                try:
                    cursor.execute("BEGIN IMMEDIATE")
                    _prune_daily_suggestions_cursor(cursor, datetime.now())
                    conn.commit()
                except Exception:
                    conn.rollback()
                    raise

        run_sqlite_with_retry(
            _prune_rows,
            max_retries=_SQLITE_RETRY_ATTEMPTS,
            retry_delay_seconds=_SQLITE_RETRY_DELAY_SECONDS,
        )
        return True
    except Exception as error:
        if (not _retried) and _is_missing_table_error(error, table_name="chatbot_memories"):
            if ensure_chatbot_storage_schema(db_path, logger, force_recheck=True):
                return _prune_daily_suggestions_in_sqlite(
                    db_path,
                    logger,
                    _retried=True,
                )
        logger.error("Failed to prune daily suggestion cache in SQLite: %s", error)
        return False


def save_daily_suggestions_in_sqlite(
    db_path: Path,
    key: str,
    value: Any,
    logger: logging.Logger,
    *,
    _retried: bool = False,
) -> bool:
    """공용 일일 추천 캐시를 저장하고 같은 트랜잭션에서 범위를 정리한다."""
    if not key.startswith(_DAILY_SUGGESTIONS_PREFIX):
        logger.error("Refused non-daily-suggestions cache key: %s", key)
        return False
    if not ensure_chatbot_storage_schema(db_path, logger):
        return False
    db_path_text = str(db_path)
    try:
        def _save_and_prune() -> None:
            with connect_sqlite(
                db_path_text,
                timeout_seconds=_SQLITE_TIMEOUT_SECONDS,
                pragmas=_SQLITE_SESSION_PRAGMAS,
            ) as conn:
                cursor = conn.cursor()
                try:
                    cursor.execute("BEGIN IMMEDIATE")
                    txn_now = datetime.now()
                    _upsert_memory_rows_cursor(
                        cursor=cursor,
                        rows=[(
                            "", key,
                            json.dumps(value, ensure_ascii=False, separators=(",", ":")),
                            txn_now.isoformat(),
                        )],
                    )
                    _prune_daily_suggestions_cursor(cursor, txn_now)
                    conn.commit()
                except Exception:
                    conn.rollback()
                    raise

        run_sqlite_with_retry(
            _save_and_prune,
            max_retries=_SQLITE_RETRY_ATTEMPTS,
            retry_delay_seconds=_SQLITE_RETRY_DELAY_SECONDS,
        )
        return True
    except Exception as error:
        if (not _retried) and _is_missing_table_error(error, table_name="chatbot_memories"):
            if ensure_chatbot_storage_schema(db_path, logger, force_recheck=True):
                return save_daily_suggestions_in_sqlite(
                    db_path,
                    key,
                    value,
                    logger,
                    _retried=True,
                )
        logger.error("Failed to save daily suggestion cache in SQLite: %s", error)
        return False


def _upsert_memory_rows_cursor(
    *,
    cursor: sqlite3.Cursor,
    rows: list[tuple[str, str, str, str]],
) -> None:
    if not rows:
        return
    cursor.executemany(
        """
        INSERT INTO chatbot_memories (owner_id, memory_key, value_json, updated_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(owner_id, memory_key) DO UPDATE SET
            value_json = excluded.value_json,
            updated_at = excluded.updated_at
        WHERE
            chatbot_memories.value_json IS NOT excluded.value_json
            OR chatbot_memories.updated_at IS NOT excluded.updated_at
        """,
        rows,
    )


def load_memories_from_sqlite(
    db_path: Path,
    logger: logging.Logger,
    *,
    _retried: bool = False,
) -> Dict[str, Any] | None:
    if not db_path.exists():
        return None
    if not ensure_chatbot_storage_schema(db_path, logger):
        return None
    if not _prune_daily_suggestions_in_sqlite(db_path, logger):
        return None
    db_path_text = str(db_path)

    try:
        def _load_rows() -> list[sqlite3.Row]:
            with connect_sqlite(
                db_path_text,
                timeout_seconds=_SQLITE_TIMEOUT_SECONDS,
                pragmas=_SQLITE_SESSION_PRAGMAS,
                read_only=True,
            ) as conn:
                conn.row_factory = sqlite3.Row
                return conn.execute(
                    """
                    SELECT owner_id, memory_key, value_json, updated_at
                    FROM chatbot_memories
                    ORDER BY owner_id ASC, memory_key ASC
                    """
                ).fetchall()

        rows = run_sqlite_with_retry(
            _load_rows,
            max_retries=_SQLITE_RETRY_ATTEMPTS,
            retry_delay_seconds=_SQLITE_RETRY_DELAY_SECONDS,
        )
        memories: dict[str, dict[str, dict[str, Any]]] = {}
        for row in rows:
            try:
                value = json.loads(row["value_json"])
            except Exception:
                value = row["value_json"]
            memories.setdefault(str(row["owner_id"]), {})[row["memory_key"]] = {
                "value": value,
                "updated_at": row["updated_at"],
            }
        return memories
    except Exception as error:
        if (not _retried) and _is_missing_table_error(error, table_name="chatbot_memories"):
            if ensure_chatbot_storage_schema(
                db_path,
                logger,
                force_recheck=True,
            ):
                return load_memories_from_sqlite(
                    db_path,
                    logger,
                    _retried=True,
                )
        logger.error(f"Failed to load chatbot memories from SQLite: {error}")
        return None


def save_memories_to_sqlite(
    db_path: Path,
    memories: Dict[str, Dict[str, Any]],
    logger: logging.Logger,
    *,
    _retried: bool = False,
) -> bool:
    """스냅샷의 행을 upsert 한다. 스냅샷에 없는 행은 지우지 않는다.

    다른 워커가 저장한 행일 수 있다. 레거시 JSON 을 빈 SQLite 로 옮길 때 쓴다.
    """
    if not ensure_chatbot_storage_schema(db_path, logger):
        return False
    db_path_text = str(db_path)

    try:
        rows: list[tuple[str, str, str, str]] = []
        for owner_id, owned in memories.items():
            for key, raw_value in (owned or {}).items():
                value = raw_value.get("value") if isinstance(raw_value, dict) else raw_value
                updated_at = (
                    str(raw_value.get("updated_at"))
                    if isinstance(raw_value, dict) and raw_value.get("updated_at")
                    else datetime.now().isoformat()
                )
                rows.append(
                    (
                        str(owner_id),
                        str(key),
                        json.dumps(value, ensure_ascii=False, separators=(",", ":")),
                        updated_at,
                    )
                )

        def _save_rows() -> None:
            with connect_sqlite(
                db_path_text,
                timeout_seconds=_SQLITE_TIMEOUT_SECONDS,
                pragmas=_SQLITE_SESSION_PRAGMAS,
            ) as conn:
                cursor = conn.cursor()
                _upsert_memory_rows_cursor(
                    cursor=cursor,
                    rows=rows,
                )
                conn.commit()

        run_sqlite_with_retry(
            _save_rows,
            max_retries=_SQLITE_RETRY_ATTEMPTS,
            retry_delay_seconds=_SQLITE_RETRY_DELAY_SECONDS,
        )
        return True
    except Exception as error:
        if (not _retried) and _is_missing_table_error(error, table_name="chatbot_memories"):
            if ensure_chatbot_storage_schema(
                db_path,
                logger,
                force_recheck=True,
            ):
                return save_memories_to_sqlite(
                    db_path,
                    memories,
                    logger,
                    _retried=True,
                )
        logger.error(f"Failed to save chatbot memories into SQLite: {error}")
        return False


def upsert_memory_entry_in_sqlite(
    db_path: Path,
    owner_id: str,
    key: str,
    record: Dict[str, Any],
    logger: logging.Logger,
    *,
    _retried: bool = False,
) -> bool:
    if not ensure_chatbot_storage_schema(db_path, logger):
        return False
    db_path_text = str(db_path)
    try:
        value = record.get("value")
        updated_at = str(record.get("updated_at") or datetime.now().isoformat())

        def _upsert_entry() -> None:
            with connect_sqlite(
                db_path_text,
                timeout_seconds=_SQLITE_TIMEOUT_SECONDS,
                pragmas=_SQLITE_SESSION_PRAGMAS,
            ) as conn:
                conn.execute(
                    """
                    INSERT INTO chatbot_memories (owner_id, memory_key, value_json, updated_at)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(owner_id, memory_key) DO UPDATE SET
                        value_json=excluded.value_json,
                        updated_at=excluded.updated_at
                    WHERE
                        chatbot_memories.value_json IS NOT excluded.value_json
                        OR chatbot_memories.updated_at IS NOT excluded.updated_at
                    """,
                    (
                        str(owner_id),
                        str(key),
                        json.dumps(value, ensure_ascii=False, separators=(",", ":")),
                        updated_at,
                    ),
                )
                conn.commit()

        run_sqlite_with_retry(
            _upsert_entry,
            max_retries=_SQLITE_RETRY_ATTEMPTS,
            retry_delay_seconds=_SQLITE_RETRY_DELAY_SECONDS,
        )
        return True
    except Exception as error:
        if (not _retried) and _is_missing_table_error(error, table_name="chatbot_memories"):
            if ensure_chatbot_storage_schema(
                db_path,
                logger,
                force_recheck=True,
            ):
                return upsert_memory_entry_in_sqlite(
                    db_path,
                    owner_id,
                    key,
                    record,
                    logger,
                    _retried=True,
                )
        logger.error(f"Failed to upsert chatbot memory into SQLite: {error}")
        return False


def delete_memory_entry_in_sqlite(
    db_path: Path,
    owner_id: str,
    key: str,
    logger: logging.Logger,
    *,
    _retried: bool = False,
) -> bool:
    if not ensure_chatbot_storage_schema(db_path, logger):
        return False
    db_path_text = str(db_path)
    try:
        def _delete_entry() -> None:
            with connect_sqlite(
                db_path_text,
                timeout_seconds=_SQLITE_TIMEOUT_SECONDS,
                pragmas=_SQLITE_SESSION_PRAGMAS,
            ) as conn:
                conn.execute(
                    """
                    DELETE FROM chatbot_memories
                    WHERE owner_id = ? AND memory_key = ?
                    """,
                    (str(owner_id), str(key)),
                )
                conn.commit()

        run_sqlite_with_retry(
            _delete_entry,
            max_retries=_SQLITE_RETRY_ATTEMPTS,
            retry_delay_seconds=_SQLITE_RETRY_DELAY_SECONDS,
        )
        return True
    except Exception as error:
        if (not _retried) and _is_missing_table_error(error, table_name="chatbot_memories"):
            if ensure_chatbot_storage_schema(
                db_path,
                logger,
                force_recheck=True,
            ):
                return delete_memory_entry_in_sqlite(
                    db_path,
                    owner_id,
                    key,
                    logger,
                    _retried=True,
                )
        logger.error(f"Failed to delete chatbot memory from SQLite: {error}")
        return False


def clear_memories_in_sqlite(
    db_path: Path,
    logger: logging.Logger,
    *,
    owner_id: str,
    _retried: bool = False,
) -> bool:
    """한 소유자의 메모리 행을 지운다. 공용은 owner_id="" 다."""
    if not ensure_chatbot_storage_schema(db_path, logger):
        return False
    db_path_text = str(db_path)
    try:
        def _clear_rows() -> None:
            with connect_sqlite(
                db_path_text,
                timeout_seconds=_SQLITE_TIMEOUT_SECONDS,
                pragmas=_SQLITE_SESSION_PRAGMAS,
            ) as conn:
                conn.execute(
                    "DELETE FROM chatbot_memories WHERE owner_id = ?",
                    (str(owner_id),),
                )
                conn.commit()

        run_sqlite_with_retry(
            _clear_rows,
            max_retries=_SQLITE_RETRY_ATTEMPTS,
            retry_delay_seconds=_SQLITE_RETRY_DELAY_SECONDS,
        )
        return True
    except Exception as error:
        if (not _retried) and _is_missing_table_error(error, table_name="chatbot_memories"):
            if ensure_chatbot_storage_schema(
                db_path,
                logger,
                force_recheck=True,
            ):
                return clear_memories_in_sqlite(
                    db_path,
                    logger,
                    owner_id=owner_id,
                    _retried=True,
                )
        logger.error(f"Failed to clear chatbot memories in SQLite: {error}")
        return False


def clear_general_memories_in_sqlite(
    db_path: Path,
    logger: logging.Logger,
    *,
    owner_id: str,
    _retried: bool = False,
) -> bool:
    """요청자 일반 메모리만 지운다. 공용과 설정 프로필에는 사용하지 않는다."""
    if not owner_id:
        logger.error("Refused to clear general memories without an owner")
        return False
    if not ensure_chatbot_storage_schema(db_path, logger):
        return False
    db_path_text = str(db_path)
    try:
        def _clear_rows() -> None:
            with connect_sqlite(
                db_path_text,
                timeout_seconds=_SQLITE_TIMEOUT_SECONDS,
                pragmas=_SQLITE_SESSION_PRAGMAS,
            ) as conn:
                conn.execute(
                    """
                    DELETE FROM chatbot_memories
                    WHERE owner_id = ? AND memory_key <> ?
                    """,
                    (owner_id, "user_profile"),
                )
                conn.commit()

        run_sqlite_with_retry(
            _clear_rows,
            max_retries=_SQLITE_RETRY_ATTEMPTS,
            retry_delay_seconds=_SQLITE_RETRY_DELAY_SECONDS,
        )
        return True
    except Exception as error:
        if (not _retried) and _is_missing_table_error(error, table_name="chatbot_memories"):
            if ensure_chatbot_storage_schema(db_path, logger, force_recheck=True):
                return clear_general_memories_in_sqlite(
                    db_path,
                    logger,
                    owner_id=owner_id,
                    _retried=True,
                )
        logger.error("Failed to clear general chatbot memories in SQLite: %s", error)
        return False


__all__ = [
    "clear_general_memories_in_sqlite",
    "clear_memories_in_sqlite",
    "delete_memory_entry_in_sqlite",
    "load_memories_from_sqlite",
    "normalize_daily_suggestions_memories",
    "save_memories_to_sqlite",
    "save_daily_suggestions_in_sqlite",
    "upsert_memory_entry_in_sqlite",
]
