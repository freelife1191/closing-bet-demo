#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
종목 질의 감지/포맷팅 서비스
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional


def detect_stock_query_from_stock_map(
    message: str,
    stock_map: Dict[str, str],
    ticker_map: Dict[str, str],
    format_stock_context_fn: Callable[[str, str], str],
    logger: Any,
) -> Optional[str]:
    """전체 종목 맵에서 종목 질문을 감지해 상세 컨텍스트를 반환한다."""
    detected_name = None
    detected_ticker = None

    for name, ticker in stock_map.items():
        if name in message:
            detected_name = name
            detected_ticker = ticker
            break

    if not detected_ticker:
        for ticker, name in ticker_map.items():
            if ticker in message:
                detected_name = name
                detected_ticker = ticker
                break

    if detected_name and detected_ticker:
        logger.info("Detected stock query: %s", detected_name)
        return format_stock_context_fn(detected_name, detected_ticker)
    return None


def detect_stock_query_from_vcp_data(
    message: str,
    vcp_stocks: List[dict],
    format_stock_info_fn: Callable[[Dict[str, Any]], str],
) -> Optional[str]:
    """VCP 캐시 데이터에서 종목 질문을 감지해 요약 정보를 반환한다."""
    for stock in vcp_stocks:
        name = stock.get("name", "")
        ticker = stock.get("ticker", "")
        if name and (name in message or ticker in message):
            return format_stock_info_fn(stock)
    return None


def detect_stock_query(
    message: str,
    get_cached_data_fn: Callable[[], Dict[str, Any]],
    detect_stock_query_from_vcp_data_fn: Callable[[str, List[dict]], Optional[str]],
) -> Optional[str]:
    """
    종목 관련 질문 감지.
    현재 동작 호환을 위해 VCP 캐시 기반 탐지 경로를 우선(사실상 단일) 사용한다.
    """
    data = get_cached_data_fn()
    vcp_stocks = data.get("vcp_stocks", [])
    return detect_stock_query_from_vcp_data_fn(message, vcp_stocks)


def fallback_response(user_message: str, vcp_data: List[dict]) -> str:
    """AI 사용 불가 시 폴백 응답."""
    lower_msg = user_message.lower()
    if any(kw in lower_msg for kw in ["뭐 살", "추천", "종목", "top"]):
        if vcp_data:
            response = "📊 **오늘의 수급 상위 종목**\n\n"
            for i, stock in enumerate(vcp_data[:5], 1):
                name = stock.get("name", "N/A")
                score = stock.get("supply_demand_score", 0)
                response += f"{i}. **{name}**: {score}점\n"
            return response
        return "현재 데이터를 불러올 수 없습니다."
    return "질문을 이해하지 못했습니다."


def format_stock_info(stock: Dict[str, Any]) -> str:
    """종목 정보 포맷팅."""
    name = stock.get("name", "N/A")
    ticker = stock.get("ticker", "")
    score = stock.get("supply_demand_score", 0)
    stage = stock.get("supply_demand_stage", "")
    double = "✅ 쌍끌이" if stock.get("is_double_buy") else ""

    foreign_5d = stock.get("foreign_5d", 0)
    inst_5d = stock.get("inst_5d", 0)

    return f"""**{name}** ({ticker})
- 수급 점수: {score}점 ({stage})
- 외국인 5일: {foreign_5d}주
- 기관 5일: {inst_5d}주
{double}"""
