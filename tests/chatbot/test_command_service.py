#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
command_service 유틸 회귀 테스트
"""

import os
import sys


sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from chatbot.command_service import (
    clear_current_session_messages,
    handle_clear_command,
    handle_command,
    handle_memory_command,
    handle_model_command,
)


class _FakeHistory:
    def __init__(self):
        self.sessions = {}
        self.saved = 0
        self.cleared = False

    def get_session(self, session_id):
        return self.sessions.get(session_id)

    def _save(self):
        self.saved += 1

    def clear_all(self):
        self.cleared = True
        self.sessions = {}

    def clear_for_owner(self, owner_id):
        if not owner_id:
            return 0
        targets = [
            session_id
            for session_id, session in self.sessions.items()
            if session.get("owner_id") == owner_id
        ]
        for session_id in targets:
            del self.sessions[session_id]
        return len(targets)


class _FakeMemory:
    def __init__(self):
        self.store = {}
        self.cleared = False

    def clear(self, owner_id=None):
        self.cleared = True
        self.store.pop(owner_id or "", None)
        return "OK_CLEAR"

    def view(self, owner_id=None):
        return self.store.get(owner_id or "", {})

    def add(self, key, value, owner_id=None):
        self.store.setdefault(owner_id or "", {})[key] = {"value": value}
        return "OK_ADD"

    def update(self, key, value, owner_id=None):
        self.store.setdefault(owner_id or "", {})[key] = {"value": value}
        return "OK_UPDATE"

    def remove(self, key, owner_id=None):
        self.store.get(owner_id or "", {}).pop(key, None)
        return "OK_REMOVE"


class _FakeBot:
    def __init__(self):
        self.history = _FakeHistory()
        self.memory = _FakeMemory()
        self.current_model_name = "gemini-2.0-flash-lite"
        self.available_models = ["gemini-2.0-flash-lite", "gemini-2.5-flash-lite"]
        self._data_cache = {"v": 1}
        self.user_id = "u1"

    def get_available_models(self):
        return self.available_models

    def set_model(self, model_name):
        if model_name in self.available_models:
            self.current_model_name = model_name
            return True
        return False

    def get_status(self, owner_id=None):
        owned = [
            s for s in self.history.sessions.values()
            if owner_id and s.get("owner_id") == owner_id
        ]
        return {
            "user_id": "u1",
            "model": self.current_model_name,
            "memory_count": len(self.memory.view(owner_id)) if owner_id else 0,
            "history_count": len(owned),
        }


def test_clear_current_session_messages_only_when_session_exists():
    bot = _FakeBot()
    bot.history.sessions["s1"] = {"messages": [{"role": "user"}]}
    assert clear_current_session_messages(bot, "s1") is True
    assert bot.history.sessions["s1"]["messages"] == []
    assert clear_current_session_messages(bot, "missing") is False


def test_handle_clear_command_all_and_current():
    bot = _FakeBot()
    bot.history.sessions["s1"] = {"messages": [{"role": "user"}], "owner_id": "owner-a"}

    result_current = handle_clear_command(bot, ["/clear"], "s1", "owner-a")
    assert "현재 대화 세션이 초기화" in result_current

    result_all = handle_clear_command(bot, ["/clear", "all"], "s1", "owner-a")
    assert "내 대화 1건" in result_all
    # 전역 삭제는 더 이상 일어나지 않는다. 메모리는 요청자의 것만 지운다.
    assert bot.history.cleared is False
    assert bot.memory.cleared is True


def test_handle_clear_all_leaves_other_owners_untouched():
    """[CHAT-016] /clear all 이 남의 대화를 지우면 안 된다."""
    bot = _FakeBot()
    bot.history.sessions["mine"] = {"messages": [], "owner_id": "owner-a"}
    bot.history.sessions["theirs"] = {"messages": [], "owner_id": "owner-b"}
    bot.history.sessions["legacy"] = {"messages": [], "owner_id": None}

    handle_clear_command(bot, ["/clear", "all"], "mine", "owner-a")

    assert "mine" not in bot.history.sessions
    assert "theirs" in bot.history.sessions
    assert "legacy" in bot.history.sessions


def test_handle_clear_all_refuses_when_owner_is_unknown():
    """소유자를 모르면 아무것도 지우지 않는다. 레거시 세션이 통째로 날아가는 것을 막는다."""
    bot = _FakeBot()
    bot.history.sessions["legacy"] = {"messages": [], "owner_id": None}

    result = handle_clear_command(bot, ["/clear", "all"], "legacy", None)

    assert "초기화하지 않았습니다" in result
    assert "legacy" in bot.history.sessions
    assert bot.history.cleared is False


def test_handle_model_command_updates_session_model():
    bot = _FakeBot()
    bot.history.sessions["s1"] = {"model": "gemini-2.0-flash-lite"}

    result = handle_model_command(bot, ["/model", "gemini-2.5-flash-lite"], "s1")
    assert "변경되었습니다" in result
    assert bot.history.sessions["s1"]["model"] == "gemini-2.5-flash-lite"


def test_handle_memory_command_view_and_add():
    bot = _FakeBot()
    assert "없습니다" in handle_memory_command(bot, ["view"], "owner-a")

    add_result = handle_memory_command(bot, ["add", "risk", "high"], "owner-a")
    assert add_result == "OK_ADD"
    view_result = handle_memory_command(bot, ["view"], "owner-a")
    assert "risk" in view_result


def test_handle_command_routes_and_unknown():
    bot = _FakeBot()
    status_text = handle_command(bot, "/status", "s1")
    help_text = handle_command(bot, "/help", "s1")
    unknown_text = handle_command(bot, "/unknown", "s1")

    assert "현재 상태" in status_text
    assert "도움말" in help_text
    assert "알 수 없는 명령어" in unknown_text


def test_status_counts_only_requester_sessions():
    """`/status` 의 「세션 개수」는 요청자 자신의 것만 센다."""
    bot = _FakeBot()
    bot.history.sessions["s1"] = {"owner_id": "owner-a", "messages": []}
    bot.history.sessions["s2"] = {"owner_id": "owner-b", "messages": []}
    bot.history.sessions["s3"] = {"owner_id": None, "messages": []}

    assert "세션 개수: 1" in handle_command(bot, "/status", "s1", "owner-a")
    assert "세션 개수: 0" in handle_command(bot, "/status", "s1", "owner-c")
    assert "세션 개수: 0" in handle_command(bot, "/status", "s1")
