#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CoreCommandMixin 명령 저장 회귀 테스트
"""

import os
import sys


sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from chatbot.core_command_mixin import CoreCommandMixin
from chatbot.session_access import is_ephemeral_command


class _RecordingHistory:
    def __init__(self):
        self.saved: list[tuple[str, str, str]] = []

    def add_message(self, session_id, role, content, save=False):
        _ = save
        self.saved.append((session_id, role, content))


class _CommandBot(CoreCommandMixin):
    def __init__(self):
        self.history = _RecordingHistory()

    def _handle_command(self, command, session_id=None):
        _ = session_id
        return f"응답:{command}"


def _run_command(command: str):
    bot = _CommandBot()
    ephemeral = is_ephemeral_command(command, files=None)
    handled, response, error = bot._execute_command(
        user_message=command,
        session_id="s1",
        files=None,
        is_ephemeral=ephemeral,
    )
    return bot, handled, response, error


def test_state_changing_commands_are_persisted_to_history():
    for command in ("/clear", "/model gemini-3.7-flash", "/memory add 메모", "/refresh"):
        bot, handled, response, error = _run_command(command)

        assert handled is True, command
        assert error is None, command
        assert response == f"응답:{command}", command
        assert bot.history.saved == [
            ("s1", "user", command),
            ("s1", "model", f"응답:{command}"),
        ], command


def test_lightweight_commands_leave_no_history():
    for command in ("/status", "/help"):
        bot, handled, _response, error = _run_command(command)

        assert handled is True, command
        assert error is None, command
        assert bot.history.saved == [], command


def test_plain_message_is_not_treated_as_command():
    bot, handled, response, error = _run_command("삼성전자 어때?")

    assert handled is False
    assert response is None
    assert error is None
    assert bot.history.saved == []
