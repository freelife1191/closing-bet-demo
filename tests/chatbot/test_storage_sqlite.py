#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
챗봇 SQLite 저장소 회귀 테스트
"""

import json
import os
import sqlite3
import sys
import threading
import time
from pathlib import Path


sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

import chatbot.core as chatbot_core
import chatbot.storage_sqlite_history as storage_sqlite_history
import chatbot.storage_sqlite_memory as storage_sqlite_memory
import chatbot.storage_sqlite_common as sqlite_common
from chatbot.storage_sqlite_helpers import (
    apply_history_session_deltas_in_sqlite,
    clear_history_sessions_in_sqlite,
    load_history_sessions_from_sqlite,
    load_memories_from_sqlite,
    resolve_chatbot_storage_db_path,
    save_history_sessions_to_sqlite,
    save_memories_to_sqlite,
)


def _count_rows(db_path: Path, table: str) -> int:
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
    return int(row[0]) if row else 0


def _is_full_table_delete(sql: str, *, table: str) -> bool:
    normalized = " ".join(str(sql).strip().split()).upper()
    return normalized == f"DELETE FROM {table.upper()}"


def test_history_manager_persists_and_restores_from_sqlite(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(chatbot_core, "DATA_DIR", tmp_path)

    manager = chatbot_core.HistoryManager(user_id="u1")
    session_id = manager.create_session(owner_id="owner-a")
    manager.add_message(session_id, "user", "첫 질문")
    manager.add_message(session_id, "model", "첫 응답")

    db_path = resolve_chatbot_storage_db_path(tmp_path)
    assert db_path.exists()
    assert _count_rows(db_path, "chatbot_sessions") == 1
    assert _count_rows(db_path, "chatbot_messages") == 2

    history_file = tmp_path / "chatbot_history.json"
    if history_file.exists():
        history_file.unlink()

    restored = chatbot_core.HistoryManager(user_id="u2")
    messages = restored.get_messages(session_id)

    assert len(messages) == 2
    assert messages[0]["role"] == "user"
    assert messages[0]["parts"][0]["text"] == "첫 질문"


def test_history_manager_migrates_legacy_json_into_sqlite(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(chatbot_core, "DATA_DIR", tmp_path)

    session_id = "legacy-session"
    legacy_payload = {
        session_id: {
            "id": session_id,
            "title": "레거시 세션",
            "messages": [
                {
                    "role": "user",
                    "parts": [{"text": "레거시 질문"}],
                    "timestamp": "2026-02-22T00:00:00",
                }
            ],
            "created_at": "2026-02-22T00:00:00",
            "updated_at": "2026-02-22T00:00:00",
            "model": "gemini-2.0-flash-lite",
            "owner_id": "owner-legacy",
        }
    }
    (tmp_path / "chatbot_history.json").write_text(
        json.dumps(legacy_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    manager = chatbot_core.HistoryManager(user_id="u1")
    session = manager.get_session(session_id)

    assert session is not None
    assert session["owner_id"] == "owner-legacy"

    db_path = resolve_chatbot_storage_db_path(tmp_path)
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            """
            SELECT COUNT(*) FROM chatbot_sessions WHERE session_id = ?
            """,
            (session_id,),
        ).fetchone()
    assert row and int(row[0]) == 1


def test_memory_manager_persists_and_restores_from_sqlite(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(chatbot_core, "DATA_DIR", tmp_path)

    memory = chatbot_core.MemoryManager(user_id="u1")
    memory.add("risk", "aggressive")

    db_path = resolve_chatbot_storage_db_path(tmp_path)
    assert db_path.exists()
    assert _count_rows(db_path, "chatbot_memories") == 1

    memory_file = tmp_path / "chatbot_memory.json"
    if memory_file.exists():
        memory_file.unlink()

    restored = chatbot_core.MemoryManager(user_id="u2")
    assert restored.get("risk")["value"] == "aggressive"


def test_apply_history_session_deltas_updates_and_deletes(tmp_path: Path):
    db_path = resolve_chatbot_storage_db_path(tmp_path)
    baseline_sessions = {
        "s1": {
            "id": "s1",
            "title": "세션1",
            "messages": [{"role": "user", "parts": [{"text": "a"}], "timestamp": "2026-02-22T00:00:00"}],
            "created_at": "2026-02-22T00:00:00",
            "updated_at": "2026-02-22T00:00:00",
            "model": "gemini-2.0-flash-lite",
            "owner_id": "owner-a",
        },
        "s2": {
            "id": "s2",
            "title": "세션2",
            "messages": [{"role": "user", "parts": [{"text": "b"}], "timestamp": "2026-02-22T00:00:00"}],
            "created_at": "2026-02-22T00:00:00",
            "updated_at": "2026-02-22T00:00:00",
            "model": "gemini-2.0-flash-lite",
            "owner_id": "owner-b",
        },
    }
    assert save_history_sessions_to_sqlite(db_path, baseline_sessions, chatbot_core.logger) is True

    updated_sessions = dict(baseline_sessions)
    updated_sessions["s1"] = {
        **baseline_sessions["s1"],
        "updated_at": "2026-02-23T00:00:00",
        "messages": [
            {"role": "user", "parts": [{"text": "a"}], "timestamp": "2026-02-22T00:00:00"},
            {"role": "model", "parts": [{"text": "a-답변"}], "timestamp": "2026-02-23T00:00:00"},
        ],
    }

    assert (
        apply_history_session_deltas_in_sqlite(
            db_path,
            sessions=updated_sessions,
            changed_session_ids={"s1"},
            deleted_session_ids={"s2"},
            clear_all=False,
            logger=chatbot_core.logger,
        )
        is True
    )

    with sqlite3.connect(db_path) as conn:
        remaining_sessions = int(conn.execute("SELECT COUNT(*) FROM chatbot_sessions").fetchone()[0])
        remaining_messages = int(conn.execute("SELECT COUNT(*) FROM chatbot_messages").fetchone()[0])
        s1_message_count = int(
            conn.execute("SELECT COUNT(*) FROM chatbot_messages WHERE session_id = ?", ("s1",)).fetchone()[0]
        )

    assert remaining_sessions == 1
    assert remaining_messages == 2
    assert s1_message_count == 2


def test_apply_history_session_deltas_clear_all(monkeypatch, tmp_path: Path):
    db_path = resolve_chatbot_storage_db_path(tmp_path)
    baseline_sessions = {
        "s1": {
            "id": "s1",
            "title": "세션1",
            "messages": [{"role": "user", "parts": [{"text": "a"}], "timestamp": "2026-02-22T00:00:00"}],
            "created_at": "2026-02-22T00:00:00",
            "updated_at": "2026-02-22T00:00:00",
            "model": "gemini-2.0-flash-lite",
            "owner_id": "owner-a",
        }
    }
    assert save_history_sessions_to_sqlite(db_path, baseline_sessions, chatbot_core.logger) is True
    traced_sql: list[str] = []
    original_connect = storage_sqlite_history.connect_sqlite

    def _traced_connect(*args, **kwargs):
        conn = original_connect(*args, **kwargs)
        conn.set_trace_callback(traced_sql.append)
        return conn

    monkeypatch.setattr(storage_sqlite_history, "connect_sqlite", _traced_connect)

    assert (
        apply_history_session_deltas_in_sqlite(
            db_path,
            sessions={},
            changed_session_ids=set(),
            deleted_session_ids=set(),
            clear_all=True,
            logger=chatbot_core.logger,
        )
        is True
    )

    assert _count_rows(db_path, "chatbot_sessions") == 0
    assert _count_rows(db_path, "chatbot_messages") == 0
    assert any("DELETE FROM chatbot_sessions" in sql for sql in traced_sql)
    assert not any("DELETE FROM chatbot_messages" in sql for sql in traced_sql)


def test_save_history_sessions_uses_session_delete_only(monkeypatch, tmp_path: Path):
    db_path = resolve_chatbot_storage_db_path(tmp_path)
    sessions = {
        "s1": {
            "id": "s1",
            "title": "세션1",
            "messages": [{"role": "user", "parts": [{"text": "a"}], "timestamp": "2026-02-22T00:00:00"}],
            "created_at": "2026-02-22T00:00:00",
            "updated_at": "2026-02-22T00:00:00",
            "model": "gemini-2.0-flash-lite",
            "owner_id": "owner-a",
        }
    }
    assert save_history_sessions_to_sqlite(db_path, sessions, chatbot_core.logger) is True

    traced_sql: list[str] = []
    original_connect = storage_sqlite_history.connect_sqlite

    def _traced_connect(*args, **kwargs):
        conn = original_connect(*args, **kwargs)
        conn.set_trace_callback(traced_sql.append)
        return conn

    monkeypatch.setattr(storage_sqlite_history, "connect_sqlite", _traced_connect)

    assert save_history_sessions_to_sqlite(db_path, sessions, chatbot_core.logger) is True
    assert any("DELETE FROM chatbot_sessions" in sql for sql in traced_sql)
    assert not any("DELETE FROM chatbot_messages" in sql for sql in traced_sql)


def test_save_history_sessions_syncs_snapshot_without_full_clear(monkeypatch, tmp_path: Path):
    db_path = resolve_chatbot_storage_db_path(tmp_path)
    baseline_sessions = {
        "s1": {
            "id": "s1",
            "title": "세션1",
            "messages": [{"role": "user", "parts": [{"text": "a"}], "timestamp": "2026-02-22T00:00:00"}],
            "created_at": "2026-02-22T00:00:00",
            "updated_at": "2026-02-22T00:00:00",
            "model": "gemini-2.0-flash-lite",
            "owner_id": "owner-a",
        },
        "s2": {
            "id": "s2",
            "title": "세션2",
            "messages": [{"role": "user", "parts": [{"text": "b"}], "timestamp": "2026-02-22T00:00:00"}],
            "created_at": "2026-02-22T00:00:00",
            "updated_at": "2026-02-22T00:00:00",
            "model": "gemini-2.0-flash-lite",
            "owner_id": "owner-b",
        },
    }
    assert save_history_sessions_to_sqlite(db_path, baseline_sessions, chatbot_core.logger) is True

    traced_sql: list[str] = []
    original_connect = storage_sqlite_history.connect_sqlite

    def _traced_connect(*args, **kwargs):
        conn = original_connect(*args, **kwargs)
        conn.set_trace_callback(traced_sql.append)
        return conn

    monkeypatch.setattr(storage_sqlite_history, "connect_sqlite", _traced_connect)

    next_snapshot = {"s1": baseline_sessions["s1"]}
    assert save_history_sessions_to_sqlite(db_path, next_snapshot, chatbot_core.logger) is True

    assert _count_rows(db_path, "chatbot_sessions") == 1
    assert _count_rows(db_path, "chatbot_messages") == 1
    assert any("DELETE FROM chatbot_sessions" in sql for sql in traced_sql)
    assert not any(_is_full_table_delete(sql, table="chatbot_sessions") for sql in traced_sql)
    assert not any(
        "CREATE TEMP TABLE IF NOT EXISTS _tmp_chatbot_session_ids" in sql
        for sql in traced_sql
    )


def test_save_history_sessions_uses_temp_table_fallback_for_large_snapshot(monkeypatch, tmp_path: Path):
    db_path = resolve_chatbot_storage_db_path(tmp_path)
    baseline_sessions = {
        "s1": {
            "id": "s1",
            "title": "세션1",
            "messages": [{"role": "user", "parts": [{"text": "a"}], "timestamp": "2026-02-22T00:00:00"}],
            "created_at": "2026-02-22T00:00:00",
            "updated_at": "2026-02-22T00:00:00",
            "model": "gemini-2.0-flash-lite",
            "owner_id": "owner-a",
        },
        "s2": {
            "id": "s2",
            "title": "세션2",
            "messages": [{"role": "user", "parts": [{"text": "b"}], "timestamp": "2026-02-22T00:00:00"}],
            "created_at": "2026-02-22T00:00:00",
            "updated_at": "2026-02-22T00:00:00",
            "model": "gemini-2.0-flash-lite",
            "owner_id": "owner-b",
        },
        "s3": {
            "id": "s3",
            "title": "세션3",
            "messages": [{"role": "user", "parts": [{"text": "c"}], "timestamp": "2026-02-22T00:00:00"}],
            "created_at": "2026-02-22T00:00:00",
            "updated_at": "2026-02-22T00:00:00",
            "model": "gemini-2.0-flash-lite",
            "owner_id": "owner-c",
        },
    }
    assert save_history_sessions_to_sqlite(db_path, baseline_sessions, chatbot_core.logger) is True

    traced_sql: list[str] = []
    original_connect = storage_sqlite_history.connect_sqlite

    def _traced_connect(*args, **kwargs):
        conn = original_connect(*args, **kwargs)
        conn.set_trace_callback(traced_sql.append)
        return conn

    monkeypatch.setattr(storage_sqlite_history, "connect_sqlite", _traced_connect)
    monkeypatch.setattr(storage_sqlite_history, "_SQLITE_INLINE_DELETE_MAX_VARIABLES", 1)

    next_snapshot = {
        "s1": baseline_sessions["s1"],
        "s2": baseline_sessions["s2"],
    }
    assert save_history_sessions_to_sqlite(db_path, next_snapshot, chatbot_core.logger) is True

    assert any(
        "CREATE TEMP TABLE IF NOT EXISTS _tmp_chatbot_session_ids" in sql
        for sql in traced_sql
    )


def test_clear_history_sessions_uses_session_delete_only(monkeypatch, tmp_path: Path):
    db_path = resolve_chatbot_storage_db_path(tmp_path)
    sessions = {
        "s1": {
            "id": "s1",
            "title": "세션1",
            "messages": [{"role": "user", "parts": [{"text": "a"}], "timestamp": "2026-02-22T00:00:00"}],
            "created_at": "2026-02-22T00:00:00",
            "updated_at": "2026-02-22T00:00:00",
            "model": "gemini-2.0-flash-lite",
            "owner_id": "owner-a",
        }
    }
    assert save_history_sessions_to_sqlite(db_path, sessions, chatbot_core.logger) is True

    traced_sql: list[str] = []
    original_connect = storage_sqlite_history.connect_sqlite

    def _traced_connect(*args, **kwargs):
        conn = original_connect(*args, **kwargs)
        conn.set_trace_callback(traced_sql.append)
        return conn

    monkeypatch.setattr(storage_sqlite_history, "connect_sqlite", _traced_connect)

    assert clear_history_sessions_in_sqlite(db_path, chatbot_core.logger) is True
    assert _count_rows(db_path, "chatbot_sessions") == 0
    assert _count_rows(db_path, "chatbot_messages") == 0
    assert any("DELETE FROM chatbot_sessions" in sql for sql in traced_sql)
    assert not any("DELETE FROM chatbot_messages" in sql for sql in traced_sql)


def _install_message_delete_audit_trigger(db_path: Path) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS message_delete_audit (
                deleted_count INTEGER NOT NULL
            )
            """
        )
        conn.execute("DELETE FROM message_delete_audit")
        conn.execute("INSERT INTO message_delete_audit(deleted_count) VALUES (0)")
        conn.execute(
            """
            CREATE TRIGGER IF NOT EXISTS trg_chatbot_messages_delete_audit
            AFTER DELETE ON chatbot_messages
            BEGIN
                UPDATE message_delete_audit
                SET deleted_count = deleted_count + 1;
            END;
            """
        )
        conn.commit()


