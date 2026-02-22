#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
챗봇 히스토리 SQLite 저장 헬퍼
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


def _is_missing_table_error(error: Exception, *, table_names: tuple[str, ...]) -> bool:
    if not isinstance(error, sqlite3.OperationalError):
        return False
    message = str(error).lower()
    if "no such table" not in message:
        return False
    return any(table_name.lower() in message for table_name in table_names)


def _serialize_message_parts(parts: Any) -> str:
    try:
        return json.dumps(parts, ensure_ascii=False, separators=(",", ":"))
    except Exception:
        return json.dumps([], ensure_ascii=False, separators=(",", ":"))


def _build_message_rows(raw_messages: Any, updated_at: str) -> list[tuple[int, str, str, str]]:
    rows: list[tuple[int, str, str, str]] = []
    if not isinstance(raw_messages, list):
        return rows

    for message_index, raw_message in enumerate(raw_messages):
        if not isinstance(raw_message, dict):
            continue
        role = str(raw_message.get("role") or "user")
        parts_json = _serialize_message_parts(raw_message.get("parts", []))
        timestamp = str(raw_message.get("timestamp") or updated_at)
        rows.append((int(message_index), role, parts_json, timestamp))
    return rows


def _upsert_session_metadata_cursor(
    *,
    cursor: sqlite3.Cursor,
    session_id: str,
    title: str,
    created_at: str,
    updated_at: str,
    model_name: str,
    owner_id: Any,
) -> None:
    cursor.execute(
        """
        INSERT INTO chatbot_sessions (
            session_id, title, created_at, updated_at, model_name, owner_id
        ) VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(session_id) DO UPDATE SET
            title=excluded.title,
            created_at=excluded.created_at,
            updated_at=excluded.updated_at,
            model_name=excluded.model_name,
            owner_id=excluded.owner_id
        """,
        (session_id, title, created_at, updated_at, model_name, owner_id),
    )


def _insert_message_rows_cursor(
    *,
    cursor: sqlite3.Cursor,
    session_id: str,
    message_rows: list[tuple[int, str, str, str]],
) -> None:
    if not message_rows:
        return

    rows = [
        (
            session_id,
            int(message_index),
            role,
            parts_json,
            timestamp,
        )
        for message_index, role, parts_json, timestamp in message_rows
    ]
    cursor.executemany(
        """
        INSERT INTO chatbot_messages (
            session_id, message_index, role, parts_json, timestamp
        ) VALUES (?, ?, ?, ?, ?)
        """,
        rows,
    )


def _rewrite_session_message_rows_cursor(
    *,
    cursor: sqlite3.Cursor,
    session_id: str,
    message_rows: list[tuple[int, str, str, str]],
) -> None:
    cursor.execute(
        """
        DELETE FROM chatbot_messages
        WHERE session_id = ?
        """,
        (session_id,),
    )
    _insert_message_rows_cursor(
        cursor=cursor,
        session_id=session_id,
        message_rows=message_rows,
    )


def _clear_all_sessions_cursor(*, cursor: sqlite3.Cursor) -> None:
    # foreign_keys=ON 이므로 세션 삭제 시 메시지가 ON DELETE CASCADE 로 함께 삭제된다.
    cursor.execute("DELETE FROM chatbot_sessions")


def _load_last_message_row_cursor(
    *,
    cursor: sqlite3.Cursor,
    session_id: str,
) -> tuple[int, str, str, str] | None:
    row = cursor.execute(
        """
        SELECT message_index, role, parts_json, timestamp
        FROM chatbot_messages
        WHERE session_id = ?
        ORDER BY message_index DESC
        LIMIT 1
        """,
        (session_id,),
    ).fetchone()
    if not row:
        return None
    message_index = int(row[0] or 0)
    return (message_index, str(row[1]), str(row[2]), str(row[3]))


