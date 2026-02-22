#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
챗봇 SQLite 스토리지 공통 유틸
"""

from __future__ import annotations

import logging
import threading
from pathlib import Path

from services.sqlite_utils import build_sqlite_pragmas, connect_sqlite


_SQLITE_PRAGMAS = build_sqlite_pragmas(
    busy_timeout_ms=30_000,
    include_foreign_keys=True,
)
_SCHEMA_READY_LOCK = threading.Lock()
_SCHEMA_READY_DB_PATHS: set[str] = set()


def _normalize_db_key(db_path: Path) -> str:
    try:
        return str(db_path.expanduser().resolve(strict=False))
    except Exception:
        return str(db_path)


def resolve_chatbot_storage_db_path(data_dir: Path) -> Path:
    return data_dir / "chatbot_storage.db"


def ensure_chatbot_storage_schema(
    db_path: Path,
    logger: logging.Logger,
    *,
    force_recheck: bool = False,
) -> bool:
    db_key = _normalize_db_key(db_path)
    with _SCHEMA_READY_LOCK:
        if force_recheck:
            _SCHEMA_READY_DB_PATHS.discard(db_key)
        elif db_key in _SCHEMA_READY_DB_PATHS:
            if db_path.exists():
                return True
            _SCHEMA_READY_DB_PATHS.discard(db_key)

    try:
        with connect_sqlite(
            str(db_path),
            timeout_seconds=30,
            pragmas=_SQLITE_PRAGMAS,
        ) as conn:
            cursor = conn.cursor()
            cursor.executescript(
                """
                CREATE TABLE IF NOT EXISTS chatbot_sessions (
                    session_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    model_name TEXT NOT NULL,
                    owner_id TEXT
                );
                CREATE TABLE IF NOT EXISTS chatbot_messages (
                    session_id TEXT NOT NULL,
                    message_index INTEGER NOT NULL,
                    role TEXT NOT NULL,
                    parts_json TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    PRIMARY KEY (session_id, message_index),
                    FOREIGN KEY (session_id) REFERENCES chatbot_sessions(session_id) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS chatbot_memories (
                    memory_key TEXT PRIMARY KEY,
                    value_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_chatbot_sessions_owner_updated
                ON chatbot_sessions(owner_id, updated_at DESC);
                CREATE INDEX IF NOT EXISTS idx_chatbot_sessions_updated
                ON chatbot_sessions(updated_at DESC);
                CREATE INDEX IF NOT EXISTS idx_chatbot_messages_session_idx
                ON chatbot_messages(session_id, message_index);
                """
            )
            conn.commit()
        with _SCHEMA_READY_LOCK:
            _SCHEMA_READY_DB_PATHS.add(db_key)
        return True
    except Exception as error:
        with _SCHEMA_READY_LOCK:
            _SCHEMA_READY_DB_PATHS.discard(db_key)
        logger.error(f"Failed to initialize chatbot SQLite schema: {error}")
        return False


__all__ = [
    "_SQLITE_PRAGMAS",
    "ensure_chatbot_storage_schema",
    "resolve_chatbot_storage_db_path",
]