def _read_message_delete_audit_count(db_path: Path) -> int:
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT deleted_count FROM message_delete_audit LIMIT 1"
        ).fetchone()
    return int(row[0]) if row else 0


def _install_session_update_audit_trigger(db_path: Path) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS session_update_audit (
                updated_count INTEGER NOT NULL
            )
            """
        )
        conn.execute("DELETE FROM session_update_audit")
        conn.execute("INSERT INTO session_update_audit(updated_count) VALUES (0)")
        conn.execute(
            """
            CREATE TRIGGER IF NOT EXISTS trg_chatbot_sessions_update_audit
            AFTER UPDATE ON chatbot_sessions
            BEGIN
                UPDATE session_update_audit
                SET updated_count = updated_count + 1;
            END;
            """
        )
        conn.commit()


def _read_session_update_audit_count(db_path: Path) -> int:
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT updated_count FROM session_update_audit LIMIT 1"
        ).fetchone()
    return int(row[0]) if row else 0


def _install_memory_update_audit_trigger(db_path: Path) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS memory_update_audit (
                updated_count INTEGER NOT NULL
            )
            """
        )
        conn.execute("DELETE FROM memory_update_audit")
        conn.execute("INSERT INTO memory_update_audit(updated_count) VALUES (0)")
        conn.execute(
            """
            CREATE TRIGGER IF NOT EXISTS trg_chatbot_memories_update_audit
            AFTER UPDATE ON chatbot_memories
            BEGIN
                UPDATE memory_update_audit
                SET updated_count = updated_count + 1;
            END;
            """
        )
        conn.commit()