def _is_append_only_message_update(
    *,
    cursor: sqlite3.Cursor,
    session_id: str,
    message_rows: list[tuple[int, str, str, str]],
) -> tuple[bool, int]:
    existing_last = _load_last_message_row_cursor(
        cursor=cursor,
        session_id=session_id,
    )
    if existing_last is None:
        return True, 0

    existing_count = int(existing_last[0]) + 1
    if len(message_rows) <= existing_count:
        return False, existing_count

    _, last_role, last_parts_json, last_timestamp = message_rows[existing_count - 1]
    return (
        (existing_last[1], existing_last[2], existing_last[3]) == (last_role, last_parts_json, last_timestamp),
        existing_count,
    )


def _decode_message_parts(parts_json: str) -> list[Any]:
    try:
        loaded = json.loads(parts_json)
        if isinstance(loaded, list):
            return loaded
    except Exception:
        pass
    return [{"text": str(parts_json)}]


def load_history_sessions_from_sqlite(
    db_path: Path,
    logger: logging.Logger,
    *,
    _retried: bool = False,
) -> Dict[str, Any] | None:
    if not db_path.exists():
        return None
    if not ensure_chatbot_storage_schema(db_path, logger):
        return None

    try:
        with connect_sqlite(str(db_path), timeout_seconds=30, pragmas=_SQLITE_PRAGMAS) as conn:
            conn.row_factory = sqlite3.Row

            session_rows = conn.execute(
                """
                SELECT session_id, title, created_at, updated_at, model_name, owner_id
                FROM chatbot_sessions
                ORDER BY updated_at DESC, session_id ASC
                """
            ).fetchall()

            sessions: dict[str, dict[str, Any]] = {}
            for row in session_rows:
                session_id = str(row["session_id"])
                sessions[session_id] = {
                    "id": session_id,
                    "title": row["title"],
                    "messages": [],
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                    "model": row["model_name"],
                    "owner_id": row["owner_id"],
                }

            if not sessions:
                return {}

            message_rows = conn.execute(
                """
                SELECT session_id, message_index, role, parts_json, timestamp
                FROM chatbot_messages
                ORDER BY session_id ASC, message_index ASC
                """
            ).fetchall()
            for row in message_rows:
                session = sessions.get(str(row["session_id"]))
                if session is None:
                    continue
                session["messages"].append(
                    {
                        "role": row["role"],
                        "parts": _decode_message_parts(row["parts_json"]),
                        "timestamp": row["timestamp"],
                    }
                )

            return sessions
    except Exception as error:
        if (not _retried) and _is_missing_table_error(
            error,
            table_names=("chatbot_sessions", "chatbot_messages"),
        ):
            if ensure_chatbot_storage_schema(
                db_path,
                logger,
                force_recheck=True,
            ):
                return load_history_sessions_from_sqlite(
                    db_path,
                    logger,
                    _retried=True,
                )
        logger.error(f"Failed to load chatbot history from SQLite: {error}")
        return None


def _upsert_history_session_with_messages_cursor(
    *,
    cursor: sqlite3.Cursor,
    raw_session_id: str,
    raw_session: Dict[str, Any],
) -> None:
    session_id = str(raw_session.get("id") or raw_session_id)
    title = str(raw_session.get("title") or "새로운 대화")
    created_at = str(raw_session.get("created_at") or datetime.now().isoformat())
    updated_at = str(raw_session.get("updated_at") or created_at)
    model_name = str(raw_session.get("model") or "gemini-2.0-flash-lite")
    owner_id = raw_session.get("owner_id")
    message_rows = _build_message_rows(raw_session.get("messages", []), updated_at)

    _upsert_session_metadata_cursor(
        cursor=cursor,
        session_id=session_id,
        title=title,
        created_at=created_at,
        updated_at=updated_at,
        model_name=model_name,
        owner_id=owner_id,
    )
    _insert_message_rows_cursor(
        cursor=cursor,
        session_id=session_id,
        message_rows=message_rows,
    )


