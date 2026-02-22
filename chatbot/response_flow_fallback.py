#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
챗봇 응답 처리: 스트림 폴백/최종 동기화 유틸
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, Generator, List, Optional, Tuple

from .markdown_utils import _extract_reasoning_and_answer
from .response_flow_errors import build_fallback_models, is_retryable_stream_error
from .response_flow_stream import stream_single_model_response


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


__all__ = [
    "stream_with_fallback_models",
    "sync_stream_with_final_response",
]
