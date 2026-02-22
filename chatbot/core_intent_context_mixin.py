#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KRStockChatbot 의도별 컨텍스트 구성 래퍼 믹스인.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from .intent_context import (
    build_additional_context as _build_additional_context_impl,
    build_news_intent_context as _build_news_intent_context_impl,
    build_vcp_intent_context as _build_vcp_intent_context_impl,
    build_watchlist_context_bundle as _build_watchlist_context_bundle_impl,
    resolve_primary_intent_context as _resolve_primary_intent_context_impl,
)
from .intent_detail_service import (
    build_closing_bet_context as _build_closing_bet_context_impl,
    build_market_gate_context as _build_market_gate_context_impl,
    build_watchlist_detailed_context as _build_watchlist_detailed_context_impl,
    build_watchlist_summary_context as _build_watchlist_summary_context_impl,
    contains_any_keyword as _contains_any_keyword_impl,
)

logger = logging.getLogger(__name__)


class CoreIntentContextMixin:
    """`KRStockChatbot`의 의도/추가 컨텍스트 래퍼."""

    def _contains_any_keyword(self, user_message: str, keywords: List[str]) -> bool:
        """문자열에 키워드 중 하나라도 포함되는지 확인."""
        return _contains_any_keyword_impl(user_message, keywords)

    def _build_closing_bet_context(self) -> Tuple[str, str]:
        """종가베팅 의도 컨텍스트/지시문 생성."""
        return _build_closing_bet_context_impl(
            memory=self.memory,
            user_id=self.user_id,
            fetch_jongga_data_fn=self._fetch_jongga_data,
            logger=logger,
        )

    def _build_market_gate_context(self, market_gate_data: Dict[str, Any]) -> str:
        """시장/마켓게이트 질문용 컨텍스트 생성."""
        return _build_market_gate_context_impl(market_gate_data)

    def _build_watchlist_detailed_context(
        self,
        watchlist: List[str],
        vcp_data: List[dict],
    ) -> str:
        """관심종목 상세 컨텍스트 생성."""
        return _build_watchlist_detailed_context_impl(
            watchlist=watchlist,
            vcp_data=vcp_data,
            stock_map=self.stock_map,
            format_stock_context_fn=self._format_stock_context,
        )

    def _build_watchlist_summary_context(self, watchlist: List[str], vcp_data: List[dict]) -> str:
        """관심종목 VCP 요약 컨텍스트 생성."""
        return _build_watchlist_summary_context_impl(watchlist, vcp_data)

    def _build_vcp_intent_context(self) -> Tuple[str, str]:
        """VCP/수급 질문용 컨텍스트 생성."""
        return _build_vcp_intent_context_impl(self._fetch_vcp_ai_analysis)

    def _build_news_intent_context(self) -> Tuple[str, str]:
        """뉴스/이슈 질문용 컨텍스트 생성."""
        return _build_news_intent_context_impl(self._fetch_latest_news)

    def _resolve_primary_intent_context(
        self,
        user_message: str,
        market_gate_data: Dict[str, Any],
    ) -> Tuple[str, str, bool]:
        """메시지의 1차 의도를 해석해 컨텍스트/지시문을 반환한다."""
        return _resolve_primary_intent_context_impl(
            user_message=user_message,
            market_gate_data=market_gate_data,
            contains_any_keyword=self._contains_any_keyword,
            build_closing_bet_context=self._build_closing_bet_context,
            build_market_gate_context=self._build_market_gate_context,
            build_vcp_intent_context_fn=self._build_vcp_intent_context,
            build_news_intent_context_fn=self._build_news_intent_context,
        )

    def _build_watchlist_context_bundle(
        self,
        user_message: str,
        watchlist: Optional[list],
        vcp_data: List[dict],
    ) -> Tuple[str, str]:
        """관심종목 컨텍스트와(필요 시) 지시문 오버라이드를 생성한다."""
        return _build_watchlist_context_bundle_impl(
            user_message=user_message,
            watchlist=watchlist,
            vcp_data=vcp_data,
            contains_any_keyword=self._contains_any_keyword,
            build_watchlist_detailed_context=self._build_watchlist_detailed_context,
            build_watchlist_summary_context=self._build_watchlist_summary_context,
        )

    def _build_additional_context(
        self,
        user_message: str,
        watchlist: Optional[list],
        vcp_data: List[dict],
        market_gate_data: Dict[str, Any],
    ) -> Tuple[str, str, bool]:
        """질문 의도별 추가 컨텍스트와 intent 문구를 구성한다."""
        return _build_additional_context_impl(
            user_message=user_message,
            watchlist=watchlist,
            vcp_data=vcp_data,
            market_gate_data=market_gate_data,
            resolve_primary_intent_context_fn=self._resolve_primary_intent_context,
            build_watchlist_context_bundle_fn=self._build_watchlist_context_bundle,
        )

