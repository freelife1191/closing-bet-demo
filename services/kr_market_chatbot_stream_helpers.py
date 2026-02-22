#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KR Market Chatbot Stream Helpers

챗봇 SSE 스트리밍/후처리 로직을 제공한다.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Callable, Generator

from services.kr_market_chatbot_quota_helpers import maybe_increment_chatbot_usage


def stream_chatbot_response(
    *,
    bot: Any,
    payload: dict[str, Any],
    user_api_key: str | None,
    usage_key: str | None,
    use_free_tier: bool,
    logger: logging.Logger,
    increment_user_usage_fn: Callable[[str | None], int],
    log_activity_fn: Callable[[str, dict[str, Any], bool], None],
) -> Generator[str, None, None]:
    """챗봇 스트림 응답 생성기 (SSE)."""

    def _finalize_chat_stream(
        full_response: str,
        usage_metadata: dict[str, Any],
        stream_has_error: bool,
    ) -> None:
        log_activity_fn(full_response, usage_metadata, stream_has_error)
        maybe_increment_chatbot_usage(
            use_free_tier=use_free_tier,
            usage_key=usage_key,
            stream_has_error=stream_has_error,
            full_response=full_response,
            increment_user_usage_fn=increment_user_usage_fn,
            logger=logger,
        )

    yield from stream_chatbot_response_chunks(
        bot=bot,
        payload=payload,
        user_api_key=user_api_key,
        usage_key=usage_key,
        logger=logger,
        on_finalize=_finalize_chat_stream,
    )


def stream_chatbot_response_chunks(
    bot: Any,
    payload: dict[str, Any],
    user_api_key: str | None,
    usage_key: str | None,
    logger: logging.Logger,
    on_finalize: Callable[[str, dict[str, Any], bool], None] | None = None,
) -> Generator[str, None, None]:
    """챗봇 SSE chunk를 생성하고 종료 시 콜백을 호출한다."""
    full_response = ""
    usage_metadata: dict[str, Any] = {}
    stream_has_error = False

    try:
        for chunk in bot.chat_stream(
            payload["message"],
            session_id=payload["session_id"],
            model=payload["model_name"],
            files=payload["files"] if payload["files"] else None,
            watchlist=payload["watchlist"],
            persona=payload["persona"],
            api_key=user_api_key,
            owner_id=usage_key,
        ):
            if "chunk" in chunk:
                full_response += str(chunk["chunk"])
            if "usage_metadata" in chunk:
                usage_metadata = chunk["usage_metadata"]
            if chunk.get("error"):
                stream_has_error = True

            yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
    except Exception as e:
        stream_has_error = True
        logger.error(f"[{usage_key}] Chat stream error: {e}")
        yield f"data: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"
    finally:
        if on_finalize is not None:
            on_finalize(full_response, usage_metadata, stream_has_error)

