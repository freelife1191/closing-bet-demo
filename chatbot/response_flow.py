#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
챗봇 응답 처리(에러/스트리밍/폴백) 유틸
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, Generator, List, Optional, Tuple

from .markdown_utils import _compute_stream_delta, _extract_reasoning_and_answer


def extract_usage_metadata(response: Any) -> Dict[str, int]:
    """Gemini 응답에서 토큰 사용량 메타데이터를 추출한다."""
    if not hasattr(response, "usage_metadata"):
        return {}
    meta = response.usage_metadata
    return {
        "prompt_token_count": getattr(meta, "prompt_token_count", 0),
        "candidates_token_count": getattr(meta, "candidates_token_count", 0),
        "total_token_count": getattr(meta, "total_token_count", 0),
    }


def friendly_error_message(error_msg: str, default_prefix: str) -> str:
    """사용자 친화 에러 메시지 변환."""
    if (
        "429" in error_msg
        or "Resource exhausted" in error_msg
        or "RESOURCE_EXHAUSTED" in error_msg
    ):
        return (
            "⚠️ **AI 서버 요청 한도 초과**\n\n"
            "Google AI 서버의 분당 요청 한도에 도달했습니다.\n"
            "**약 30초~1분 후에 다시 시도해주세요.**\n\n"
            "💡 안정적인 사용을 위해 **[설정] > [API Key]** 메뉴에서 "
            "개인 API Key를 등록하시면 이 제한을 피할 수 있습니다."
        )

    if (
        "400" in error_msg
        or "API_KEY_INVALID" in error_msg
        or "API key not valid" in error_msg
    ):
        return (
            "⚠️ **API Key 설정 오류**\n\n"
            "시스템에 설정된 API Key가 유효하지 않습니다.\n"
            "관리자에게 문의하거나 **[설정] > [API Key]** 메뉴에서 "
            "올바른 API Key를 다시 등록해주세요.\n"
            "(Google 서비스 문제일 수도 있습니다.)"
        )

    return f"{default_prefix}{error_msg}"


def build_fallback_models(target_model_name: str) -> List[str]:
    """스트리밍 재시도용 모델 후보 리스트."""
    fallback_sequence = [
        "gemini-2.0-flash-lite",
        "gemini-2.5-flash-lite",
        "gemini-2.0-flash",
        "gemini-2.5-flash",
        "gemini-3-flash-preview",
    ]
    models = [target_model_name]
    for model_name in fallback_sequence:
        if model_name not in models:
            models.append(model_name)
    return models


def is_retryable_stream_error(error_msg: str) -> bool:
    """스트리밍 폴백 재시도 가능 에러인지 판별한다."""
    error_upper = error_msg.upper()
    return (
        "503" in error_msg
        or "UNAVAILABLE" in error_upper
        or "429" in error_msg
        or "RESOURCE EXHAUSTED" in error_upper
        or "RESOURCE_EXHAUSTED" in error_upper
    )


def yield_stream_deltas(
    session_id: str,
    streamed_reasoning: str,
    streamed_answer: str,
    current_reasoning: str,
    current_answer: str,
) -> Generator[Dict[str, Any], None, Tuple[str, str]]:
    """스트리밍 중 추론/답변 델타를 계산하고 이벤트를 방출한다."""
    reasoning_reset, reasoning_delta = _compute_stream_delta(
        streamed_reasoning,
        current_reasoning,
    )
    if reasoning_reset:
        streamed_reasoning = ""
        yield {"reasoning_clear": True, "session_id": session_id}
    if reasoning_delta:
        streamed_reasoning = current_reasoning
        yield {
            "reasoning_chunk": reasoning_delta,
            "session_id": session_id,
        }

    answer_reset, answer_delta = _compute_stream_delta(
        streamed_answer,
        current_answer,
    )
    if answer_reset:
        streamed_answer = ""
        yield {"answer_clear": True, "session_id": session_id}
    if answer_delta:
        streamed_answer = current_answer
        yield {
            "chunk": answer_delta,
            "answer_chunk": answer_delta,
            "session_id": session_id,
        }

    return streamed_reasoning, streamed_answer


def stream_single_model_response(
    response_stream: Any,
    session_id: str,
) -> Generator[Dict[str, Any], None, Tuple[str, str, str]]:
    """단일 모델 응답 스트림을 처리하고 최종 누적 상태를 반환한다."""
    bot_response = ""
    streamed_reasoning = ""
    streamed_answer = ""

    for chunk in response_stream:
        chunk_text = getattr(chunk, "text", "")
        if not chunk_text:
            continue

        bot_response += chunk_text
        current_reasoning, current_answer = _extract_reasoning_and_answer(
            bot_response,
            is_streaming=True,
        )
        streamed_reasoning, streamed_answer = yield from yield_stream_deltas(
            session_id=session_id,
            streamed_reasoning=streamed_reasoning,
            streamed_answer=streamed_answer,
            current_reasoning=current_reasoning,
            current_answer=current_answer,
        )

    return bot_response, streamed_reasoning, streamed_answer


def stream_with_fallback_models(
    active_client: Any,
    target_model_name: str,
    api_history: List[dict],
    content_parts: List[Any],
    session_id: str,
    user_id: str,
    logger: logging.Logger,
) -> Generator[Dict[str, Any], None, Tuple[str, str, str, Optional[str]]]:
    """폴백 모델 순회로 스트리밍을 수행한다."""
    last_error = None

    for current_model in build_fallback_models(target_model_name):
        try:
            chat_session = active_client.chats.create(
                model=current_model,
                history=api_history,
            )
            response_stream = chat_session.send_message_stream(content_parts)
            bot_response, streamed_reasoning, streamed_answer = yield from stream_single_model_response(
                response_stream=response_stream,
                session_id=session_id,
            )
            return bot_response, streamed_reasoning, streamed_answer, None
        except Exception as e:
            last_error = str(e)
            if is_retryable_stream_error(last_error):
                logger.warning(
                    "[User: %s] %s Error (retryable). Details: %s",
                    user_id,
                    current_model,
                    last_error,
                )
                yield {"clear": True, "session_id": session_id}
                continue
            raise

    return "", "", "", (last_error or "알 수 없는 오류")


def sync_stream_with_final_response(
    bot_response: str,
    streamed_reasoning: str,
    streamed_answer: str,
    session_id: str,
    normalize_response: Callable[[str], str],
) -> Generator[Dict[str, Any], None, str]:
    """최종 정규화 결과와 스트리밍 화면을 동기화한다."""
    normalized_response = normalize_response(bot_response)
    final_reasoning, final_answer = _extract_reasoning_and_answer(
        normalized_response,
        is_streaming=False,
    )

    if (
        normalized_response != bot_response
        or final_reasoning != streamed_reasoning
        or final_answer != streamed_answer
    ):
        yield {"clear": True, "session_id": session_id}
        if final_reasoning:
            yield {"reasoning_chunk": final_reasoning, "session_id": session_id}
        if final_answer:
            yield {
                "chunk": final_answer,
                "answer_chunk": final_answer,
                "session_id": session_id,
            }

    return normalized_response
