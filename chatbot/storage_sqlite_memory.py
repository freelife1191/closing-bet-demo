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

from services.sqlite_utils import connect_sqlite

from .storage_sqlite_common import _SQLITE_PRAGMAS, ensure_chatbot_storage_schema


def load_memories_from_sqlite(
    db_path: Path,
    logger: logging.Logger,
) -> Dict[str, Any] | None:
    if not db_path.exists():
        return None
    if not ensure_chatbot_storage_schema(db_path, logger):
        return None

    try:
        with connect_sqlite(str(db_path), timeout_seconds=30, pragmas=_SQLITE_PRAGMAS) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT memory_key, value_json, updated_at
                FROM chatbot_memories
                ORDER BY memory_key ASC
                """
            ).fetchall()

            memories: dict[str, dict[str, Any]] = {}
            for row in rows:
                try:
                    value = json.loads(row["value_json"])
                except Exception:
                    value = row["value_json"]
                memories[row["memory_key"]] = {
                    "value": value,
                    "updated_at": row["updated_at"],
                }
            return memories
    except Exception as error:
        logger.error(f"Failed to load chatbot memories from SQLite: {error}")
        return None


def save_memories_to_sqlite(
    db_path: Path,
    memories: Dict[str, Any],
    logger: logging.Logger,
) -> bool:
    if not ensure_chatbot_storage_schema(db_path, logger):
        return False

    try:
        with connect_sqlite(str(db_path), timeout_seconds=30, pragmas=_SQLITE_PRAGMAS) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM chatbot_memories")

            for key, raw_value in memories.items():
                value = raw_value.get("value") if isinstance(raw_value, dict) else raw_value
                updated_at = (
                    str(raw_value.get("updated_at"))
                    if isinstance(raw_value, dict) and raw_value.get("updated_at")
                    else datetime.now().isoformat()
                )
                cursor.execute(
                    """
                    INSERT INTO chatbot_memories (memory_key, value_json, updated_at)
                    VALUES (?, ?, ?)
                    """,
                    (str(key), json.dumps(value, ensure_ascii=False), updated_at),
                )
            conn.commit()
        return True
    except Exception as error:
        logger.error(f"Failed to save chatbot memories into SQLite: {error}")
        return False


def upsert_memory_entry_in_sqlite(
    db_path: Path,
    key: str,
    record: Dict[str, Any],
    logger: logging.Logger,
) -> bool:
    if not ensure_chatbot_storage_schema(db_path, logger):
        return False
    try:
        value = record.get("value")
        updated_at = str(record.get("updated_at") or datetime.now().isoformat())
        with connect_sqlite(str(db_path), timeout_seconds=30, pragmas=_SQLITE_PRAGMAS) as conn:
            conn.execute(
                """
                INSERT INTO chatbot_memories (memory_key, value_json, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(memory_key) DO UPDATE SET
                    value_json=excluded.value_json,
                    updated_at=excluded.updated_at
                """,
                (str(key), json.dumps(value, ensure_ascii=False), updated_at),
            )
            conn.commit()
        return True
    except Exception as error:
        logger.error(f"Failed to upsert chatbot memory into SQLite: {error}")
        return False


def delete_memory_entry_in_sqlite(
    db_path: Path,
    key: str,
    logger: logging.Logger,
) -> bool:
    if not ensure_chatbot_storage_schema(db_path, logger):
        return False
    try:
        with connect_sqlite(str(db_path), timeout_seconds=30, pragmas=_SQLITE_PRAGMAS) as conn:
            conn.execute(
                """
                DELETE FROM chatbot_memories
                WHERE memory_key = ?
                """,
                (str(key),),
            )
            conn.commit()
        return True
    except Exception as error:
        logger.error(f"Failed to delete chatbot memory from SQLite: {error}")
        return False


def clear_memories_in_sqlite(
    db_path: Path,
    logger: logging.Logger,
) -> bool:
    if not ensure_chatbot_storage_schema(db_path, logger):
        return False
    try:
        with connect_sqlite(str(db_path), timeout_seconds=30, pragmas=_SQLITE_PRAGMAS) as conn:
            conn.execute("DELETE FROM chatbot_memories")
            conn.commit()
        return True
    except Exception as error:
        logger.error(f"Failed to clear chatbot memories in SQLite: {error}")
        return False


__all__ = [
    "clear_memories_in_sqlite",
    "delete_memory_entry_in_sqlite",
    "load_memories_from_sqlite",
    "save_memories_to_sqlite",
    "upsert_memory_entry_in_sqlite",
]
