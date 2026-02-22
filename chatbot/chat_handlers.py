#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
챗봇 요청 처리 핸들러 (동기/스트림)
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Generator, Optional

from .chat_execution import run_non_stream_response, run_stream_response
from .response_flow import friendly_error_message


logger = logging.getLogger(__name__)


def _resolve_target_model_name(bot: Any, model: Optional[str]) -> str:
    return model or getattr(bot, "current_model_name", "gemini-2.0-flash-lite")


def _prepare_request(
    bot: Any,
    user_message: str,
    session_id: Optional[str],
    target_model_name: str,
    files: Optional[list],
    api_key: Optional[str],
    owner_id: Optional[str],
) -> tuple[Optional[Any], str, Optional[str], Optional[str], Optional[str]]:
    return bot._prepare_chat_request(
        user_message=user_message,
        session_id=session_id,
        target_model_name=target_model_name,
        files=files,
        api_key=api_key,
        owner_id=owner_id,
        reuse_session_id_on_owner_mismatch=True,
    )


def handle_chat(
    bot: Any,
    user_message: str,
    session_id: str = None,
    model: str = None,
    files: list = None,
    watchlist: list = None,
    persona: str = None,
    api_key: str = None,
    owner_id: str = None,
) -> Dict[str, Any]:
    """비스트림 채팅 처리."""
    target_model_name = _resolve_target_model_name(bot, model)
    active_client, resolved_session_id, client_error, command_response, command_error = _prepare_request(
        bot=bot,
        user_message=user_message,
        session_id=session_id,
        target_model_name=target_model_name,
        files=files,
        api_key=api_key,
        owner_id=owner_id,
    )

    if client_error:
        return {"response": client_error, "session_id": resolved_session_id}
    if command_response is not None:
        return {"response": command_response, "session_id": resolved_session_id}
    if command_error:
        return {"response": command_error, "session_id": resolved_session_id}

    try:
        api_history, content_parts = bot._build_chat_payload(
            user_message=user_message,
            session_id=resolved_session_id,
            target_model_name=target_model_name,
            files=files,
            watchlist=watchlist,
            persona=persona,
        )
        bot_response, usage_metadata = run_non_stream_response(
            active_client=active_client,
            target_model_name=target_model_name,
            api_history=api_history,
            content_parts=content_parts,
            normalize_response=bot._normalize_markdown_response,
        )
        bot._persist_chat_history(resolved_session_id, user_message, files, bot_response)
        return {
            "response": bot_response,
            "session_id": resolved_session_id,
            "usage_metadata": usage_metadata,
        }
    except Exception as error:
        logger.error("Chat handler error: %s", error)
        return {
            "response": friendly_error_message(
                str(error),
                "⚠️ 응답 생성 중 오류가 발생했습니다: ",
            ),
            "session_id": resolved_session_id,
        }


def _command_stream_terminal_event(
    session_id: str,
    command_response: Optional[str],
    command_error: Optional[str],
) -> list[dict[str, Any]]:
    message = command_error or command_response or ""
    events = []
    if message:
        events.append(
            {
                "chunk": message,
                "answer_chunk": message,
                "session_id": session_id,
            }
        )
    events.append({"done": True, "session_id": session_id})
    return events


def handle_chat_stream(
    bot: Any,
    user_message: str,
    session_id: str = None,
    model: str = None,
    files: list = None,
    watchlist: list = None,
    persona: str = None,
    api_key: str = None,
    owner_id: str = None,
) -> Generator[Dict[str, Any], None, None]:
    """스트림 채팅 처리."""
    target_model_name = _resolve_target_model_name(bot, model)
    active_client, resolved_session_id, client_error, command_response, command_error = _prepare_request(
        bot=bot,
        user_message=user_message,
        session_id=session_id,
        target_model_name=target_model_name,
        files=files,
        api_key=api_key,
        owner_id=owner_id,
    )

    if client_error:
        yield {"error": client_error, "session_id": resolved_session_id, "done": True}
        return
    if command_response is not None or command_error:
        for event in _command_stream_terminal_event(
            session_id=resolved_session_id,
            command_response=command_response,
            command_error=command_error,
        ):
            yield event
        return

    try:
        api_history, content_parts = bot._build_chat_payload(
            user_message=user_message,
            session_id=resolved_session_id,
            target_model_name=target_model_name,
            files=files,
            watchlist=watchlist,
            persona=persona,
        )

        bot_response, usage_metadata, stream_error = yield from run_stream_response(
            active_client=active_client,
            target_model_name=target_model_name,
            api_history=api_history,
            content_parts=content_parts,
            session_id=resolved_session_id,
            user_id=bot.user_id,
            logger=logger,
            normalize_response=bot._normalize_markdown_response,
        )

        if stream_error:
            yield {"error": stream_error, "session_id": resolved_session_id, "done": True}
            return

        bot._persist_chat_history(resolved_session_id, user_message, files, bot_response or "")
        if usage_metadata:
            yield {"usage_metadata": usage_metadata, "session_id": resolved_session_id}
        yield {"done": True, "session_id": resolved_session_id}
    except Exception as error:
        logger.error("Chat stream handler error: %s", error)
        yield {
            "error": friendly_error_message(
                str(error),
                "⚠️ 스트리밍 응답 생성 중 오류가 발생했습니다: ",
            ),
            "session_id": resolved_session_id,
            "done": True,
        }


__all__ = [
    "handle_chat",
    "handle_chat_stream",
]

