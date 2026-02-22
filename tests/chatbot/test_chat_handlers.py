#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
chat_handlers 유틸 회귀 테스트
"""

import os
import sys
from types import SimpleNamespace


sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from chatbot.chat_handlers import handle_chat, handle_chat_stream


def _drain_generator(gen):
    events = []
    try:
        while True:
            events.append(next(gen))
    except StopIteration:
        return events


class _FakeSession:
    def __init__(self, response=None, stream=None):
        self._response = response
        self._stream = stream

    def send_message(self, _content_parts):
        return self._response

    def send_message_stream(self, _content_parts):
        return self._stream


class _FakeChats:
    def __init__(self, response=None, stream=None):
        self.response = response
        self.stream = stream

    def create(self, model, history):
        _ = (model, history)
        return _FakeSession(response=self.response, stream=self.stream)


class _FakeClient:
    def __init__(self, response=None, stream=None):
        self.chats = _FakeChats(response=response, stream=stream)


class _FakeBot:
    def __init__(self):
        self.current_model_name = "gemini-2.0-flash-lite"
        self.user_id = "u1"
        self.saved = []
        self.prepare_result = None
        self.payload = ([], ["msg"])
        self.normalize = lambda text: text

    def _prepare_chat_request(self, **kwargs):
        _ = kwargs
        return self.prepare_result

    def _build_chat_payload(self, **kwargs):
        _ = kwargs
        return self.payload

    def _normalize_markdown_response(self, text):
        return self.normalize(text)

    def _persist_chat_history(self, session_id, user_message, files, bot_response):
        self.saved.append((session_id, user_message, files, bot_response))


def test_handle_chat_returns_client_error_without_model_call():
    bot = _FakeBot()
    bot.prepare_result = (None, "s1", "client error", None, None)

    result = handle_chat(bot, user_message="hello")

    assert result == {"response": "client error", "session_id": "s1"}
    assert bot.saved == []


def test_handle_chat_success_persists_history_and_usage():
    usage = SimpleNamespace(
        prompt_token_count=1,
        candidates_token_count=2,
        total_token_count=3,
    )
    response = SimpleNamespace(text="정상 응답", usage_metadata=usage)
    bot = _FakeBot()
    bot.prepare_result = (_FakeClient(response=response), "s1", None, None, None)

    result = handle_chat(bot, user_message="질문")

    assert result["response"] == "정상 응답"
    assert result["session_id"] == "s1"
    assert result["usage_metadata"]["total_token_count"] == 3
    assert bot.saved[-1][0] == "s1"


def test_handle_chat_stream_emits_done_and_persists_history():
    bot = _FakeBot()
    stream = [SimpleNamespace(text="[답변]\n스트림 응답")]
    bot.prepare_result = (_FakeClient(stream=stream), "s1", None, None, None)

    events = _drain_generator(handle_chat_stream(bot, user_message="질문"))

    assert any(e.get("answer_chunk") for e in events)
    assert events[-1].get("done") is True
    assert bot.saved[-1][3].endswith("스트림 응답")
