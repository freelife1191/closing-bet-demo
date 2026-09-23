#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""[CHAT-034] 챗봇 저장소의 누락 테이블 복구가 공용 래퍼 한 곳을 지나는지 확인한다."""

from __future__ import annotations

import logging
import sqlite3

import pytest

import chatbot.storage_sqlite_common as sqlite_common
import chatbot.storage_sqlite_history as history
import chatbot.storage_sqlite_memory as memory
from chatbot.storage_sqlite_common import (
    ensure_chatbot_storage_schema,
    resolve_chatbot_storage_db_path,
    run_chatbot_sqlite_with_recovery,
)

LOGGER = logging.getLogger(__name__)
HISTORY = ("chatbot_sessions", "chatbot_messages")
MEMORY = ("chatbot_memories",)
TS = "2026-09-23T00:00:00"
SESSION = {"id": "s1", "title": "t", "messages": [], "created_at": TS,
           "updated_at": TS, "model": "m", "owner_id": "o"}
RECORD = {"value": "v", "updated_at": TS}


def _drop(db_path, tables):
    with sqlite3.connect(db_path) as conn:
        for table in tables:
            conn.execute(f"DROP TABLE IF EXISTS {table}")


def _has_table(db_path, table):
    with sqlite3.connect(db_path) as conn:
        return conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
        ).fetchone() is not None


def _skip_prune(monkeypatch):
    # load_memories 는 try 앞에서 prune 을 먼저 부르므로, 우회하지 않으면 복구가 prune 에서 끝난다.
    monkeypatch.setattr(memory, "_prune_daily_suggestions_in_sqlite", lambda *a, **k: True)


def test_wrapper_does_not_recover_other_tables(tmp_path, monkeypatch):
    db_path = resolve_chatbot_storage_db_path(tmp_path)
    recover_calls = []
    monkeypatch.setattr(
        sqlite_common, "ensure_chatbot_storage_schema",
        lambda *a, **k: recover_calls.append(k) or True,
    )

    def _fail():
        raise sqlite3.OperationalError("no such table: chatbot_sessions")

    with pytest.raises(sqlite3.OperationalError):
        run_chatbot_sqlite_with_recovery(db_path, LOGGER, _fail, table_names=MEMORY)
    assert recover_calls == []


CASES = [
    ("load_history", HISTORY, lambda p: history.load_history_sessions_from_sqlite(p, LOGGER), {}),
    ("save_history", HISTORY, lambda p: history.save_history_sessions_to_sqlite(p, {"s1": SESSION}, LOGGER), True),
    ("upsert_session", HISTORY, lambda p: history.upsert_history_session_with_messages(p, SESSION, LOGGER), True),
    ("apply_deltas", HISTORY, lambda p: history.apply_history_session_deltas_in_sqlite(
        p, {"s1": SESSION}, {"s1"}, set(), False, LOGGER), True),
    ("delete_session", HISTORY, lambda p: history.delete_history_session_from_sqlite(p, "s1", LOGGER), True),
    ("clear_history", HISTORY, lambda p: history.clear_history_sessions_in_sqlite(p, LOGGER), True),
    ("prune_daily", MEMORY, lambda p: memory._prune_daily_suggestions_in_sqlite(p, LOGGER), True),
    ("save_daily", MEMORY, lambda p: memory.save_daily_suggestions_in_sqlite(p, "daily_suggestions_x", [], LOGGER), True),
    ("load_memories", MEMORY, lambda p: memory.load_memories_from_sqlite(p, LOGGER), {}),
    ("save_memories", MEMORY, lambda p: memory.save_memories_to_sqlite(p, {"o": {"k": RECORD}}, LOGGER), True),
    ("upsert_memory", MEMORY, lambda p: memory.upsert_memory_entry_in_sqlite(p, "o", "k", RECORD, LOGGER), True),
    ("delete_memory", MEMORY, lambda p: memory.delete_memory_entry_in_sqlite(p, "o", "k", LOGGER), True),
    ("clear_memories", MEMORY, lambda p: memory.clear_memories_in_sqlite(p, LOGGER, owner_id="o"), True),
    ("clear_general", MEMORY, lambda p: memory.clear_general_memories_in_sqlite(p, LOGGER, owner_id="o"), True),
]


@pytest.mark.parametrize("name,tables,call,expected", CASES, ids=[c[0] for c in CASES])
def test_each_storage_function_recovers_dropped_tables(tmp_path, monkeypatch, name, tables, call, expected):
    db_path = resolve_chatbot_storage_db_path(tmp_path)
    assert ensure_chatbot_storage_schema(db_path, LOGGER)
    if name == "load_memories":
        _skip_prune(monkeypatch)
    _drop(db_path, tables)

    assert call(db_path) == expected
    assert all(_has_table(db_path, table) for table in tables)


def test_load_history_recovers_when_only_messages_table_missing(tmp_path):
    db_path = resolve_chatbot_storage_db_path(tmp_path)
    assert ensure_chatbot_storage_schema(db_path, LOGGER)
    assert history.save_history_sessions_to_sqlite(db_path, {"s1": SESSION}, LOGGER) is True
    _drop(db_path, ("chatbot_messages",))

    loaded = history.load_history_sessions_from_sqlite(db_path, LOGGER)

    assert loaded is not None and list(loaded) == ["s1"]
    assert _has_table(db_path, "chatbot_messages")


def test_failed_recovery_returns_default_without_looping(tmp_path, monkeypatch):
    db_path = resolve_chatbot_storage_db_path(tmp_path)
    assert ensure_chatbot_storage_schema(db_path, LOGGER)
    forced = []

    def _spy(path, logger, *, force_recheck=False):
        if force_recheck:
            forced.append(path)
            return False
        return True

    for module in (sqlite_common, history, memory):
        monkeypatch.setattr(module, "ensure_chatbot_storage_schema", _spy)
    _skip_prune(monkeypatch)
    _drop(db_path, MEMORY)

    assert memory.load_memories_from_sqlite(db_path, LOGGER) is None
    assert memory.save_memories_to_sqlite(db_path, {"o": {"k": RECORD}}, LOGGER) is False
    assert len(forced) == 2


def test_retry_failure_after_recovery_returns_default_with_one_recovery(tmp_path, monkeypatch):
    db_path = resolve_chatbot_storage_db_path(tmp_path)
    assert ensure_chatbot_storage_schema(db_path, LOGGER)
    forced = []

    def _spy(path, logger, *, force_recheck=False):
        # 복구했다고 답하지만 테이블은 만들지 않아 재시도도 실패한다.
        if force_recheck:
            forced.append(path)
        return True

    for module in (sqlite_common, history, memory):
        monkeypatch.setattr(module, "ensure_chatbot_storage_schema", _spy)
    _drop(db_path, MEMORY)

    assert memory.save_memories_to_sqlite(db_path, {"o": {"k": RECORD}}, LOGGER) is False
    assert len(forced) == 1
