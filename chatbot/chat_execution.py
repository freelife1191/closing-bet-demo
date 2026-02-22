#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
챗봇 단일/스트리밍 실행 유틸
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, Generator, List, Optional, Tuple

from .response_flow import (
    extract_usage_metadata,
    friendly_error_message,
    is_retryable_stream_error,
    stream_with_fallback_models,
    sync_stream_with_final_response,
)


def run_non_stream_response(
    active_client: Any,
    target_model_name: str,
    api_history: List[dict],
    content_parts: List[Any],
    normalize_response: Callable[[str], str],
) -> Tuple[str, Dict[str, int]]:
    """단일 응답 요청을 실행하고 정규화/usage 메타를 반환한다."""
    chat_session = active_client.chats.create(
        model=target_model_name,
        history=api_history,
    )
    response = chat_session.send_message(content_parts)
    raw_text = getattr(response, "text", "") or ""
    bot_response = normalize_response(raw_text)
    usage_metadata = extract_usage_metadata(response)
    return bot_response, usage_metadata


def _build_stream_fallback_error(error_msg: str) -> str:
    if is_retryable_stream_error(error_msg):
        return (
            "⚠️ 서버 통신 지연이 발생했습니다. 잠시 후 다시 시도해주세요. "
            f"(상세: {error_msg})"
        )
    return friendly_error_message(error_msg, "⚠️ 스트리밍 응답 처리 오류: ")


def run_stream_response(
    active_client: Any,
    target_model_name: str,
    api_history: List[dict],
    content_parts: List[Any],
    session_id: str,
    user_id: str,
    logger: logging.Logger,
    normalize_response: Callable[[str], str],
) -> Generator[Dict[str, Any], None, Tuple[Optional[str], Dict[str, int], Optional[str]]]:
    """
    스트림 응답을 실행하고 이벤트를 중계한다.

    returns:
        (bot_response, usage_metadata, stream_error)
    """
    usage_metadata: Dict[str, int] = {}
    try:
        (
            bot_response,
            streamed_reasoning,
            streamed_answer,
            fallback_error,
        ) = yield from stream_with_fallback_models(
            active_client=active_client,
            target_model_name=target_model_name,
            api_history=api_history,
            content_parts=content_parts,
            session_id=session_id,
            user_id=user_id,
            logger=logger,
        )
        if fallback_error:
            return None, usage_metadata, _build_stream_fallback_error(fallback_error)

        normalized_response = yield from sync_stream_with_final_response(
            bot_response=bot_response,
            streamed_reasoning=streamed_reasoning,
            streamed_answer=streamed_answer,
            session_id=session_id,
            normalize_response=normalize_response,
        )
        return normalized_response, usage_metadata, None
    except Exception as error:
        return None, usage_metadata, friendly_error_message(
            str(error),
            "⚠️ 스트리밍 응답 처리 오류: ",
        )


__all__ = [
    "run_non_stream_response",
    "run_stream_response",
]

