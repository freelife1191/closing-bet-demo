#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
챗봇 SQLite 저장소 회귀 테스트
"""

import json
import os
import sqlite3
import sys
from pathlib import Path


sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

import chatbot.core as chatbot_core
from chatbot.storage_sqlite_helpers import (
    apply_history_session_deltas_in_sqlite,
    resolve_chatbot_storage_db_path,
    save_history_sessions_to_sqlite,
)


def _count_rows(db_path: Path, table: str) -> int:
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
    return int(row[0]) if row else 0


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


def test_apply_history_session_deltas_clear_all(tmp_path: Path):
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


def test_apply_history_session_deltas_append_only_skips_message_delete(tmp_path: Path):
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
