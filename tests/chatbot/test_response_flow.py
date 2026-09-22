#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
response_flow 유틸 회귀 테스트
"""

import logging
import os
import sys
from types import SimpleNamespace


sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from chatbot.response_flow import (
    build_fallback_models,
    extract_usage_metadata,
    friendly_error_message,
    stream_single_model_response,
    stream_with_fallback_models,
    sync_stream_with_final_response,
)


def _drain_generator(gen):
    """Generator 이벤트를 모두 소비하고 (events, return_value)를 반환한다."""
    events = []
    try:
        while True:
            events.append(next(gen))
    except StopIteration as stop:
        return events, stop.value


def test_extract_usage_metadata_returns_empty_when_usage_missing():
    response = SimpleNamespace(text="ok")
    assert extract_usage_metadata(response) == {}


def test_extract_usage_metadata_returns_empty_when_usage_is_none():
    # 스트리밍 청크는 usage_metadata 속성을 갖되 값이 None 인 채로 오는 경우가 많다.
    response = SimpleNamespace(text="ok", usage_metadata=None)
    assert extract_usage_metadata(response) == {}


def test_extract_usage_metadata_reads_all_known_fields():
    usage = SimpleNamespace(
        prompt_token_count=11,
        candidates_token_count=22,
        total_token_count=33,
    )
    response = SimpleNamespace(usage_metadata=usage)

    assert extract_usage_metadata(response) == {
        "prompt_token_count": 11,
        "candidates_token_count": 22,
        "total_token_count": 33,
    }


def test_friendly_error_message_maps_rate_limit_and_api_key_errors():
    rate_msg = friendly_error_message(
        "429 RESOURCE_EXHAUSTED",
        default_prefix="prefix:",
    )
    key_msg = friendly_error_message(
        "400 API_KEY_INVALID",
        default_prefix="prefix:",
    )

    assert "요청 한도 초과" in rate_msg
    assert "AI 서버 인증 오류" in key_msg


def test_friendly_error_message_maps_server_errors_by_leading_status_code():
    # [CHAT-036] google-genai APIError 는 "<code> <status>. <details>" 형식이다.
    internal = friendly_error_message(
        "500 INTERNAL. {'error': {'code': 500, 'message': 'Internal error encountered.', 'status': 'INTERNAL'}}",
        default_prefix="prefix:",
    )

    assert "AI 서버 일시 장애" in internal
    assert "prefix:" not in internal


def test_friendly_error_message_ignores_status_like_digits_inside_details():
    # [CHAT-036] 세부 문구의 16400 이 "400" 부분 문자열에 걸려 인증 오류로 오분류되던 회귀
    message = friendly_error_message(
        "503 UNAVAILABLE. {'message': 'max_output_tokens=16400'}",
        default_prefix="prefix:",
    )

    assert "인증 오류" not in message
    assert "AI 서버 일시 장애" in message


def test_friendly_error_message_maps_vertex_auth_failures_and_keeps_unknown_errors():
    assert "AI 서버 인증 오류" in friendly_error_message(
        "401 UNAUTHENTICATED. {'error': {'status': 'UNAUTHENTICATED'}}",
        default_prefix="prefix:",
    )
    assert "AI 서버 인증 오류" in friendly_error_message(
        "403 PERMISSION_DENIED. {'error': {'status': 'PERMISSION_DENIED'}}",
        default_prefix="prefix:",
    )
    # 상태 코드가 없는 일반 예외는 접두사와 원문을 그대로 돌려준다.
    assert friendly_error_message("connection reset", default_prefix="prefix:") == (
        "prefix:connection reset"
    )


def test_build_fallback_models_starts_with_target_and_deduplicates():
    models = build_fallback_models("gemini-3.7-flash")
    assert models[0] == "gemini-3.7-flash"
    assert models.count("gemini-3.7-flash") == 1
    assert "gemini-2.5-flash" in models


def test_stream_single_model_response_emits_reasoning_and_answer_chunks():
    chunks = [
        SimpleNamespace(text="[추론 과정]\n근거를 정리합니다."),
        SimpleNamespace(text="\n[답변]\n최종 답변"),
    ]
    gen = stream_single_model_response(chunks, session_id="s1")
    events, result = _drain_generator(gen)
    bot_response, streamed_reasoning, streamed_answer, _usage = result

    assert any(e.get("reasoning_chunk") for e in events)
    assert any(e.get("answer_chunk") for e in events)
    assert "최종 답변" in bot_response
    assert "근거를 정리합니다." in streamed_reasoning
    assert streamed_answer == "최종 답변"


def test_stream_single_model_response_handles_split_headers_across_chunks():
    chunks = [
        SimpleNamespace(text="**[추"),
        SimpleNamespace(text="론 과정]**\n근거 A"),
        SimpleNamespace(text="\n[답"),
        SimpleNamespace(text="변]\n결론 B"),
    ]
    gen = stream_single_model_response(chunks, session_id="s1")
    events, result = _drain_generator(gen)
    _, streamed_reasoning, streamed_answer, _usage = result

    assert any("근거 A" in (e.get("reasoning_chunk") or "") for e in events)
    assert any("결론 B" in (e.get("answer_chunk") or "") for e in events)
    assert "근거 A" in streamed_reasoning
    assert "결론 B" in streamed_answer


def test_stream_single_model_response_flushes_pending_tail_without_headers():
    chunks = [SimpleNamespace(text="헤더 없이 바로 답변")]

    gen = stream_single_model_response(chunks, session_id="s1")
    events, result = _drain_generator(gen)
    _, streamed_reasoning, streamed_answer, _usage = result

    assert streamed_reasoning == ""
    assert streamed_answer == "헤더 없이 바로 답변"
    assert any("헤더 없이 바로 답변" in (e.get("answer_chunk") or "") for e in events)


def test_sync_stream_with_final_response_emits_clear_and_final_answer():
    gen = sync_stream_with_final_response(
        bot_response="[추론 과정]\n근거\n[답변]\n결론",
        streamed_reasoning="근거",
        streamed_answer="",
        session_id="s1",
        normalize_response=lambda text: text,
    )
    events, normalized = _drain_generator(gen)

    assert normalized.endswith("결론")
    assert events[0] == {"clear": True, "session_id": "s1"}
    assert any(e.get("answer_chunk") == "결론" for e in events)


class _FakeChatSession:
    def __init__(self, behavior):
        self.behavior = behavior

    def send_message_stream(self, _content_parts):
        if isinstance(self.behavior, Exception):
            raise self.behavior
        return self.behavior


class _FakeChats:
    def __init__(self, model_behaviors):
        self.model_behaviors = model_behaviors

    def create(self, model, history):
        _ = history
        behavior = self.model_behaviors.get(model)
        if behavior is None:
            raise RuntimeError(f"unexpected model: {model}")
        return _FakeChatSession(behavior)


class _FakeClient:
    def __init__(self, model_behaviors):
        self.chats = _FakeChats(model_behaviors)


def test_stream_with_fallback_models_treats_500_internal_as_retryable():
    # [CHAT-036] 500 INTERNAL 은 503 과 같은 일시 장애다. 다음 모델로 넘어가야 한다.
    model_behaviors = {
        "gemini-3.7-flash": RuntimeError(
            "500 INTERNAL. {'error': {'code': 500, 'message': 'Internal error encountered.', 'status': 'INTERNAL'}}"
        ),
        "gemini-3.5-flash-lite": [SimpleNamespace(text="[답변]\n복구 응답")],
    }
    fake_client = _FakeClient(model_behaviors)

    gen = stream_with_fallback_models(
        active_client=fake_client,
        target_model_name="gemini-3.7-flash",
        api_history=[],
        content_parts=["hello"],
        session_id="s1",
        user_id="u1",
        logger=logging.getLogger("test.response_flow"),
    )
    events, result = _drain_generator(gen)
    bot_response, _reasoning, _answer, _usage, fallback_error = result

    assert events[0] == {"clear": True, "session_id": "s1"}
    assert fallback_error is None
    assert "복구 응답" in bot_response


def test_stream_with_fallback_models_retries_then_succeeds():
    model_behaviors = {
        "gemini-3.7-flash": RuntimeError("503 UNAVAILABLE"),
        "gemini-3.5-flash-lite": [SimpleNamespace(text="[답변]\n복구 응답")],
    }
    fake_client = _FakeClient(model_behaviors)

    gen = stream_with_fallback_models(
        active_client=fake_client,
        target_model_name="gemini-3.7-flash",
        api_history=[],
        content_parts=["hello"],
        session_id="s1",
        user_id="u1",
        logger=logging.getLogger("test.response_flow"),
    )
    events, result = _drain_generator(gen)
    bot_response, streamed_reasoning, streamed_answer, _usage, fallback_error = result

    assert events[0] == {"clear": True, "session_id": "s1"}
    assert "복구 응답" in bot_response
    assert streamed_reasoning == ""
    assert streamed_answer == "복구 응답"
    assert fallback_error is None
