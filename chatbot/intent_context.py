#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
질문 의도 기반 컨텍스트 조합 유틸
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Tuple


def build_vcp_intent_context(fetch_vcp_ai_analysis: Callable[[], str]) -> Tuple[str, str]:
    """VCP/수급 질문용 컨텍스트 생성."""
    vcp_analysis = fetch_vcp_ai_analysis()
    if vcp_analysis:
        context = f"\n\n## [VCP AI 분석 결과 - 매수 추천 종목]\n{vcp_analysis}"
    else:
        context = "\n\n## [VCP 분석]\n현재 분석된 VCP 시그널이 없습니다."
    instruction = "위 VCP AI 분석 결과를 참고하여 투자 추천과 근거를 설명해주세요."
    return context, instruction


def build_news_intent_context(fetch_latest_news: Callable[[], str]) -> Tuple[str, str]:
    """뉴스/이슈 질문용 컨텍스트 생성."""
    news_data = fetch_latest_news()
    if news_data:
        context = f"\n\n## [최근 뉴스]\n{news_data}"
    else:
        context = "\n\n## [뉴스]\n최근 수집된 주요 뉴스가 없습니다."
    instruction = "위 뉴스 데이터를 참고하여 시장에 미칠 영향을 분석해주세요."
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
    """메시지의 1차 의도를 해석해 컨텍스트/지시문을 반환한다."""
    intent_rules: List[Tuple[List[str], Callable[[], Tuple[str, str]], bool]] = [
        (
            ["종가베팅", "종가 베팅", "Closing Betting"],
            build_closing_bet_context,
            True,
        ),
        (
            ["시장", "마켓게이트", "Market Gate", "시황", "장세", "지수"],
            lambda: (
                build_market_gate_context(market_gate_data),
                "위 Market Gate 데이터를 참고하여 현재 시장 상황과 투자 전략을 상세히 분석해주세요.",
            ),
            False,
        ),
        (
            ["VCP", "수급", "추천", "뭐 살", "매수", "시그널"],
            build_vcp_intent_context_fn,
            False,
        ),
        (
            ["뉴스", "호재", "이슈", "속보", "소식"],
            build_news_intent_context_fn,
            False,
        ),
    ]

    for keywords, context_builder, jongga_flag in intent_rules:
        if not contains_any_keyword(user_message, keywords):
            continue
        context, instruction = context_builder()
        return context, instruction, jongga_flag

    return "", "", False


def build_watchlist_context_bundle(
    user_message: str,
    watchlist: Optional[list],
    vcp_data: List[dict],
    contains_any_keyword: Callable[[str, List[str]], bool],
    build_watchlist_detailed_context: Callable[[List[str], List[dict]], str],
    build_watchlist_summary_context: Callable[[List[str], List[dict]], str],
) -> Tuple[str, str]:
    """관심종목 컨텍스트와(필요 시) 지시문 오버라이드를 생성한다."""
    if not watchlist:
        return "", ""

    if contains_any_keyword(
        user_message,
        ["내 종목", "관심 종목", "관심종목", "포트폴리오", "가지고 있는"],
    ):
        context = build_watchlist_detailed_context(watchlist, vcp_data)
        instruction = (
            "위 [내 관심종목 상세 분석 데이터]를 바탕으로, 각 종목의 현재 주가 흐름, "
            "수급 상태, VCP 패턴 여부를 종합하여 상세히 진단해주세요."
        )
        return context, instruction

    return build_watchlist_summary_context(watchlist, vcp_data), ""


def build_additional_context(
    user_message: str,
    watchlist: Optional[list],
    vcp_data: List[dict],
    market_gate_data: Dict[str, Any],
    resolve_primary_intent_context_fn: Callable[[str, Dict[str, Any]], Tuple[str, str, bool]],
    build_watchlist_context_bundle_fn: Callable[[str, Optional[list], List[dict]], Tuple[str, str]],
) -> Tuple[str, str, bool]:
    """질문 의도별 추가 컨텍스트와 intent 문구를 구성한다."""
    intent_context, intent_instruction, jongga_context = resolve_primary_intent_context_fn(
        user_message,
        market_gate_data,
    )
    watchlist_context, watchlist_instruction = build_watchlist_context_bundle_fn(
        user_message,
        watchlist,
        vcp_data,
    )

    additional_context = intent_context + watchlist_context
    if watchlist_instruction:
        intent_instruction = watchlist_instruction
    return additional_context, intent_instruction, jongga_context
