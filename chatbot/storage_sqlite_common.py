#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
챗봇 SQLite 스토리지 공통 유틸
"""

from __future__ import annotations

import logging
from pathlib import Path

from services.sqlite_utils import connect_sqlite


_SQLITE_PRAGMAS = (
    "PRAGMA journal_mode=WAL",
    "PRAGMA synchronous=NORMAL",
    "PRAGMA temp_store=MEMORY",
    "PRAGMA busy_timeout=30000",
    "PRAGMA foreign_keys=ON",
)


def resolve_chatbot_storage_db_path(data_dir: Path) -> Path:
    return data_dir / "chatbot_storage.db"


def ensure_chatbot_storage_schema(db_path: Path, logger: logging.Logger) -> bool:
    try:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        with connect_sqlite(
            str(db_path),
            timeout_seconds=30,
            pragmas=_SQLITE_PRAGMAS,
        ) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS chatbot_sessions (
                    session_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    model_name TEXT NOT NULL,
                    owner_id TEXT
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS chatbot_messages (
                    session_id TEXT NOT NULL,
                    message_index INTEGER NOT NULL,
                    role TEXT NOT NULL,
                    parts_json TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    PRIMARY KEY (session_id, message_index),
                    FOREIGN KEY (session_id) REFERENCES chatbot_sessions(session_id) ON DELETE CASCADE
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS chatbot_memories (
                    memory_key TEXT PRIMARY KEY,
                    value_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_chatbot_sessions_owner_updated
                ON chatbot_sessions(owner_id, updated_at DESC)
                """
            )
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_chatbot_sessions_updated
                ON chatbot_sessions(updated_at DESC)
                """
            )
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_chatbot_messages_session_idx
                ON chatbot_messages(session_id, message_index)
                """
            )
            conn.commit()
        return True
    except Exception as error:
        logger.error(f"Failed to initialize chatbot SQLite schema: {error}")
        return False


__all__ = [
    "_SQLITE_PRAGMAS",
    "ensure_chatbot_storage_schema",
    "resolve_chatbot_storage_db_path",
]
