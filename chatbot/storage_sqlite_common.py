#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
챗봇 SQLite 스토리지 공통 유틸
"""

from __future__ import annotations

import logging
import sqlite3
import threading
from pathlib import Path

from services.sqlite_utils import (
    build_sqlite_pragmas,
    connect_sqlite,
    normalize_sqlite_db_key,
    run_sqlite_with_retry,
    sqlite_db_path_exists,
)


_SQLITE_PRAGMAS = build_sqlite_pragmas(
    busy_timeout_ms=30_000,
    include_foreign_keys=True,
)
_SQLITE_TIMEOUT_SECONDS = 30
_SQLITE_RETRY_ATTEMPTS = 2
_SQLITE_RETRY_DELAY_SECONDS = 0.03
_SCHEMA_READY_LOCK = threading.Lock()
_SCHEMA_READY_CONDITION = threading.Condition(_SCHEMA_READY_LOCK)
_SCHEMA_READY_DB_PATHS: set[str] = set()
_SCHEMA_INIT_IN_PROGRESS: set[str] = set()


def resolve_chatbot_storage_db_path(data_dir: Path) -> Path:
    return data_dir / "chatbot_storage.db"


def _is_duplicate_column_error(error: Exception) -> bool:
    if not isinstance(error, sqlite3.OperationalError):
        return False
    return "duplicate column name" in str(error).lower()


def _load_table_columns(cursor: sqlite3.Cursor, table_name: str) -> set[str]:
    rows = cursor.execute(f"PRAGMA table_info({table_name})").fetchall()
    columns: set[str] = set()
    for row in rows:
        if len(row) < 2:
            continue
        columns.add(str(row[1]))
    return columns


def _ensure_chatbot_sessions_columns(
    cursor: sqlite3.Cursor,
    logger: logging.Logger,
) -> None:
    columns = _load_table_columns(cursor, "chatbot_sessions")
    if "messages_hash" in columns:
        return

    try:
        cursor.execute(
            """
            ALTER TABLE chatbot_sessions
            ADD COLUMN messages_hash TEXT NOT NULL DEFAULT ''
            """
        )
    except sqlite3.OperationalError as error:
        if not _is_duplicate_column_error(error):
            logger.error(f"Failed to migrate chatbot_sessions.messages_hash: {error}")
            raise


def _drop_redundant_chatbot_messages_index(
    cursor: sqlite3.Cursor,
    logger: logging.Logger,
) -> None:
    try:
        cursor.execute("DROP INDEX IF EXISTS idx_chatbot_messages_session_idx")
    except sqlite3.OperationalError as error:
        logger.error(f"Failed to drop redundant chatbot_messages index: {error}")
        raise


def ensure_chatbot_storage_schema(
    db_path: Path,
    logger: logging.Logger,
    *,
    force_recheck: bool = False,
) -> bool:
    db_path_text = str(db_path)
    db_key = normalize_sqlite_db_key(db_path_text)
    with _SCHEMA_READY_CONDITION:
        if force_recheck:
            _SCHEMA_READY_DB_PATHS.discard(db_key)
        elif db_key in _SCHEMA_READY_DB_PATHS:
            if sqlite_db_path_exists(db_path_text):
                return True
            _SCHEMA_READY_DB_PATHS.discard(db_key)

        while db_key in _SCHEMA_INIT_IN_PROGRESS:
            _SCHEMA_READY_CONDITION.wait()
            if db_key in _SCHEMA_READY_DB_PATHS:
                if sqlite_db_path_exists(db_path_text):
                    return True
                _SCHEMA_READY_DB_PATHS.discard(db_key)

        _SCHEMA_INIT_IN_PROGRESS.add(db_key)

    def _initialize_schema() -> None:
        with connect_sqlite(
            db_path_text,
            timeout_seconds=_SQLITE_TIMEOUT_SECONDS,
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
                    owner_id TEXT,
                    messages_hash TEXT NOT NULL DEFAULT ''
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
                """
            )
            _ensure_chatbot_sessions_columns(
                cursor=cursor,
                logger=logger,
            )
            _drop_redundant_chatbot_messages_index(
                cursor=cursor,
                logger=logger,
            )
            conn.commit()

    initialization_succeeded = False
    init_error: Exception | None = None
    try:
        run_sqlite_with_retry(
            _initialize_schema,
            max_retries=_SQLITE_RETRY_ATTEMPTS,
            retry_delay_seconds=_SQLITE_RETRY_DELAY_SECONDS,
        )
        initialization_succeeded = True
    except Exception as error:
        init_error = error
    finally:
        with _SCHEMA_READY_CONDITION:
            _SCHEMA_INIT_IN_PROGRESS.discard(db_key)
            if initialization_succeeded:
                _SCHEMA_READY_DB_PATHS.add(db_key)
            else:
                _SCHEMA_READY_DB_PATHS.discard(db_key)
            _SCHEMA_READY_CONDITION.notify_all()

    if initialization_succeeded:
        return True
    logger.error(f"Failed to initialize chatbot SQLite schema: {init_error}")
    return False


__all__ = [
    "_SQLITE_PRAGMAS",
    "ensure_chatbot_storage_schema",
    "resolve_chatbot_storage_db_path",
]