def _read_memory_update_audit_count(db_path: Path) -> int:
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT updated_count FROM memory_update_audit LIMIT 1"
        ).fetchone()
    return int(row[0]) if row else 0


def test_apply_history_session_deltas_append_only_skips_message_delete(monkeypatch, tmp_path: Path):
    db_path = resolve_chatbot_storage_db_path(tmp_path)
    baseline_sessions = {
        "s1": {
            "id": "s1",
            "title": "세션1",
            "messages": [
                {"role": "user", "parts": [{"text": "a"}], "timestamp": "2026-02-22T00:00:00"},
                {"role": "model", "parts": [{"text": "b"}], "timestamp": "2026-02-22T00:00:01"},
            ],
            "created_at": "2026-02-22T00:00:00",
            "updated_at": "2026-02-22T00:00:01",
            "model": "gemini-2.0-flash-lite",
            "owner_id": "owner-a",
        }
    }
    assert save_history_sessions_to_sqlite(db_path, baseline_sessions, chatbot_core.logger) is True
    _install_message_delete_audit_trigger(db_path)
    traced_sql: list[str] = []
    original_connect = storage_sqlite_history.connect_sqlite

    def _traced_connect(*args, **kwargs):
        conn = original_connect(*args, **kwargs)
        conn.set_trace_callback(traced_sql.append)
        return conn

    monkeypatch.setattr(storage_sqlite_history, "connect_sqlite", _traced_connect)

    updated_sessions = {
        "s1": {
            **baseline_sessions["s1"],
            "updated_at": "2026-02-22T00:00:02",
            "messages": [
                {"role": "user", "parts": [{"text": "a"}], "timestamp": "2026-02-22T00:00:00"},
                {"role": "model", "parts": [{"text": "b"}], "timestamp": "2026-02-22T00:00:01"},
                {"role": "user", "parts": [{"text": "c"}], "timestamp": "2026-02-22T00:00:02"},
            ],
        }
    }

    assert (
        apply_history_session_deltas_in_sqlite(
            db_path,
            sessions=updated_sessions,
            changed_session_ids={"s1"},
            deleted_session_ids=set(),
            clear_all=False,
            logger=chatbot_core.logger,
        )
        is True
    )

    assert _read_message_delete_audit_count(db_path) == 0
    assert _count_rows(db_path, "chatbot_messages") == 3
    assert not any("SELECT COUNT(*) FROM chatbot_messages" in sql for sql in traced_sql)


