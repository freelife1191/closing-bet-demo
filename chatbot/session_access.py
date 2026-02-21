#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
챗봇 세션 접근/사전처리 유틸
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Optional, Tuple


def is_ephemeral_command(user_message: str, files: Optional[list]) -> bool:
    """저장 없이 처리 가능한 경량 명령 여부."""
    return bool(
        not files and user_message.strip().startswith(("/status", "/help", "/memory view"))
    )


def ensure_session_access(
    history: Any,
    session_id: Optional[str],
    target_model_name: str,
    is_ephemeral: bool,
    owner_id: Optional[str],
    reuse_session_id_on_owner_mismatch: bool,
    logger: logging.Logger,
) -> str:
    """세션 생성/검증 및 소유권 확인."""
    if not session_id or not history.get_session(session_id):
        session_id = history.create_session(
            model_name=target_model_name,
            save_immediate=not is_ephemeral,
            owner_id=owner_id,
            session_id=session_id,
        )

    if session_id:
        session_data = history.get_session(session_id)
        if session_data:
            session_owner = session_data.get("owner_id")
            if session_owner and session_owner != owner_id:
                logger.warning(
                    "Session access denied. Owner: %s, Requester: %s",
                    session_owner,
                    owner_id,
                )
                if reuse_session_id_on_owner_mismatch:
                    session_id = history.create_session(
                        model_name=target_model_name,
                        save_immediate=not is_ephemeral,
                        owner_id=owner_id,
                        session_id=session_id,
                    )
                else:
                    session_id = history.create_session(
                        model_name=target_model_name,
                        save_immediate=not is_ephemeral,
                        owner_id=owner_id,
                    )

    return session_id


def prepare_chat_request(
    resolve_active_client: Callable[[Optional[str]], Tuple[Optional[Any], Optional[str]]],
    ensure_session_access_fn: Callable[
        [Optional[str], str, bool, Optional[str], bool], str
    ],
    execute_command: Callable[[str, str, Optional[list], bool], Tuple[bool, Optional[str], Optional[str]]],
    user_message: str,
    session_id: Optional[str],
    target_model_name: str,
    files: Optional[list],
    api_key: Optional[str],
    owner_id: Optional[str],
    reuse_session_id_on_owner_mismatch: bool,
) -> Tuple[Optional[Any], str, Optional[str], Optional[str], Optional[str]]:
    """
    채팅 공통 사전 처리.
    returns: (active_client, resolved_session_id, client_error, cmd_response, cmd_error)
    """
    active_client, client_error = resolve_active_client(api_key)
    if client_error:
        return None, session_id or "", client_error, None, None

    is_ephemeral = is_ephemeral_command(user_message, files)
    resolved_session_id = ensure_session_access_fn(
        session_id,
        target_model_name,
        is_ephemeral,
        owner_id,
        reuse_session_id_on_owner_mismatch,
    )

    handled, cmd_resp, cmd_error = execute_command(
        user_message,
        resolved_session_id,
        files,
        is_ephemeral,
    )
    if handled:
        return active_client, resolved_session_id, None, cmd_resp, cmd_error

    return active_client, resolved_session_id, None, None, None
