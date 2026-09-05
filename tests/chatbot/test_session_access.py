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
        self.sessions[session_id] = {"id": session_id, "owner_id": owner_id, "messages": []}
        return session_id

    def get_session(self, session_id):
        return self.sessions.get(session_id)

    def get_messages(self, session_id):
        return self.sessions.get(session_id, {}).get("messages", [])


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


def test_is_ephemeral_command_ignores_case_and_arguments():
    assert is_ephemeral_command("/STATUS", files=None)
    assert is_ephemeral_command("  /help  ", files=None)
    # command_service.handle_command 와 같은 split() 이라 탭 구분도 같게 잘린다.
    assert is_ephemeral_command("/status\t추가", files=None)
    assert not is_ephemeral_command("", files=None)
    assert not is_ephemeral_command("   ", files=None)


def test_ensure_session_access_never_hands_over_a_session_with_another_owner():
    """남의 세션 ID 로 채팅을 보내도 그 세션을 가져가지 못한다."""
    history = _FakeHistory()
    logger = _FakeLogger()
    victim_id = history.create_session(owner_id="owner-a")

    resolved = ensure_session_access(
        history=history,
        session_id=victim_id,
        target_model_name="gemini-2.0-flash-lite",
        is_ephemeral=False,
        owner_id="owner-b",
        logger=logger,
    )

    assert resolved != victim_id
    assert history.get_session(victim_id)["owner_id"] == "owner-a"
    assert history.get_session(resolved)["owner_id"] == "owner-b"
    assert logger.warnings


def test_ensure_session_access_blocks_requests_without_an_owner():
    """소유자를 모르는 요청은 남의 세션 대화를 프롬프트에 실을 수 없다.

    build_api_history 가 세션 ID 하나로 과거 대화 전부를 LLM 컨텍스트에 싣기 때문에,
    돌려받은 세션이 비어 있다는 것이 곧 유출이 막혔다는 뜻이다.
    """
    history = _FakeHistory()
    logger = _FakeLogger()
    victim_id = history.create_session(owner_id="owner-a")
    history.sessions[victim_id]["messages"] = [{"role": "user", "parts": ["보유 종목은 삼성전자"]}]

    resolved = ensure_session_access(
        history=history,
        session_id=victim_id,
        target_model_name="gemini-2.0-flash-lite",
        is_ephemeral=False,
        owner_id=None,
        logger=logger,
    )

    assert resolved != victim_id
    assert history.get_messages(resolved) == []
    assert history.get_messages(victim_id) != []


def test_ensure_session_access_keeps_legacy_and_own_sessions():
    """소유자가 비어 있는 레거시 세션은 이어받고, 자기 세션은 그대로 쓴다."""
    history = _FakeHistory()
    logger = _FakeLogger()

    legacy_id = history.create_session(owner_id=None)
    assert ensure_session_access(
        history=history,
        session_id=legacy_id,
        target_model_name="gemini-2.0-flash-lite",
        is_ephemeral=False,
        owner_id="owner-a",
        logger=logger,
    ) == legacy_id
    assert history.get_session(legacy_id)["owner_id"] == "owner-a"

    assert ensure_session_access(
        history=history,
        session_id=legacy_id,
        target_model_name="gemini-2.0-flash-lite",
        is_ephemeral=False,
        owner_id="owner-a",
        logger=logger,
    ) == legacy_id
    assert not logger.warnings


def test_prepare_chat_request_returns_command_response_when_handled():
    def resolve_active_client(api_key):
        _ = api_key
        return "client", None

    def ensure_session_access_fn(session_id, target_model_name, is_ephemeral, owner_id):
        _ = (target_model_name, is_ephemeral, owner_id)
        return session_id or "s1"

    def execute_command(user_message, session_id, files, is_ephemeral, owner_id):
        # 소유자가 명령 실행까지 전달되어야 /clear all 이 자기 대화만 지운다.
        assert owner_id == "owner"
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
    )

    assert result == ("client", "s1", None, "cmd ok", None)


def test_prepare_chat_request_returns_client_error_immediately():
    def resolve_active_client(api_key):
        _ = api_key
        return None, "client error"

    def ensure_session_access_fn(session_id, target_model_name, is_ephemeral, owner_id):
        _ = (session_id, target_model_name, is_ephemeral, owner_id)
        raise AssertionError("should not be called")

    def execute_command(user_message, session_id, files, is_ephemeral, owner_id):
        _ = (user_message, session_id, files, is_ephemeral, owner_id)
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
    )

    assert result == (None, "", "client error", None, None)
