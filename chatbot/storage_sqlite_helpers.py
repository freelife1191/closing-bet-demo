#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
챗봇 히스토리/메모리 SQLite 저장 퍼사드
"""

from __future__ import annotations

from .storage_sqlite_common import (
    ensure_chatbot_storage_schema,
    resolve_chatbot_storage_db_path,
)
from .storage_sqlite_history import (
    apply_history_session_deltas_in_sqlite,
    clear_history_sessions_in_sqlite,
    delete_history_session_from_sqlite,
    load_history_sessions_from_sqlite,
    restore_lost_history_messages_in_sqlite,
    save_history_sessions_to_sqlite,
    upsert_history_session_with_messages,
)
from .storage_sqlite_memory import (
    clear_general_memories_in_sqlite,
    clear_memories_in_sqlite,
    delete_memory_entry_in_sqlite,
    load_memories_from_sqlite,
    normalize_daily_suggestions_memories,
    save_daily_suggestions_in_sqlite,
    save_memories_to_sqlite,
    upsert_memory_entry_in_sqlite,
)


__all__ = [
    "apply_history_session_deltas_in_sqlite",
    "clear_general_memories_in_sqlite",
    "clear_history_sessions_in_sqlite",
    "clear_memories_in_sqlite",
    "delete_history_session_from_sqlite",
    "delete_memory_entry_in_sqlite",
    "ensure_chatbot_storage_schema",
    "load_history_sessions_from_sqlite",
    "load_memories_from_sqlite",
    "normalize_daily_suggestions_memories",
    "resolve_chatbot_storage_db_path",
    "restore_lost_history_messages_in_sqlite",
    "save_daily_suggestions_in_sqlite",
    "save_history_sessions_to_sqlite",
    "save_memories_to_sqlite",
    "upsert_history_session_with_messages",
    "upsert_memory_entry_in_sqlite",
]
