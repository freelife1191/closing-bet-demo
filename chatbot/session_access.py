#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
채팅 세션 접근/검증 유틸
"""

from __future__ import annotations

from typing import Any, Callable, Optional, Tuple

from .storage_history_helpers import is_session_accessible_by_owner


_EPHEMERAL_COMMANDS = {"/status", "/help"}


def is_ephemeral_command(user_message: str, files: Optional[list]) -> bool:
    """저장 없이 처리 가능한 경량 명령인지 판별한다."""
    if files:
        return False
    if not isinstance(user_message, str):
        return False

    # command_service.handle_command 와 같은 split() 으로 첫 토큰을 뽑아야 두 판정이 어긋나지 않는다.
    return next(iter(user_message.lower().split()), "") in _EPHEMERAL_COMMANDS


def _persist_owner_update(history: Any, session_id: str) -> None:
    """owner_id 보정 시 히스토리 저장 훅을 호출한다."""
    if hasattr(history, "_mark_session_changed"):
        try:
            history._mark_session_changed(session_id)
        except Exception:
            pass
    if hasattr(history, "_save"):
        try:
            history._save()
        except Exception:
            pass


def _assign_owner_if_empty(history: Any, session: dict[str, Any], session_id: str, owner_id: Optional[str]) -> None:
    if not owner_id:
        return
    if session.get("owner_id") is not None:
        return
    session["owner_id"] = owner_id
    _persist_owner_update(history, session_id)


def ensure_session_access(
    history: Any,
    session_id: Optional[str],
    target_model_name: str,
    is_ephemeral: bool,
    owner_id: Optional[str],
    logger: Any,
) -> str:
    """세션 존재/소유권을 보장하고 최종 세션 ID를 반환한다.

    조회와 삭제가 쓰는 is_session_accessible_by_owner 로 판정해 세 경로의 기준을
    하나로 둔다. 오류 대신 새 세션을 주는 것은 로그인 상태가 바뀌어도 채팅 자체는
    이어져야 하기 때문이며, 호출자는 응답의 session_id 로 바뀐 것을 알 수 있다.
    """
    save_immediate = not is_ephemeral

    if not session_id:
        return history.create_session(
            model_name=target_model_name,
            save_immediate=save_immediate,
            owner_id=owner_id,
        )

    session = history.get_session(session_id)
    if session is None:
        return history.create_session(
            model_name=target_model_name,
            save_immediate=save_immediate,
            owner_id=owner_id,
            session_id=session_id,
        )

    if not is_session_accessible_by_owner(session, owner_id):
        new_session_id = history.create_session(
            model_name=target_model_name,
            save_immediate=save_immediate,
            owner_id=owner_id,
        )
        logger.warning(
            "Session owner mismatch detected; created new session (old=%s, new=%s, old_owner=%s, new_owner=%s)",
            session_id,
            new_session_id,
            session.get("owner_id"),
            owner_id,
        )
        return new_session_id

    _assign_owner_if_empty(history, session, session_id, owner_id)
    return session_id


def prepare_chat_request(
    resolve_active_client: Callable[[Optional[str]], Tuple[Optional[Any], Optional[str]]],
    ensure_session_access_fn: Callable[[Optional[str], str, bool, Optional[str]], str],
    execute_command: Callable[
        [str, str, Optional[list], bool, Optional[str]],
        Tuple[bool, Optional[str], Optional[str]],
    ],
    user_message: str,
    session_id: Optional[str],
    target_model_name: str,
    files: Optional[list],
    api_key: Optional[str],
    owner_id: Optional[str],
) -> Tuple[Optional[Any], str, Optional[str], Optional[str], Optional[str]]:
    """
    채팅 요청의 공통 사전 처리.

    returns:
        (active_client, resolved_session_id, client_error, command_response, command_error)
    """
    active_client, client_error = resolve_active_client(api_key)
    if client_error:
        return None, "", client_error, None, None

    ephemeral = is_ephemeral_command(user_message, files)
    resolved_session_id = ensure_session_access_fn(
        session_id,
        target_model_name,
        ephemeral,
        owner_id,
    )

    # 명령 실행에도 소유자를 넘긴다. `/clear all` 이 요청자 자신의 대화만 지우려면
    # 여기가 유일한 전달 경로다.
    handled, command_response, command_error = execute_command(
        user_message,
        resolved_session_id,
        files,
        ephemeral,
        owner_id,
    )
    if handled:
        return active_client, resolved_session_id, None, command_response, command_error

    return active_client, resolved_session_id, None, None, None


__all__ = [
    "ensure_session_access",
    "is_ephemeral_command",
    "prepare_chat_request",
]