def _upsert_history_session_with_messages_delta_cursor(
    *,
    cursor: sqlite3.Cursor,
    raw_session_id: str,
    raw_session: Dict[str, Any],
) -> None:
    session_id = str(raw_session.get("id") or raw_session_id)
    title = str(raw_session.get("title") or "새로운 대화")
    created_at = str(raw_session.get("created_at") or datetime.now().isoformat())
    updated_at = str(raw_session.get("updated_at") or created_at)
    model_name = str(raw_session.get("model") or "gemini-2.0-flash-lite")
    owner_id = raw_session.get("owner_id")
    message_rows = _build_message_rows(raw_session.get("messages", []), updated_at)

    _upsert_session_metadata_cursor(
        cursor=cursor,
        session_id=session_id,
        title=title,
        created_at=created_at,
        updated_at=updated_at,
        model_name=model_name,
        owner_id=owner_id,
    )

    is_append_only, existing_count = _is_append_only_message_update(
        cursor=cursor,
        session_id=session_id,
        message_rows=message_rows,
    )
    if is_append_only:
        _insert_message_rows_cursor(
            cursor=cursor,
            session_id=session_id,
            message_rows=message_rows[existing_count:],
        )
        return

    _rewrite_session_message_rows_cursor(
        cursor=cursor,
        session_id=session_id,
        message_rows=message_rows,
    )


def save_history_sessions_to_sqlite(
    db_path: Path,
    sessions: Dict[str, Any],
    logger: logging.Logger,
    *,
    _retried: bool = False,
) -> bool:
    if not ensure_chatbot_storage_schema(db_path, logger):
        return False

    try:
        with connect_sqlite(str(db_path), timeout_seconds=30, pragmas=_SQLITE_PRAGMAS) as conn:
            cursor = conn.cursor()
            _clear_all_sessions_cursor(cursor=cursor)

            for raw_session_id, raw_session in sessions.items():
                if not isinstance(raw_session, dict):
                    continue
                _upsert_history_session_with_messages_cursor(
                    cursor=cursor,
                    raw_session_id=str(raw_session_id),
                    raw_session=raw_session,
                )
            conn.commit()
        return True
    except Exception as error:
        if (not _retried) and _is_missing_table_error(
            error,
            table_names=("chatbot_sessions", "chatbot_messages"),
        ):
            if ensure_chatbot_storage_schema(
                db_path,
                logger,
                force_recheck=True,
            ):
                return save_history_sessions_to_sqlite(
                    db_path,
                    sessions,
                    logger,
                    _retried=True,
                )
        logger.error(f"Failed to save chatbot history into SQLite: {error}")
        return False


def upsert_history_session_with_messages(
    db_path: Path,
    session: Dict[str, Any],
    logger: logging.Logger,
    *,
    _retried: bool = False,
) -> bool:
    if not ensure_chatbot_storage_schema(db_path, logger):
        return False

    try:
        raw_session_id = str(session.get("id") or "")
        if not raw_session_id:
            return False

        with connect_sqlite(str(db_path), timeout_seconds=30, pragmas=_SQLITE_PRAGMAS) as conn:
            cursor = conn.cursor()
            _upsert_history_session_with_messages_delta_cursor(
                cursor=cursor,
                raw_session_id=raw_session_id,
                raw_session=session,
            )
            conn.commit()
        return True
    except Exception as error:
        if (not _retried) and _is_missing_table_error(
            error,
            table_names=("chatbot_sessions", "chatbot_messages"),
        ):
            if ensure_chatbot_storage_schema(
                db_path,
                logger,
                force_recheck=True,
            ):
                return upsert_history_session_with_messages(
                    db_path,
                    session,
                    logger,
                    _retried=True,
                )
        logger.error(f"Failed to upsert chatbot session into SQLite: {error}")
        return False