def test_apply_history_session_deltas_non_append_falls_back_to_rewrite(tmp_path: Path):
    db_path = resolve_chatbot_storage_db_path(tmp_path)
    baseline_sessions = {
        "s1": {
            "id": "s1",
            "title": "세션1",
            "messages": [
                {"role": "user", "parts": [{"text": "a"}], "timestamp": "2026-02-22T00:00:00"},
                {"role": "model", "parts": [{"text": "b"}], "timestamp": "2026-02-22T00:00:01"},
            ],
            "created_at": "2026-02-22T00:00:00",
            "updated_at": "2026-02-22T00:00:01",
            "model": "gemini-2.0-flash-lite",
            "owner_id": "owner-a",
        }
    }
    assert save_history_sessions_to_sqlite(db_path, baseline_sessions, chatbot_core.logger) is True
    _install_message_delete_audit_trigger(db_path)

    updated_sessions = {
        "s1": {
            **baseline_sessions["s1"],
            "updated_at": "2026-02-22T00:00:03",
            "messages": [
                {"role": "user", "parts": [{"text": "a-수정"}], "timestamp": "2026-02-22T00:00:03"},
                {"role": "model", "parts": [{"text": "b"}], "timestamp": "2026-02-22T00:00:01"},
            ],
        }
    }

    assert (
        apply_history_session_deltas_in_sqlite(
            db_path,
            sessions=updated_sessions,
            changed_session_ids={"s1"},
            deleted_session_ids=set(),
            clear_all=False,
            logger=chatbot_core.logger,
        )
        is True
    )

    assert _read_message_delete_audit_count(db_path) > 0
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            """
            SELECT parts_json
            FROM chatbot_messages
            WHERE session_id = 's1' AND message_index = 0
            """
        ).fetchone()
    assert row is not None
    assert "a-수정" in str(row[0])


