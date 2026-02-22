#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KRStockChatbot 데이터 접근/조회 래퍼 믹스인.
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .daily_suggestions_service import generate_daily_suggestions
from .data_service import (
    build_daily_suggestions_cache_key as _build_daily_suggestions_cache_key_impl,
    build_daily_suggestions_prompt as _build_daily_suggestions_prompt_impl,
    build_watchlist_suggestions_text as _build_watchlist_suggestions_text_impl,
    default_daily_suggestions as _default_daily_suggestions_impl,
    fetch_latest_news as _fetch_latest_news_impl,
    fetch_market_gate as _fetch_market_gate_impl,
    fetch_mock_data as _fetch_mock_data_impl,
    fetch_vcp_ai_analysis as _fetch_vcp_ai_analysis_impl,
    get_cached_daily_suggestions as _get_cached_daily_suggestions_impl,
    get_cached_data as _get_cached_data_impl,
)
from .markdown_utils import _normalize_markdown_text
from .payload_service import collect_market_context as _collect_market_context_impl
from .stock_context import (
    fetch_institutional_trend,
    fetch_signal_history,
    fetch_stock_history,
    format_stock_context,
)
from .stock_query_service import (
    detect_stock_query as _detect_stock_query_impl,
    detect_stock_query_from_stock_map as _detect_stock_query_from_stock_map_impl,
    detect_stock_query_from_vcp_data as _detect_stock_query_from_vcp_data_impl,
)

logger = logging.getLogger(__name__)
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"


class CoreDataAccessMixin:
    """`KRStockChatbot`의 데이터 접근/캐시/종목질의 래퍼."""

    def _get_cached_data(self) -> Dict[str, Any]:
        """Fetch market data with caching"""
        return _get_cached_data_impl(self)

    def _fetch_mock_data(self):
        """폴백용 Mock 데이터 (실제 데이터 로드 실패 시)"""
        return _fetch_mock_data_impl()

    def _fetch_market_gate(self) -> Dict[str, Any]:
        """market_gate.json에서 최신 시장 상태 조회"""
        return _fetch_market_gate_impl(DATA_DIR)

    def _fetch_vcp_ai_analysis(self) -> str:
        """kr_ai_analysis.json에서 VCP AI 분석 결과 조회 (상위 5개)"""
        return _fetch_vcp_ai_analysis_impl(DATA_DIR)

    def _build_daily_suggestions_cache_key(
        self,
        watchlist: Optional[list],
        persona: Optional[str],
    ) -> str:
        """일일 추천 캐시 키 생성."""
        return _build_daily_suggestions_cache_key_impl(watchlist, persona)

    def _get_cached_daily_suggestions(
        self,
        cache_key: str,
        now: datetime,
    ) -> Optional[List[Dict[str, str]]]:
        """유효한(1시간 이내) 일일 추천 캐시 조회."""
        return _get_cached_daily_suggestions_impl(self.memory, cache_key, now)

    def _build_watchlist_suggestions_text(self, watchlist: Optional[list]) -> str:
        """일일 추천 생성용 관심종목 상세 텍스트 구성."""
        return _build_watchlist_suggestions_text_impl(
            watchlist=watchlist,
            stock_map=self.stock_map,
            format_stock_context_fn=self._format_stock_context,
        )

    def _build_daily_suggestions_prompt(
        self,
        persona: Optional[str],
        market_summary: str,
        vcp_text: str,
        news_text: str,
        watchlist_text: str,
        jongga_text: Optional[str] = None,
    ) -> str:
        """페르소나별 추천 질문 생성 프롬프트 구성."""
        return _build_daily_suggestions_prompt_impl(
            persona=persona,
            market_summary=market_summary,
            vcp_text=vcp_text,
            news_text=news_text,
            watchlist_text=watchlist_text,
            fetch_jongga_data_fn=self._fetch_jongga_data,
            jongga_text=jongga_text,
        )

    def _default_daily_suggestions(self) -> List[Dict[str, str]]:
        """일일 추천 생성 실패 시 기본 질문 세트."""
        return _default_daily_suggestions_impl()

    def get_daily_suggestions(
        self,
        watchlist: list = None,
        persona: str = None,
    ) -> List[Dict[str, str]]:
        """시장/데이터/페르소나 기반 일일 추천 질문 5개 생성."""
        return generate_daily_suggestions(
            bot=self,
            watchlist=watchlist,
            persona=persona,
        )

    def _fetch_latest_news(self) -> str:
        """jongga_v2_latest.json 내 뉴스 데이터 조회 (최근 5개)"""
        return _fetch_latest_news_impl(DATA_DIR)

    def _fetch_stock_history(self, ticker: str) -> str:
        """daily_prices.csv에서 최근 5일 주가 조회"""
        return fetch_stock_history(DATA_DIR, ticker, logger)

    def _fetch_institutional_trend(self, ticker: str) -> str:
        """all_institutional_trend_data.csv에서 수급 데이터 조회 (최근 5일)"""
        return fetch_institutional_trend(DATA_DIR, ticker)

    def _fetch_signal_history(self, ticker: str) -> str:
        """signals_log.csv에서 VCP 시그널 이력 조회"""
        return fetch_signal_history(DATA_DIR, ticker)

    def _format_stock_context(self, name: str, ticker: str) -> str:
        """종목 관련 모든 데이터 통합"""
        price_txt = self._fetch_stock_history(ticker)
        trend_txt = self._fetch_institutional_trend(ticker)
        signal_txt = self._fetch_signal_history(ticker)
        return format_stock_context(name, ticker, price_txt, trend_txt, signal_txt)

    def _detect_stock_query_from_stock_map(self, message: str) -> Optional[str]:
        """전체 종목 맵에서 종목 질문을 감지해 상세 컨텍스트를 반환한다."""
        return _detect_stock_query_from_stock_map_impl(
            message=message,
            stock_map=self.stock_map,
            ticker_map=self.ticker_map,
            format_stock_context_fn=self._format_stock_context,
            logger=logger,
        )

    def _detect_stock_query_from_vcp_data(self, message: str) -> Optional[str]:
        """VCP 캐시 데이터에서 종목 질문을 감지해 요약 정보를 반환한다."""
        vcp_stocks = self._get_cached_data().get("vcp_stocks", [])
        return _detect_stock_query_from_vcp_data_impl(
            message=message,
            vcp_stocks=vcp_stocks,
            format_stock_info_fn=self._format_stock_info,
        )

    def _detect_stock_query(self, message: str) -> Optional[str]:
        """
        종목 관련 질문 감지.
        현재 동작 호환을 위해 VCP 캐시 기반 탐지 경로를 우선(사실상 단일) 사용한다.
        """
        return _detect_stock_query_impl(
            message=message,
            get_cached_data_fn=self._get_cached_data,
            detect_stock_query_from_vcp_data_fn=lambda msg, stocks: _detect_stock_query_from_vcp_data_impl(
                message=msg,
                vcp_stocks=stocks,
                format_stock_info_fn=self._format_stock_info,
            ),
        )

    def _normalize_markdown_response(self, text: str) -> str:
        """LLM 응답의 자주 깨지는 마크다운 문법을 안전하게 정규화"""
        return _normalize_markdown_text(text)

    def _collect_market_context(
        self,
    ) -> Tuple[Dict[str, Any], List[dict], Dict[str, Any], Dict[str, Any]]:
        """챗봇 프롬프트용 시장/시그널 컨텍스트를 수집한다."""
        return _collect_market_context_impl(self)
