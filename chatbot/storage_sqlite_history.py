#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
챗봇 히스토리 SQLite 저장 헬퍼
"""

from __future__ import annotations

import hashlib
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

from .storage_sqlite_common import _SQLITE_PRAGMAS, ensure_chatbot_storage_schema

_SQLITE_TIMEOUT_SECONDS = 30
_SQLITE_RETRY_ATTEMPTS = 2
_SQLITE_RETRY_DELAY_SECONDS = 0.03


def _is_missing_table_error(error: Exception, *, table_names: tuple[str, ...]) -> bool:
    return is_sqlite_missing_table_error(error, table_names=table_names)


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
    messages_hash: str,
) -> None:
    cursor.execute(
        """
        INSERT INTO chatbot_sessions (
            session_id, title, created_at, updated_at, model_name, owner_id, messages_hash
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(session_id) DO UPDATE SET
            title=excluded.title,
            created_at=excluded.created_at,
            updated_at=excluded.updated_at,
            model_name=excluded.model_name,
            owner_id=excluded.owner_id,
            messages_hash=excluded.messages_hash
        WHERE
            chatbot_sessions.title IS NOT excluded.title
            OR chatbot_sessions.created_at IS NOT excluded.created_at
            OR chatbot_sessions.updated_at IS NOT excluded.updated_at
            OR chatbot_sessions.model_name IS NOT excluded.model_name
            OR chatbot_sessions.owner_id IS NOT excluded.owner_id
            OR chatbot_sessions.messages_hash IS NOT excluded.messages_hash
        """,
        (session_id, title, created_at, updated_at, model_name, owner_id, messages_hash),
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


def _delete_stale_sessions_cursor(
    *,
    cursor: sqlite3.Cursor,
    active_session_ids: list[str],
) -> None:
    if not active_session_ids:
        _clear_all_sessions_cursor(cursor=cursor)
        return

    cursor.execute(
        """
        CREATE TEMP TABLE IF NOT EXISTS _tmp_chatbot_session_ids (
            session_id TEXT PRIMARY KEY
        )
        """
    )
    cursor.execute("DELETE FROM _tmp_chatbot_session_ids")
    cursor.executemany(
        "INSERT OR IGNORE INTO _tmp_chatbot_session_ids(session_id) VALUES (?)",
        [(session_id,) for session_id in active_session_ids],
    )
    cursor.execute(
        """
        DELETE FROM chatbot_sessions
        WHERE session_id NOT IN (
            SELECT session_id
            FROM _tmp_chatbot_session_ids
        )
        """
    )


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


def _ensure_message_table_accessible_cursor(*, cursor: sqlite3.Cursor) -> None:
    cursor.execute(
        """
        SELECT 1
        FROM chatbot_messages
        LIMIT 1
        """
    ).fetchone()


def _is_same_message_tail_snapshot(
    *,
    cursor: sqlite3.Cursor,
    session_id: str,
    message_rows: list[tuple[int, str, str, str]],
) -> bool:
    if not message_rows:
        return _load_last_message_row_cursor(cursor=cursor, session_id=session_id) is None

    existing_last = _load_last_message_row_cursor(
        cursor=cursor,
        session_id=session_id,
    )
    if existing_last is None:
        return False
    existing_count = int(existing_last[0]) + 1
    if existing_count != len(message_rows):
        return False

    _, last_role, last_parts_json, last_timestamp = message_rows[-1]
    return (
        existing_last[1] == last_role
        and existing_last[2] == last_parts_json
        and existing_last[3] == last_timestamp
    )


def _normalize_owner_id(owner_id: Any) -> str | None:
    if owner_id is None:
        return None
    return str(owner_id)


def _message_rows_hash(message_rows: list[tuple[int, str, str, str]]) -> str:
    serialized = json.dumps(
        message_rows,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _load_existing_session_metadata_cursor(
    *,
    cursor: sqlite3.Cursor,
    session_id: str,
) -> tuple[str, str, str, str, str | None, str] | None:
    row = cursor.execute(
        """
        SELECT title, created_at, updated_at, model_name, owner_id, messages_hash
        FROM chatbot_sessions
        WHERE session_id = ?
        """,
        (session_id,),
    ).fetchone()
    if row is None:
        return None
    return (
        str(row[0]),
        str(row[1]),
        str(row[2]),
        str(row[3]),
        _normalize_owner_id(row[4]),
        str(row[5] or ""),
    )


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
    db_path_text = str(db_path)

    try:
        def _load_sessions() -> dict[str, dict[str, Any]]:
            with connect_sqlite(
                db_path_text,
                timeout_seconds=_SQLITE_TIMEOUT_SECONDS,
                pragmas=_SQLITE_PRAGMAS,
            ) as conn:
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

        return run_sqlite_with_retry(
            _load_sessions,
            max_retries=_SQLITE_RETRY_ATTEMPTS,
            retry_delay_seconds=_SQLITE_RETRY_DELAY_SECONDS,
        )
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
    messages_hash = _message_rows_hash(message_rows)
    normalized_owner_id = _normalize_owner_id(owner_id)
    existing_metadata = _load_existing_session_metadata_cursor(
        cursor=cursor,
        session_id=session_id,
    )
    has_same_messages = False

    if existing_metadata is not None:
        (
            existing_title,
            existing_created_at,
            existing_updated_at,
            existing_model_name,
            existing_owner_id,
            existing_messages_hash,
        ) = existing_metadata
        has_same_messages = (
            existing_messages_hash == messages_hash
            and _is_same_message_tail_snapshot(
                cursor=cursor,
                session_id=session_id,
                message_rows=message_rows,
            )
        )
        if (
            existing_title == title
            and existing_created_at == created_at
            and existing_updated_at == updated_at
            and existing_model_name == model_name
            and existing_owner_id == normalized_owner_id
            and has_same_messages
        ):
            return

    _upsert_session_metadata_cursor(
        cursor=cursor,
        session_id=session_id,
        title=title,
        created_at=created_at,
        updated_at=updated_at,
        model_name=model_name,
        owner_id=owner_id,
        messages_hash=messages_hash,
    )
    if has_same_messages:
        return

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
    db_path_text = str(db_path)

    try:
        def _save_sessions() -> None:
            with connect_sqlite(
                db_path_text,
                timeout_seconds=_SQLITE_TIMEOUT_SECONDS,
                pragmas=_SQLITE_PRAGMAS,
            ) as conn:
                cursor = conn.cursor()
                _ensure_message_table_accessible_cursor(cursor=cursor)
                active_session_ids: list[str] = []

                for raw_session_id, raw_session in sessions.items():
                    if not isinstance(raw_session, dict):
                        continue
                    normalized_session_id = str(raw_session.get("id") or raw_session_id)
                    active_session_ids.append(normalized_session_id)
                    _upsert_history_session_with_messages_delta_cursor(
                        cursor=cursor,
                        raw_session_id=normalized_session_id,
                        raw_session=raw_session,
                    )

                _delete_stale_sessions_cursor(
                    cursor=cursor,
                    active_session_ids=active_session_ids,
                )
                conn.commit()

        run_sqlite_with_retry(
            _save_sessions,
            max_retries=_SQLITE_RETRY_ATTEMPTS,
            retry_delay_seconds=_SQLITE_RETRY_DELAY_SECONDS,
        )
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
    db_path_text = str(db_path)

    try:
        raw_session_id = str(session.get("id") or "")
        if not raw_session_id:
            return False

        def _upsert_session() -> None:
            with connect_sqlite(
                db_path_text,
                timeout_seconds=_SQLITE_TIMEOUT_SECONDS,
                pragmas=_SQLITE_PRAGMAS,
            ) as conn:
                cursor = conn.cursor()
                _ensure_message_table_accessible_cursor(cursor=cursor)
                _upsert_history_session_with_messages_delta_cursor(
                    cursor=cursor,
                    raw_session_id=raw_session_id,
                    raw_session=session,
                )
                conn.commit()

        run_sqlite_with_retry(
            _upsert_session,
            max_retries=_SQLITE_RETRY_ATTEMPTS,
            retry_delay_seconds=_SQLITE_RETRY_DELAY_SECONDS,
        )
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
    db_path_text = str(db_path)

    try:
        def _apply_deltas() -> bool:
            with connect_sqlite(
                db_path_text,
                timeout_seconds=_SQLITE_TIMEOUT_SECONDS,
                pragmas=_SQLITE_PRAGMAS,
            ) as conn:
                cursor = conn.cursor()
                _ensure_message_table_accessible_cursor(cursor=cursor)
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

        return bool(
            run_sqlite_with_retry(
                _apply_deltas,
                max_retries=_SQLITE_RETRY_ATTEMPTS,
                retry_delay_seconds=_SQLITE_RETRY_DELAY_SECONDS,
            )
        )
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
    db_path_text = str(db_path)
    try:
        def _delete_session() -> None:
            with connect_sqlite(
                db_path_text,
                timeout_seconds=_SQLITE_TIMEOUT_SECONDS,
                pragmas=_SQLITE_PRAGMAS,
            ) as conn:
                conn.execute(
                    """
                    DELETE FROM chatbot_sessions
                    WHERE session_id = ?
                    """,
                    (session_id,),
                )
                conn.commit()

        run_sqlite_with_retry(
            _delete_session,
            max_retries=_SQLITE_RETRY_ATTEMPTS,
            retry_delay_seconds=_SQLITE_RETRY_DELAY_SECONDS,
        )
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
    db_path_text = str(db_path)
    try:
        def _clear_sessions() -> None:
            with connect_sqlite(
                db_path_text,
                timeout_seconds=_SQLITE_TIMEOUT_SECONDS,
                pragmas=_SQLITE_PRAGMAS,
            ) as conn:
                _clear_all_sessions_cursor(cursor=conn.cursor())
                conn.commit()

        run_sqlite_with_retry(
            _clear_sessions,
            max_retries=_SQLITE_RETRY_ATTEMPTS,
            retry_delay_seconds=_SQLITE_RETRY_DELAY_SECONDS,
        )
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
