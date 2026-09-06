#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
챗봇 메모리 SQLite 저장 헬퍼
"""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime
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


def _is_missing_table_error(error: Exception, *, table_name: str) -> bool:
    return is_sqlite_missing_table_error(error, table_names=table_name)


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


__all__ = [
    "clear_memories_in_sqlite",
    "delete_memory_entry_in_sqlite",
    "load_memories_from_sqlite",
    "save_memories_to_sqlite",
    "upsert_memory_entry_in_sqlite",
]