def test_apply_history_session_deltas_metadata_only_update_skips_message_rewrite(monkeypatch, tmp_path: Path):
    db_path = resolve_chatbot_storage_db_path(tmp_path)
    baseline_sessions = {
        "s1": {
            "id": "s1",
            "title": "원본 제목",
            "messages": [
                {"role": "user", "parts": [{"text": "a"}], "timestamp": "2026-02-22T00:00:00"},
                {"role": "model", "parts": [{"text": "b"}], "timestamp": "2026-02-22T00:00:01"},
            ],
            "created_at": "2026-02-22T00:00:00",
            "updated_at": "2026-02-22T00:00:01",
            "model": "gemini-2.0-flash-lite",
            "owner_id": "owner-a",
        }
    }
    assert save_history_sessions_to_sqlite(db_path, baseline_sessions, chatbot_core.logger) is True
    _install_message_delete_audit_trigger(db_path)
    traced_sql: list[str] = []
    original_connect = storage_sqlite_history.connect_sqlite

    def _traced_connect(*args, **kwargs):
        conn = original_connect(*args, **kwargs)
        conn.set_trace_callback(traced_sql.append)
        return conn

    monkeypatch.setattr(storage_sqlite_history, "connect_sqlite", _traced_connect)

    metadata_only_sessions = {
        "s1": {
            **baseline_sessions["s1"],
            "title": "변경된 제목",
            "updated_at": "2026-02-22T00:00:02",
        }
    }
    assert (
        apply_history_session_deltas_in_sqlite(
            db_path,
            sessions=metadata_only_sessions,
            changed_session_ids={"s1"},
            deleted_session_ids=set(),
            clear_all=False,
            logger=chatbot_core.logger,
        )
        is True
    )

    assert _read_message_delete_audit_count(db_path) == 0
    assert _count_rows(db_path, "chatbot_messages") == 2
    assert not any("DELETE FROM chatbot_messages" in sql for sql in traced_sql)
    assert not any("INSERT INTO chatbot_messages" in sql for sql in traced_sql)


def test_ensure_chatbot_storage_schema_skips_redundant_init(monkeypatch, tmp_path: Path):
    db_path = resolve_chatbot_storage_db_path(tmp_path)

    original_connect = sqlite_common.connect_sqlite
    connect_calls = {"count": 0}

    def _counted_connect(*args, **kwargs):
        connect_calls["count"] += 1
        return original_connect(*args, **kwargs)

    monkeypatch.setattr(sqlite_common, "connect_sqlite", _counted_connect)

    assert sqlite_common.ensure_chatbot_storage_schema(db_path, chatbot_core.logger) is True
    assert sqlite_common.ensure_chatbot_storage_schema(db_path, chatbot_core.logger) is True
    assert connect_calls["count"] == 1


def test_ensure_chatbot_storage_schema_reinitializes_after_db_removed(monkeypatch, tmp_path: Path):
    db_path = resolve_chatbot_storage_db_path(tmp_path)

    original_connect = sqlite_common.connect_sqlite
    connect_calls = {"count": 0}

    def _counted_connect(*args, **kwargs):
        connect_calls["count"] += 1
        return original_connect(*args, **kwargs)

    monkeypatch.setattr(sqlite_common, "connect_sqlite", _counted_connect)

    assert sqlite_common.ensure_chatbot_storage_schema(db_path, chatbot_core.logger) is True
    db_path.unlink()
    assert sqlite_common.ensure_chatbot_storage_schema(db_path, chatbot_core.logger) is True
    assert connect_calls["count"] == 2


def test_ensure_chatbot_storage_schema_deduplicates_concurrent_initialization(monkeypatch, tmp_path: Path):
    db_path = resolve_chatbot_storage_db_path(tmp_path)

    original_connect = sqlite_common.connect_sqlite
    connect_calls = {"count": 0}
    connect_calls_lock = threading.Lock()
    first_connect_entered = threading.Event()

    def _slow_counted_connect(*args, **kwargs):
        with connect_calls_lock:
            connect_calls["count"] += 1
            call_index = connect_calls["count"]
        if call_index == 1:
            first_connect_entered.set()
            time.sleep(0.05)
        return original_connect(*args, **kwargs)

    monkeypatch.setattr(sqlite_common, "connect_sqlite", _slow_counted_connect)

    first_result: list[bool] = []
    second_result: list[bool] = []

    thread_first = threading.Thread(
        target=lambda: first_result.append(
            sqlite_common.ensure_chatbot_storage_schema(db_path, chatbot_core.logger)
        )
    )
    thread_first.start()
    assert first_connect_entered.wait(timeout=1.0)

    thread_second = threading.Thread(
        target=lambda: second_result.append(
            sqlite_common.ensure_chatbot_storage_schema(db_path, chatbot_core.logger)
        )
    )
    thread_second.start()

    thread_first.join(timeout=2.0)
    thread_second.join(timeout=2.0)

    assert first_result == [True]
    assert second_result == [True]
    assert connect_calls["count"] == 1


