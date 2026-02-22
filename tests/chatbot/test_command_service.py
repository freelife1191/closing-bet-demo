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


class _FakeMemory:
    def __init__(self):
        self.store = {}
        self.cleared = False

    def clear(self):
        self.cleared = True
        self.store = {}
        return "OK_CLEAR"

    def view(self):
        return self.store

    def add(self, key, value):
        self.store[key] = {"value": value}
        return "OK_ADD"

    def update(self, key, value):
        self.store[key] = {"value": value}
        return "OK_UPDATE"

    def remove(self, key):
        self.store.pop(key, None)
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

    def get_status(self):
        return {
            "user_id": "u1",
            "model": self.current_model_name,
            "memory_count": len(self.memory.view()),
            "history_count": len(self.history.sessions),
        }


def test_clear_current_session_messages_only_when_session_exists():
    bot = _FakeBot()
    bot.history.sessions["s1"] = {"messages": [{"role": "user"}]}
    assert clear_current_session_messages(bot, "s1") is True
    assert bot.history.sessions["s1"]["messages"] == []
    assert clear_current_session_messages(bot, "missing") is False


def test_handle_clear_command_all_and_current():
    bot = _FakeBot()
    bot.history.sessions["s1"] = {"messages": [{"role": "user"}]}

    result_current = handle_clear_command(bot, ["/clear"], "s1")
    assert "현재 대화 세션이 초기화" in result_current

    result_all = handle_clear_command(bot, ["/clear", "all"], "s1")
    assert "모든 데이터가 초기화" in result_all
    assert bot.history.cleared is True
    assert bot.memory.cleared is True


def test_handle_model_command_updates_session_model():
    bot = _FakeBot()
    bot.history.sessions["s1"] = {"model": "gemini-2.0-flash-lite"}

    result = handle_model_command(bot, ["/model", "gemini-2.5-flash-lite"], "s1")
    assert "변경되었습니다" in result
    assert bot.history.sessions["s1"]["model"] == "gemini-2.5-flash-lite"


def test_handle_memory_command_view_and_add():
    bot = _FakeBot()
    assert "없습니다" in handle_memory_command(bot, ["view"])

    add_result = handle_memory_command(bot, ["add", "risk", "high"])
    assert add_result == "OK_ADD"
    view_result = handle_memory_command(bot, ["view"])
    assert "risk" in view_result


def test_handle_command_routes_and_unknown():
    bot = _FakeBot()
    status_text = handle_command(bot, "/status", "s1")
    help_text = handle_command(bot, "/help", "s1")
    unknown_text = handle_command(bot, "/unknown", "s1")

    assert "현재 상태" in status_text
    assert "도움말" in help_text
    assert "알 수 없는 명령어" in unknown_text
