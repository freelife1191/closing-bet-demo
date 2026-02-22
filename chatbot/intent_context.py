#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
의도별 컨텍스트 분기 유틸
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Tuple


_CLOSING_BET_KEYWORDS = ["종가", "종가베팅", "마감", "장마감", "베팅"]
_MARKET_KEYWORDS = ["시장", "시황", "코스피", "코스닥", "섹터", "마켓게이트", "market gate"]
_VCP_KEYWORDS = ["vcp", "수급", "추천", "매수", "종목"]
_NEWS_KEYWORDS = ["뉴스", "이슈", "헤드라인", "공시", "기사"]
_WATCHLIST_DETAIL_KEYWORDS = ["분석", "진단", "자세히", "상세"]


def build_vcp_intent_context(fetch_vcp_ai_analysis_fn: Callable[[], str]) -> Tuple[str, str]:
    """VCP 의도 컨텍스트를 생성한다."""
    vcp_text = (fetch_vcp_ai_analysis_fn() or "").strip()
    if not vcp_text:
        vcp_text = "현재 분석된 VCP 시그널이 없습니다."

    context = "\n".join(["\n[VCP AI 분석 결과]", vcp_text])
    instruction = "VCP 데이터에 근거해 투자 추천과 근거, 리스크를 함께 제시하세요."
    return context, instruction


def build_news_intent_context(fetch_latest_news_fn: Callable[[], str]) -> Tuple[str, str]:
    """뉴스 의도 컨텍스트를 생성한다."""
    news_text = (fetch_latest_news_fn() or "").strip()
    if not news_text:
        news_text = "현재 수집된 뉴스가 없습니다."

    context = "\n".join(["\n[최근 뉴스]", news_text])
    instruction = "뉴스 핵심과 시장에 미칠 영향을 요약하고 투자 시사점을 제시하세요."
    return context, instruction


def resolve_primary_intent_context(
    user_message: str,
    market_gate_data: Dict[str, Any],
    contains_any_keyword: Callable[[str, List[str]], bool],
    build_closing_bet_context: Callable[[], Tuple[str, str]],
    build_market_gate_context: Callable[[Dict[str, Any]], str],
    build_vcp_intent_context_fn: Callable[[], Tuple[str, str]],
    build_news_intent_context_fn: Callable[[], Tuple[str, str]],
) -> Tuple[str, str, bool]:
    """1차 의도에 따른 컨텍스트/지시문/종가베팅 여부를 반환한다."""
    if contains_any_keyword(user_message, _CLOSING_BET_KEYWORDS):
        context, instruction = build_closing_bet_context()
        return context, instruction, True

    if contains_any_keyword(user_message, _MARKET_KEYWORDS):
        context = build_market_gate_context(market_gate_data)
        instruction = "Market Gate 상태를 중심으로 시장 요약과 대응 전략을 안내하세요."
        return context, instruction, False

    if contains_any_keyword(user_message, _NEWS_KEYWORDS):
        context, instruction = build_news_intent_context_fn()
        return context, instruction, False

    if contains_any_keyword(user_message, _VCP_KEYWORDS):
        context, instruction = build_vcp_intent_context_fn()
        return context, instruction, False

    return "", "", False


def build_watchlist_context_bundle(
    user_message: str,
    watchlist: Optional[list],
    vcp_data: List[dict],
    contains_any_keyword: Callable[[str, List[str]], bool],
    build_watchlist_detailed_context: Callable[[List[str], List[dict]], str],
    build_watchlist_summary_context: Callable[[List[str], List[dict]], str],
) -> Tuple[str, str]:
    """관심종목 컨텍스트/의도 지시문 오버라이드를 생성한다."""
    if not watchlist:
        return "", ""

    if contains_any_keyword(user_message, _WATCHLIST_DETAIL_KEYWORDS):
        context = build_watchlist_detailed_context(watchlist, vcp_data)
        instruction = "관심종목을 상세히 진단하고 종목별 강점/리스크를 분리해 설명하세요."
        return context, instruction

    context = build_watchlist_summary_context(watchlist, vcp_data)
    return context, ""


def build_additional_context(
    user_message: str,
    watchlist: Optional[list],
    vcp_data: List[dict],
    market_gate_data: Dict[str, Any],
    resolve_primary_intent_context_fn: Callable[[str, Dict[str, Any]], Tuple[str, str, bool]],
    build_watchlist_context_bundle_fn: Callable[[str, Optional[list], List[dict]], Tuple[str, str]],
) -> Tuple[str, str, bool]:
    """의도 컨텍스트와 관심종목 컨텍스트를 병합한다."""
    intent_context, intent_instruction, jongga_context = resolve_primary_intent_context_fn(
        user_message,
        market_gate_data,
    )
    watchlist_context, watchlist_instruction = build_watchlist_context_bundle_fn(
        user_message,
        watchlist,
        vcp_data,
    )

    additional_context = f"{intent_context}{watchlist_context}"
    final_instruction = watchlist_instruction or intent_instruction
    return additional_context, final_instruction, jongga_context


__all__ = [
    "build_additional_context",
    "build_news_intent_context",
    "build_vcp_intent_context",
    "build_watchlist_context_bundle",
    "resolve_primary_intent_context",
]