def apply_history_session_deltas_in_sqlite(
    db_path: Path,
    sessions: Dict[str, Any],
    changed_session_ids: set[str],
    deleted_session_ids: set[str],
    clear_all: bool,
    logger: logging.Logger,
    *,
    _retried: bool = False,
) -> bool:
    if not ensure_chatbot_storage_schema(db_path, logger):
        return False

    try:
        with connect_sqlite(str(db_path), timeout_seconds=30, pragmas=_SQLITE_PRAGMAS) as conn:
            cursor = conn.cursor()
            if clear_all:
                _clear_all_sessions_cursor(cursor=cursor)
                conn.commit()
                return True

            if deleted_session_ids:
                cursor.executemany(
                    """
                    DELETE FROM chatbot_sessions
                    WHERE session_id = ?
                    """,
                    [(str(item),) for item in sorted(deleted_session_ids)],
                )

            for session_id in sorted(changed_session_ids):
                raw_session = sessions.get(session_id)
                if not isinstance(raw_session, dict):
                    continue
                _upsert_history_session_with_messages_delta_cursor(
                    cursor=cursor,
                    raw_session_id=str(session_id),
                    raw_session=raw_session,
                )
            conn.commit()
        return True
    except Exception as error:
        if (not _retried) and _is_missing_table_error(
            error,
            table_names=("chatbot_sessions", "chatbot_messages"),
        ):
            if ensure_chatbot_storage_schema(
                db_path,
                logger,
                force_recheck=True,
            ):
                return apply_history_session_deltas_in_sqlite(
                    db_path,
                    sessions=sessions,
                    changed_session_ids=changed_session_ids,
                    deleted_session_ids=deleted_session_ids,
                    clear_all=clear_all,
                    logger=logger,
                    _retried=True,
                )
        logger.error(f"Failed to apply chatbot history deltas into SQLite: {error}")
        return False


def delete_history_session_from_sqlite(
    db_path: Path,
    session_id: str,
    logger: logging.Logger,
    *,
    _retried: bool = False,
) -> bool:
    if not ensure_chatbot_storage_schema(db_path, logger):
        return False
    try:
        with connect_sqlite(str(db_path), timeout_seconds=30, pragmas=_SQLITE_PRAGMAS) as conn:
            conn.execute(
                """
                DELETE FROM chatbot_sessions
                WHERE session_id = ?
                """,
                (session_id,),
            )
            conn.commit()
        return True
    except Exception as error:
        if (not _retried) and _is_missing_table_error(
            error,
            table_names=("chatbot_sessions", "chatbot_messages"),
        ):
            if ensure_chatbot_storage_schema(
                db_path,
                logger,
                force_recheck=True,
            ):
                return delete_history_session_from_sqlite(
                    db_path,
                    session_id,
                    logger,
                    _retried=True,
                )
        logger.error(f"Failed to delete chatbot session from SQLite: {error}")
        return False


def clear_history_sessions_in_sqlite(
    db_path: Path,
    logger: logging.Logger,
    *,
    _retried: bool = False,
) -> bool:
    if not ensure_chatbot_storage_schema(db_path, logger):
        return False
    try:
        with connect_sqlite(str(db_path), timeout_seconds=30, pragmas=_SQLITE_PRAGMAS) as conn:
            _clear_all_sessions_cursor(cursor=conn.cursor())
            conn.commit()
        return True
    except Exception as error:
        if (not _retried) and _is_missing_table_error(
            error,
            table_names=("chatbot_sessions", "chatbot_messages"),
        ):
            if ensure_chatbot_storage_schema(
                db_path,
                logger,
                force_recheck=True,
            ):
                return clear_history_sessions_in_sqlite(
                    db_path,
                    logger,
                    _retried=True,
                )
        logger.error(f"Failed to clear chatbot history in SQLite: {error}")
        return False


__all__ = [
    "apply_history_session_deltas_in_sqlite",
    "clear_history_sessions_in_sqlite",
    "delete_history_session_from_sqlite",
    "load_history_sessions_from_sqlite",
    "save_history_sessions_to_sqlite",
    "upsert_history_session_with_messages",
]
