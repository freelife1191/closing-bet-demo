#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KRStockChatbot chat/chat_stream 핸들러
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Generator, Optional

from .chat_execution import run_non_stream_response, run_stream_response
from .response_flow import friendly_error_message


logger = logging.getLogger(__name__)


def handle_chat(
    bot: Any,
    user_message: str,
    session_id: Optional[str] = None,
    model: Optional[str] = None,
    files: Optional[list] = None,
    watchlist: Optional[list] = None,
    persona: Optional[str] = None,
    api_key: Optional[str] = None,
    owner_id: Optional[str] = None,
) -> Dict[str, Any]:
    """chat() 처리 본문."""
    target_model_name = model or bot.current_model_name
    (
        active_client,
        session_id,
        client_error,
        cmd_resp,
        cmd_error,
    ) = bot._prepare_chat_request(
        user_message=user_message,
        session_id=session_id,
        target_model_name=target_model_name,
        files=files,
        api_key=api_key,
        owner_id=owner_id,
        reuse_session_id_on_owner_mismatch=True,
    )
    if client_error:
        return {"response": client_error, "session_id": session_id}
    if cmd_resp is not None or cmd_error is not None:
        if cmd_error:
            return {"response": cmd_error, "session_id": session_id}
        return {"response": cmd_resp, "session_id": session_id}

    try:
        api_history, content_parts = bot._build_chat_payload(
            user_message=user_message,
            session_id=session_id,
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
        bot._persist_chat_history(
            session_id=session_id,
            user_message=user_message,
            files=files,
            bot_response=bot_response,
        )

        return {
            "response": bot_response,
            "session_id": session_id,
            "usage_metadata": usage_metadata,
        }
    except Exception as e:
        error_msg = str(e)
        logger.error("[User: %s] Chat error: %s", bot.user_id, error_msg)
        return {
            "response": friendly_error_message(
                error_msg,
                default_prefix="⚠️ 오류가 발생했습니다: ",
            ),
            "session_id": session_id,
        }


def handle_chat_stream(
    bot: Any,
    user_message: str,
    session_id: Optional[str] = None,
    model: Optional[str] = None,
    files: Optional[list] = None,
    watchlist: Optional[list] = None,
    persona: Optional[str] = None,
    api_key: Optional[str] = None,
    owner_id: Optional[str] = None,
) -> Generator[Dict[str, Any], None, None]:
    """chat_stream() 처리 본문."""
    target_model_name = model or bot.current_model_name
    (
        active_client,
        session_id,
        client_error,
        cmd_resp,
        cmd_error,
    ) = bot._prepare_chat_request(
        user_message=user_message,
        session_id=session_id,
        target_model_name=target_model_name,
        files=files,
        api_key=api_key,
        owner_id=owner_id,
        reuse_session_id_on_owner_mismatch=False,
    )
    if client_error:
        yield {"error": client_error, "session_id": session_id}
        return

    if cmd_resp is not None or cmd_error is not None:
        if cmd_error:
            yield {"error": cmd_error, "session_id": session_id}
        else:
            yield {"chunk": cmd_resp, "session_id": session_id}
        return

    try:
        api_history, content_parts = bot._build_chat_payload(
            user_message=user_message,
            session_id=session_id,
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
            session_id=session_id,
            user_id=bot.user_id,
            logger=logger,
            normalize_response=bot._normalize_markdown_response,
        )

        if stream_error:
            yield {"error": stream_error, "session_id": session_id}
            return

        bot._persist_chat_history(
            session_id=session_id,
            user_message=user_message,
            files=files,
            bot_response=bot_response,
        )

        yield {"done": True, "session_id": session_id, "usage_metadata": usage_metadata}
        return

    except Exception as e:
        error_msg = str(e)
        logger.error("[User: %s] Chat error: %s", bot.user_id, error_msg)
        yield {
            "error": friendly_error_message(
                error_msg,
                default_prefix="⚠️ 서버 통신 오류가 발생했습니다: ",
            ),
            "session_id": session_id,
        }
        return
