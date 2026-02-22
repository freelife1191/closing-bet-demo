#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
chat_execution 유틸 회귀 테스트
"""

import logging
import os
import sys
from types import SimpleNamespace


sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from chatbot.chat_execution import run_non_stream_response, run_stream_response


def _drain_generator(gen):
    events = []
    try:
        while True:
            events.append(next(gen))
    except StopIteration as stop:
        return events, stop.value


class _FakeNonStreamSession:
    def __init__(self, response):
        self.response = response

    def send_message(self, _content_parts):
        return self.response


class _FakeStreamSession:
    def __init__(self, behavior):
        self.behavior = behavior

    def send_message_stream(self, _content_parts):
        if isinstance(self.behavior, Exception):
            raise self.behavior
        return self.behavior


class _FakeChats:
    def __init__(
        self,
        non_stream_response=None,
        stream_behaviors=None,
        default_stream_behavior=None,
    ):
        self.non_stream_response = non_stream_response
        self.stream_behaviors = stream_behaviors or {}
        self.default_stream_behavior = default_stream_behavior

    def create(self, model, history):
        _ = history
        if self.non_stream_response is not None:
            return _FakeNonStreamSession(self.non_stream_response)
        behavior = self.stream_behaviors.get(model, self.default_stream_behavior)
        if behavior is None:
            raise RuntimeError(f"unexpected model: {model}")
        return _FakeStreamSession(behavior)


class _FakeClient:
    def __init__(self, chats):
        self.chats = chats


def test_run_non_stream_response_returns_normalized_text_and_usage():
    usage = SimpleNamespace(
        prompt_token_count=3,
        candidates_token_count=5,
        total_token_count=8,
    )
    response = SimpleNamespace(text="hello", usage_metadata=usage)
    client = _FakeClient(_FakeChats(non_stream_response=response))

    bot_response, usage_metadata = run_non_stream_response(
        active_client=client,
        target_model_name="gemini-2.0-flash-lite",
        api_history=[],
        content_parts=["msg"],
        normalize_response=lambda text: f"[N]{text}",
    )

    assert bot_response == "[N]hello"
    assert usage_metadata["total_token_count"] == 8


def test_run_stream_response_retries_and_returns_success():
    client = _FakeClient(
        _FakeChats(
            stream_behaviors={
                "gemini-2.0-flash-lite": RuntimeError("503 UNAVAILABLE"),
                "gemini-2.5-flash-lite": [SimpleNamespace(text="[답변]\n복구 완료")],
            }
        )
    )

    gen = run_stream_response(
        active_client=client,
        target_model_name="gemini-2.0-flash-lite",
        api_history=[],
        content_parts=["msg"],
        session_id="s1",
        user_id="u1",
        logger=logging.getLogger("test.chat_execution"),
        normalize_response=lambda text: text,
    )
    events, result = _drain_generator(gen)
    bot_response, usage_metadata, stream_error = result

    assert events[0] == {"clear": True, "session_id": "s1"}
    assert any(e.get("answer_chunk") for e in events)
    assert "복구 완료" in bot_response
    assert usage_metadata == {}
    assert stream_error is None


def test_run_stream_response_returns_user_friendly_error_when_all_fallbacks_fail():
    client = _FakeClient(
        _FakeChats(default_stream_behavior=RuntimeError("503 UNAVAILABLE"))
    )

    gen = run_stream_response(
        active_client=client,
        target_model_name="gemini-2.0-flash-lite",
        api_history=[],
        content_parts=["msg"],
        session_id="s1",
        user_id="u1",
        logger=logging.getLogger("test.chat_execution"),
        normalize_response=lambda text: text,
    )
    events, result = _drain_generator(gen)
    bot_response, usage_metadata, stream_error = result

    assert len(events) >= 1
    assert bot_response is None
    assert usage_metadata == {}
    assert "서버 통신 지연" in stream_error
