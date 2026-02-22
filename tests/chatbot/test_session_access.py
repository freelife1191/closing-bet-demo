#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
session_access 유틸 회귀 테스트
"""

import os
import sys


sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from chatbot.session_access import (
    ensure_session_access,
    is_ephemeral_command,
    prepare_chat_request,
)


class _FakeHistory:
    def __init__(self):
        self.sessions = {}
        self._counter = 0

    def create_session(self, model_name=None, save_immediate=True, owner_id=None, session_id=None):
        _ = (model_name, save_immediate)
        if session_id is None:
            self._counter += 1
            session_id = f"s{self._counter}"
        self.sessions[session_id] = {"id": session_id, "owner_id": owner_id}
        return session_id

    def get_session(self, session_id):
        return self.sessions.get(session_id)


class _FakeLogger:
    def __init__(self):
        self.warnings = []

    def warning(self, message, *args):
        self.warnings.append(message % args)


def test_is_ephemeral_command_detects_lightweight_commands():
    assert is_ephemeral_command("/status", files=None)
    assert is_ephemeral_command("/help", files=[])
    assert not is_ephemeral_command("일반 질문", files=None)
    assert not is_ephemeral_command("/status", files=[{"name": "a.png"}])


def test_ensure_session_access_owner_mismatch_reuses_or_recreates_based_on_flag():
    history = _FakeHistory()
    logger = _FakeLogger()
    old_id = history.create_session(owner_id="owner-a")

    reused_id = ensure_session_access(
        history=history,
        session_id=old_id,
        target_model_name="gemini-2.0-flash-lite",
        is_ephemeral=False,
        owner_id="owner-b",
        reuse_session_id_on_owner_mismatch=True,
        logger=logger,
    )
    assert reused_id == old_id
    assert history.get_session(old_id)["owner_id"] == "owner-b"

    old_id_2 = history.create_session(owner_id="owner-c")
    recreated_id = ensure_session_access(
        history=history,
        session_id=old_id_2,
        target_model_name="gemini-2.0-flash-lite",
        is_ephemeral=False,
        owner_id="owner-d",
        reuse_session_id_on_owner_mismatch=False,
        logger=logger,
    )
    assert recreated_id != old_id_2
    assert history.get_session(recreated_id)["owner_id"] == "owner-d"
    assert logger.warnings


def test_prepare_chat_request_returns_command_response_when_handled():
    def resolve_active_client(api_key):
        _ = api_key
        return "client", None

    def ensure_session_access_fn(session_id, target_model_name, is_ephemeral, owner_id, reuse_flag):
        _ = (target_model_name, is_ephemeral, owner_id, reuse_flag)
        return session_id or "s1"

    def execute_command(user_message, session_id, files, is_ephemeral):
        _ = (user_message, session_id, files, is_ephemeral)
        return True, "cmd ok", None

    result = prepare_chat_request(
        resolve_active_client=resolve_active_client,
        ensure_session_access_fn=ensure_session_access_fn,
        execute_command=execute_command,
        user_message="/help",
        session_id=None,
        target_model_name="gemini-2.0-flash-lite",
        files=None,
        api_key=None,
        owner_id="owner",
        reuse_session_id_on_owner_mismatch=True,
    )

    assert result == ("client", "s1", None, "cmd ok", None)


def test_prepare_chat_request_returns_client_error_immediately():
    def resolve_active_client(api_key):
        _ = api_key
        return None, "client error"

    def ensure_session_access_fn(session_id, target_model_name, is_ephemeral, owner_id, reuse_flag):
        _ = (session_id, target_model_name, is_ephemeral, owner_id, reuse_flag)
        raise AssertionError("should not be called")

    def execute_command(user_message, session_id, files, is_ephemeral):
        _ = (user_message, session_id, files, is_ephemeral)
        raise AssertionError("should not be called")

    result = prepare_chat_request(
        resolve_active_client=resolve_active_client,
        ensure_session_access_fn=ensure_session_access_fn,
        execute_command=execute_command,
        user_message="hello",
        session_id=None,
        target_model_name="gemini-2.0-flash-lite",
        files=None,
        api_key="bad",
        owner_id="owner",
        reuse_session_id_on_owner_mismatch=False,
    )

    assert result == (None, "", "client error", None, None)