def test_ensure_chatbot_storage_schema_waiter_retries_after_initializer_failure(
    monkeypatch,
    tmp_path: Path,
):
    db_path = resolve_chatbot_storage_db_path(tmp_path)
    with sqlite_common._SCHEMA_READY_LOCK:
        sqlite_common._SCHEMA_READY_DB_PATHS.clear()
        sqlite_common._SCHEMA_INIT_IN_PROGRESS.clear()

    monkeypatch.setattr(sqlite_common, "sqlite_db_path_exists", lambda _path: True)

    entered_event = threading.Event()
    release_event = threading.Event()
    run_calls = {"count": 0}

    def _fail_then_succeed(_operation, *, max_retries, retry_delay_seconds):
        run_calls["count"] += 1
        if run_calls["count"] == 1:
            entered_event.set()
            assert release_event.wait(timeout=2.0)
            raise sqlite3.OperationalError("forced init failure")
        return None

    monkeypatch.setattr(sqlite_common, "run_sqlite_with_retry", _fail_then_succeed)

    first_result: list[bool] = []
    second_result: list[bool] = []

    thread_first = threading.Thread(
        target=lambda: first_result.append(
            sqlite_common.ensure_chatbot_storage_schema(db_path, chatbot_core.logger)
        )
    )
    thread_second = threading.Thread(
        target=lambda: second_result.append(
            sqlite_common.ensure_chatbot_storage_schema(db_path, chatbot_core.logger)
        )
    )

    thread_first.start()
    assert entered_event.wait(timeout=2.0)
    thread_second.start()
    time.sleep(0.05)
    assert run_calls["count"] == 1

    release_event.set()
    thread_first.join(timeout=2.0)
    thread_second.join(timeout=2.0)

    assert thread_first.is_alive() is False
    assert thread_second.is_alive() is False
    assert run_calls["count"] == 2
    assert first_result == [False]
    assert second_result == [True]


def test_ensure_chatbot_storage_schema_normalizes_relative_db_key(monkeypatch, tmp_path: Path):
    db_path = resolve_chatbot_storage_db_path(tmp_path)
    relative_db_path = Path("chatbot_storage.db")

    original_connect = sqlite_common.connect_sqlite
    connect_calls = {"count": 0}

    def _counted_connect(*args, **kwargs):
        connect_calls["count"] += 1
        return original_connect(*args, **kwargs)

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sqlite_common, "connect_sqlite", _counted_connect)

    assert sqlite_common.ensure_chatbot_storage_schema(db_path, chatbot_core.logger) is True
    assert sqlite_common.ensure_chatbot_storage_schema(relative_db_path, chatbot_core.logger) is True
    assert connect_calls["count"] == 1


