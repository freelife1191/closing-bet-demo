#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
챗봇 모델 실행(일반/스트리밍) 유틸
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, Generator, List, Optional, Tuple

from .response_flow import (
    extract_usage_metadata,
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
    """일반(non-stream) 모델 호출을 수행한다."""
    chat_session = active_client.chats.create(
        model=target_model_name,
        history=api_history,
    )
    response = chat_session.send_message(content_parts)
    bot_response = normalize_response(getattr(response, "text", "") or "")
    usage_metadata = extract_usage_metadata(response)
    return bot_response, usage_metadata


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
    """스트리밍 모델 호출을 수행하고 최종 응답/메타를 반환한다."""
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
        logger.error(
            "[User: %s] All fallback models failed. Last Error: %s",
            user_id,
            fallback_error,
        )
        return (
            None,
            {},
            "⚠️ **서버 통신 지연**\n\nAI 서버에 트래픽이 집중되고 있거나 일시적인 장애가 발생했습니다. 잠시 후 다시 시도해주세요.",
        )

    normalized_response = yield from sync_stream_with_final_response(
        bot_response=bot_response,
        streamed_reasoning=streamed_reasoning,
        streamed_answer=streamed_answer,
        session_id=session_id,
        normalize_response=normalize_response,
    )
    return normalized_response, {}, None
