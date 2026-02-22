#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KRStockChatbot payload/system prompt 래퍼 믹스인.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .data_service import fetch_jongga_data as _fetch_jongga_data_impl
from .payload_service import (
    build_api_history as _build_api_history_impl,
    build_chat_payload as _build_chat_payload_impl,
    build_content_parts as _build_content_parts_impl,
    compose_system_prompt as _compose_system_prompt_impl,
)
from .stock_query_service import (
    fallback_response as _fallback_response_impl,
    format_stock_info as _format_stock_info_impl,
)

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"


class CorePayloadMixin:
    """`KRStockChatbot`의 payload/system prompt 래퍼."""

    def _compose_system_prompt(
        self,
        user_message: str,
        target_model_name: str,
        market_data: Dict[str, Any],
        vcp_data: List[dict],
        sector_scores: Dict[str, Any],
        watchlist: Optional[list],
        persona: Optional[str],
        additional_context: str,
    ) -> str:
        """기본 시스템 프롬프트 + 질의별 컨텍스트 병합."""
        return _compose_system_prompt_impl(
            bot=self,
            user_message=user_message,
            target_model_name=target_model_name,
            market_data=market_data,
            vcp_data=vcp_data,
            sector_scores=sector_scores,
            watchlist=watchlist,
            persona=persona,
            additional_context=additional_context,
        )

    def _build_api_history(self, session_id: str) -> List[dict]:
        """Gemini SDK 전달용 히스토리(role/parts만 유지)."""
        return _build_api_history_impl(self, session_id)

    def _build_content_parts(
        self,
        files: Optional[list],
        system_prompt: str,
        intent_instruction: str,
        user_message: str,
        jongga_context: bool,
    ) -> List[Any]:
        """멀티모달 요청 payload(parts) 생성."""
        return _build_content_parts_impl(
            files=files,
            system_prompt=system_prompt,
            intent_instruction=intent_instruction,
            user_message=user_message,
            jongga_context=jongga_context,
        )

    def _build_chat_payload(
        self,
        user_message: str,
        session_id: str,
        target_model_name: str,
        files: Optional[list],
        watchlist: Optional[list],
        persona: Optional[str],
    ) -> Tuple[List[dict], List[Any]]:
        """챗/스트림 공통 요청 payload(history + parts)를 구성한다."""
        return _build_chat_payload_impl(
            bot=self,
            user_message=user_message,
            session_id=session_id,
            target_model_name=target_model_name,
            files=files,
            watchlist=watchlist,
            persona=persona,
        )

    def _fetch_jongga_data(self) -> str:
        """jongga_v2_latest.json에서 최신 S/A급 종목 조회"""
        return _fetch_jongga_data_impl(DATA_DIR)

    def _fallback_response(self, user_message: str, vcp_data: list) -> str:
        """AI 사용 불가 시 폴백 응답"""
        return _fallback_response_impl(user_message, vcp_data)

    def _format_stock_info(self, stock: Dict) -> str:
        """종목 정보 포맷팅"""
        return _format_stock_info_impl(stock)

