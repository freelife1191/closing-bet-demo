#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KRStockChatbot 명령/세션 처리 믹스인.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from .command_service import (
    clear_current_session_messages as _clear_current_session_messages_impl,
    get_help as _get_help_impl,
    get_status_message as _get_status_message_impl,
    handle_clear_command as _handle_clear_command_impl,
    handle_command as _handle_command_impl,
    handle_memory_command as _handle_memory_command_impl,
    handle_memory_write_action as _handle_memory_write_action_impl,
    handle_model_command as _handle_model_command_impl,
    handle_refresh_command as _handle_refresh_command_impl,
    render_memory_help as _render_memory_help_impl,
    render_memory_view as _render_memory_view_impl,
    render_model_command_help as _render_model_command_help_impl,
)
from .runtime_setup_service import resolve_active_client as _resolve_active_client_impl
from .session_access import (
    ensure_session_access as _ensure_session_access_impl,
    is_ephemeral_command as _is_ephemeral_command_impl,
    prepare_chat_request as _prepare_chat_request_impl,
)

logger = logging.getLogger(__name__)


class CoreCommandMixin:
    """`KRStockChatbot`의 명령/세션 관련 동작을 담당하는 믹스인."""

    def _resolve_active_client(self, api_key: Optional[str]) -> Tuple[Optional[Any], Optional[str]]:
        """요청별 활성 클라이언트 선택 (사용자 키 우선)."""
        return _resolve_active_client_impl(
            current_client=self.client,
            api_key=api_key,
            logger=logger,
        )

    def _is_ephemeral_command(self, user_message: str, files: Optional[list]) -> bool:
        """저장 없이 처리 가능한 경량 명령 여부."""
        return _is_ephemeral_command_impl(user_message, files)

    def _ensure_session_access(
        self,
        session_id: Optional[str],
        target_model_name: str,
        is_ephemeral: bool,
        owner_id: Optional[str],
        reuse_session_id_on_owner_mismatch: bool,
    ) -> str:
        """세션 생성/검증 및 소유권 확인."""
        return _ensure_session_access_impl(
            history=self.history,
            session_id=session_id,
            target_model_name=target_model_name,
            is_ephemeral=is_ephemeral,
            owner_id=owner_id,
            reuse_session_id_on_owner_mismatch=reuse_session_id_on_owner_mismatch,
            logger=logger,
        )

    def _execute_command(
        self,
        user_message: str,
        session_id: str,
        files: Optional[list],
        is_ephemeral: bool,
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        슬래시 명령 실행.
        returns: (handled, response, error_message)
        """
        if files or not user_message.startswith("/"):
            return False, None, None

        try:
            cmd_resp = self._handle_command(user_message, session_id)
            if not is_ephemeral:
                self.history.add_message(session_id, "user", user_message, save=True)
                self.history.add_message(session_id, "model", cmd_resp, save=True)
            return True, cmd_resp, None
        except Exception as error:
            logger.error(f"Command error: {error}")
            return True, None, f"⚠️ 명령어 처리 중 오류가 발생했습니다: {str(error)}"

    def _format_user_history_message(self, user_message: str, files: Optional[list]) -> str:
        if not files:
            return user_message
        return f"{user_message} [파일 {len(files)}개 첨부됨]"

    def _persist_chat_history(
        self,
        session_id: str,
        user_message: str,
        files: Optional[list],
        bot_response: str,
    ) -> None:
        """대화 히스토리(유저/모델)를 저장한다."""
        user_history_msg = self._format_user_history_message(user_message, files)
        self.history.add_message(session_id, "user", user_history_msg)
        self.history.add_message(session_id, "model", bot_response)

    def _prepare_chat_request(
        self,
        user_message: str,
        session_id: Optional[str],
        target_model_name: str,
        files: Optional[list],
        api_key: Optional[str],
        owner_id: Optional[str],
        reuse_session_id_on_owner_mismatch: bool,
    ) -> Tuple[Optional[Any], str, Optional[str], Optional[str], Optional[str]]:
        """채팅 공통 사전 처리 래퍼."""
        return _prepare_chat_request_impl(
            resolve_active_client=self._resolve_active_client,
            ensure_session_access_fn=self._ensure_session_access,
            execute_command=self._execute_command,
            user_message=user_message,
            session_id=session_id,
            target_model_name=target_model_name,
            files=files,
            api_key=api_key,
            owner_id=owner_id,
            reuse_session_id_on_owner_mismatch=reuse_session_id_on_owner_mismatch,
        )

    def _clear_current_session_messages(self, session_id: Optional[str]) -> bool:
        """현재 세션 메시지를 초기화한다."""
        return _clear_current_session_messages_impl(self, session_id)

    def _handle_clear_command(self, parts: List[str], session_id: Optional[str]) -> str:
        """`/clear` 명령 처리."""
        return _handle_clear_command_impl(self, parts, session_id)

    def _handle_refresh_command(self) -> str:
        """데이터 캐시 초기화."""
        return _handle_refresh_command_impl(self)

    def _render_model_command_help(self) -> str:
        """`/model` 도움말 텍스트 렌더링."""
        return _render_model_command_help_impl(self)

    def _handle_model_command(self, parts: List[str], session_id: Optional[str]) -> str:
        """`/model` 명령 처리."""
        return _handle_model_command_impl(self, parts, session_id)

    def _render_memory_view(self) -> str:
        """저장된 메모리 목록 문자열 생성."""
        return _render_memory_view_impl(self)

    def _render_memory_help(self) -> str:
        """메모리 명령어 사용법 문자열."""
        return _render_memory_help_impl()

    def _handle_memory_write_action(self, action: str, args: List[str]) -> Optional[str]:
        """메모리 쓰기 액션(add/update/remove/clear)을 처리한다."""
        return _handle_memory_write_action_impl(self, action, args)

    def _handle_command(self, command: str, session_id: str = None) -> str:
        """명령어 처리"""
        return _handle_command_impl(self, command, session_id)

    def _handle_memory_command(self, args: list) -> str:
        """메모리 명령어 처리"""
        return _handle_memory_command_impl(self, args)

    def _get_status_message(self) -> str:
        """현재 상태 확인 메시지"""
        return _get_status_message_impl(self)

    def _get_help(self) -> str:
        """도움말"""
        return _get_help_impl()