def test_ensure_chatbot_storage_schema_migrates_messages_hash_column(tmp_path: Path):
    db_path = resolve_chatbot_storage_db_path(tmp_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(db_path) as conn:
        conn.executescript(
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
            """
        )
        conn.execute(
            """
            INSERT INTO chatbot_sessions (
                session_id, title, created_at, updated_at, model_name, owner_id
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            ("legacy", "레거시", "2026-02-22T00:00:00", "2026-02-22T00:00:00", "gemini-2.0-flash-lite", "owner-a"),
        )
        conn.commit()

    assert sqlite_common.ensure_chatbot_storage_schema(db_path, chatbot_core.logger, force_recheck=True) is True

    with sqlite3.connect(db_path) as conn:
        columns = {str(row[1]) for row in conn.execute("PRAGMA table_info(chatbot_sessions)").fetchall()}
        row = conn.execute(
            """
            SELECT messages_hash
            FROM chatbot_sessions
            WHERE session_id = 'legacy'
            """
        ).fetchone()

    assert "messages_hash" in columns
    assert row is not None
    assert row[0] == ""


def test_ensure_chatbot_storage_schema_drops_redundant_chatbot_messages_index(tmp_path: Path):
    db_path = resolve_chatbot_storage_db_path(tmp_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(db_path) as conn:
        conn.executescript(
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
            CREATE INDEX IF NOT EXISTS idx_chatbot_messages_session_idx
            ON chatbot_messages(session_id, message_index);
            """
        )
        conn.commit()

    assert sqlite_common.ensure_chatbot_storage_schema(db_path, chatbot_core.logger, force_recheck=True) is True

    with sqlite3.connect(db_path) as conn:
        index_row = conn.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'index' AND name = 'idx_chatbot_messages_session_idx'
            """
        ).fetchone()

    assert index_row is None


def test_load_history_sessions_retries_on_transient_sqlite_lock(monkeypatch, tmp_path: Path):
    db_path = resolve_chatbot_storage_db_path(tmp_path)
    sessions = {
        "s1": {
            "id": "s1",
            "title": "세션1",
            "messages": [{"role": "user", "parts": [{"text": "a"}], "timestamp": "2026-02-22T00:00:00"}],
            "created_at": "2026-02-22T00:00:00",
            "updated_at": "2026-02-22T00:00:00",
            "model": "gemini-2.0-flash-lite",
            "owner_id": "owner-a",
        }
    }
    assert save_history_sessions_to_sqlite(db_path, sessions, chatbot_core.logger) is True

    original_connect = storage_sqlite_history.connect_sqlite
    failure_state = {"failed": False}

    def _flaky_connect(*args, **kwargs):
        if not failure_state["failed"]:
            failure_state["failed"] = True
            raise sqlite3.OperationalError("database is locked")
        return original_connect(*args, **kwargs)

    monkeypatch.setattr(storage_sqlite_history, "connect_sqlite", _flaky_connect)
    loaded = load_history_sessions_from_sqlite(db_path, chatbot_core.logger)

    assert failure_state["failed"] is True
    assert loaded is not None
    assert loaded["s1"]["title"] == "세션1"


def test_load_memories_retries_on_transient_sqlite_lock(monkeypatch, tmp_path: Path):
    db_path = resolve_chatbot_storage_db_path(tmp_path)
    memories = {
        "risk": {
            "value": "aggressive",
            "updated_at": "2026-02-22T00:00:00",
        }
    }
    assert save_memories_to_sqlite(db_path, memories, chatbot_core.logger) is True

    original_connect = storage_sqlite_memory.connect_sqlite
    failure_state = {"failed": False}

    def _flaky_connect(*args, **kwargs):
        if not failure_state["failed"]:
            failure_state["failed"] = True
            raise sqlite3.OperationalError("database is locked")
        return original_connect(*args, **kwargs)

    monkeypatch.setattr(storage_sqlite_memory, "connect_sqlite", _flaky_connect)
    loaded = load_memories_from_sqlite(db_path, chatbot_core.logger)

    assert failure_state["failed"] is True
    assert loaded is not None
    assert loaded["risk"]["value"] == "aggressive"


def test_load_history_sessions_uses_read_only_connection(monkeypatch, tmp_path: Path):
    db_path = resolve_chatbot_storage_db_path(tmp_path)
    sessions = {
        "s1": {
            "id": "s1",
            "title": "세션1",
            "messages": [{"role": "user", "parts": [{"text": "a"}], "timestamp": "2026-02-22T00:00:00"}],
            "created_at": "2026-02-22T00:00:00",
            "updated_at": "2026-02-22T00:00:00",
            "model": "gemini-2.0-flash-lite",
            "owner_id": "owner-a",
        }
    }
    assert save_history_sessions_to_sqlite(db_path, sessions, chatbot_core.logger) is True

    read_only_flags: list[bool] = []
    original_connect = storage_sqlite_history.connect_sqlite

    def _traced_connect(*args, **kwargs):
        if "read_only" in kwargs:
            read_only_flags.append(bool(kwargs["read_only"]))
        return original_connect(*args, **kwargs)

    monkeypatch.setattr(storage_sqlite_history, "connect_sqlite", _traced_connect)

    loaded = load_history_sessions_from_sqlite(db_path, chatbot_core.logger)
    assert loaded is not None
    assert loaded["s1"]["title"] == "세션1"
    assert True in read_only_flags


def test_load_memories_uses_read_only_connection(monkeypatch, tmp_path: Path):
    db_path = resolve_chatbot_storage_db_path(tmp_path)
    memories = {
        "risk": {
            "value": "aggressive",
            "updated_at": "2026-02-22T00:00:00",
        }
    }
    assert save_memories_to_sqlite(db_path, memories, chatbot_core.logger) is True

    read_only_flags: list[bool] = []
    original_connect = storage_sqlite_memory.connect_sqlite

    def _traced_connect(*args, **kwargs):
        if "read_only" in kwargs:
            read_only_flags.append(bool(kwargs["read_only"]))
        return original_connect(*args, **kwargs)

    monkeypatch.setattr(storage_sqlite_memory, "connect_sqlite", _traced_connect)

    loaded = load_memories_from_sqlite(db_path, chatbot_core.logger)
    assert loaded is not None
    assert loaded["risk"]["value"] == "aggressive"
    assert True in read_only_flags


def test_save_memories_uses_upsert_and_stale_cleanup_without_full_clear(monkeypatch, tmp_path: Path):
    db_path = resolve_chatbot_storage_db_path(tmp_path)
    baseline_memories = {
        "risk": {"value": "aggressive", "updated_at": "2026-02-22T00:00:00"},
        "style": {"value": "momentum", "updated_at": "2026-02-22T00:00:00"},
    }
    assert save_memories_to_sqlite(db_path, baseline_memories, chatbot_core.logger) is True

    traced_sql: list[str] = []
    original_connect = storage_sqlite_memory.connect_sqlite

    def _traced_connect(*args, **kwargs):
        conn = original_connect(*args, **kwargs)
        conn.set_trace_callback(traced_sql.append)
        return conn

    monkeypatch.setattr(storage_sqlite_memory, "connect_sqlite", _traced_connect)

    next_snapshot = {
        "risk": {"value": "conservative", "updated_at": "2026-02-23T00:00:00"},
    }
    assert save_memories_to_sqlite(db_path, next_snapshot, chatbot_core.logger) is True

    loaded = load_memories_from_sqlite(db_path, chatbot_core.logger)
    assert loaded is not None
    assert set(loaded.keys()) == {"risk"}
    assert loaded["risk"]["value"] == "conservative"
    assert not any(_is_full_table_delete(sql, table="chatbot_memories") for sql in traced_sql)
    assert not any(
        "CREATE TEMP TABLE IF NOT EXISTS _tmp_chatbot_memory_keys" in sql
        for sql in traced_sql
    )


def test_save_memories_uses_temp_table_fallback_for_large_snapshot(monkeypatch, tmp_path: Path):
    db_path = resolve_chatbot_storage_db_path(tmp_path)
    baseline_memories = {
        "risk": {"value": "aggressive", "updated_at": "2026-02-22T00:00:00"},
        "style": {"value": "momentum", "updated_at": "2026-02-22T00:00:00"},
        "horizon": {"value": "swing", "updated_at": "2026-02-22T00:00:00"},
    }
    assert save_memories_to_sqlite(db_path, baseline_memories, chatbot_core.logger) is True

    traced_sql: list[str] = []
    original_connect = storage_sqlite_memory.connect_sqlite

    def _traced_connect(*args, **kwargs):
        conn = original_connect(*args, **kwargs)
        conn.set_trace_callback(traced_sql.append)
        return conn

    monkeypatch.setattr(storage_sqlite_memory, "connect_sqlite", _traced_connect)
    monkeypatch.setattr(storage_sqlite_memory, "_SQLITE_INLINE_DELETE_MAX_VARIABLES", 1)

    next_snapshot = {
        "risk": {"value": "aggressive", "updated_at": "2026-02-23T00:00:00"},
        "style": {"value": "momentum", "updated_at": "2026-02-23T00:00:00"},
    }
    assert save_memories_to_sqlite(db_path, next_snapshot, chatbot_core.logger) is True

    assert any(
        "CREATE TEMP TABLE IF NOT EXISTS _tmp_chatbot_memory_keys" in sql
        for sql in traced_sql
    )


def test_save_history_sessions_skips_redundant_session_updates(tmp_path: Path):
    db_path = resolve_chatbot_storage_db_path(tmp_path)
    sessions = {
        "s1": {
            "id": "s1",
            "title": "세션1",
            "messages": [{"role": "user", "parts": [{"text": "a"}], "timestamp": "2026-02-22T00:00:00"}],
            "created_at": "2026-02-22T00:00:00",
            "updated_at": "2026-02-22T00:00:00",
            "model": "gemini-2.0-flash-lite",
            "owner_id": "owner-a",
        }
    }
    assert save_history_sessions_to_sqlite(db_path, sessions, chatbot_core.logger) is True
    _install_session_update_audit_trigger(db_path)
    traced_sql: list[str] = []
    original_connect = storage_sqlite_history.connect_sqlite

    def _traced_connect(*args, **kwargs):
        conn = original_connect(*args, **kwargs)
        conn.set_trace_callback(traced_sql.append)
        return conn

    storage_sqlite_history.connect_sqlite = _traced_connect
    try:
        assert save_history_sessions_to_sqlite(db_path, sessions, chatbot_core.logger) is True
    finally:
        storage_sqlite_history.connect_sqlite = original_connect

    assert _read_session_update_audit_count(db_path) == 0
    assert not any(
        "FROM chatbot_messages" in sql and "ORDER BY message_index ASC" in sql
        for sql in traced_sql
    )


def test_save_memories_skips_redundant_memory_updates(tmp_path: Path):
    db_path = resolve_chatbot_storage_db_path(tmp_path)
    memories = {
        "risk": {"value": "aggressive", "updated_at": "2026-02-22T00:00:00"},
    }
    assert save_memories_to_sqlite(db_path, memories, chatbot_core.logger) is True
    _install_memory_update_audit_trigger(db_path)

    assert save_memories_to_sqlite(db_path, memories, chatbot_core.logger) is True
    assert _read_memory_update_audit_count(db_path) == 0


def test_load_history_sessions_recovers_when_sessions_table_missing(tmp_path: Path):
    db_path = resolve_chatbot_storage_db_path(tmp_path)
    sessions = {
        "s1": {
            "id": "s1",
            "title": "세션1",
            "messages": [{"role": "user", "parts": [{"text": "a"}], "timestamp": "2026-02-22T00:00:00"}],
            "created_at": "2026-02-22T00:00:00",
            "updated_at": "2026-02-22T00:00:00",
            "model": "gemini-2.0-flash-lite",
            "owner_id": "owner-a",
        }
    }
    assert save_history_sessions_to_sqlite(db_path, sessions, chatbot_core.logger) is True

    with sqlite3.connect(db_path) as conn:
        conn.execute("DROP TABLE IF EXISTS chatbot_sessions")
        conn.commit()

    loaded = load_history_sessions_from_sqlite(db_path, chatbot_core.logger)
    assert loaded == {}

    with sqlite3.connect(db_path) as conn:
        table_row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='chatbot_sessions'"
        ).fetchone()
    assert table_row is not None


def test_save_history_sessions_recovers_when_messages_table_missing(tmp_path: Path):
    db_path = resolve_chatbot_storage_db_path(tmp_path)
    sessions = {
        "s1": {
            "id": "s1",
            "title": "세션1",
            "messages": [
                {"role": "user", "parts": [{"text": "a"}], "timestamp": "2026-02-22T00:00:00"},
                {"role": "model", "parts": [{"text": "b"}], "timestamp": "2026-02-22T00:00:01"},
            ],
            "created_at": "2026-02-22T00:00:00",
            "updated_at": "2026-02-22T00:00:01",
            "model": "gemini-2.0-flash-lite",
            "owner_id": "owner-a",
        }
    }
    assert save_history_sessions_to_sqlite(db_path, sessions, chatbot_core.logger) is True

    with sqlite3.connect(db_path) as conn:
        conn.execute("DROP TABLE IF EXISTS chatbot_messages")
        conn.commit()

    assert save_history_sessions_to_sqlite(db_path, sessions, chatbot_core.logger) is True
    assert _count_rows(db_path, "chatbot_sessions") == 1
    assert _count_rows(db_path, "chatbot_messages") == 2


def test_load_memories_recovers_when_memories_table_missing(tmp_path: Path):
    db_path = resolve_chatbot_storage_db_path(tmp_path)
    memories = {
        "risk": {
            "value": "aggressive",
            "updated_at": "2026-02-22T00:00:00",
        }
    }
    assert save_memories_to_sqlite(db_path, memories, chatbot_core.logger) is True

    with sqlite3.connect(db_path) as conn:
        conn.execute("DROP TABLE IF EXISTS chatbot_memories")
        conn.commit()

    loaded = load_memories_from_sqlite(db_path, chatbot_core.logger)
    assert loaded == {}

    with sqlite3.connect(db_path) as conn:
        table_row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='chatbot_memories'"
        ).fetchone()
    assert table_row is not None
