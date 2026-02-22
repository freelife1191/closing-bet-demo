#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
종목 질의 감지/포맷 유틸
"""

from __future__ import annotations

import re
from typing import Any, Callable, Dict, Optional


_TICKER_REGEX = re.compile(r"\b\d{6}\b")
_RECOMMEND_KEYWORDS = ("추천", "종목", "뭐", "매수", "살까")


def _resolve_ticker(stock: Dict[str, Any]) -> str:
    return str(stock.get("ticker") or stock.get("code") or "").strip()


def _resolve_name(stock: Dict[str, Any]) -> str:
    return str(stock.get("name") or "").strip()


def _resolve_score(stock: Dict[str, Any]) -> Any:
    return stock.get("supply_demand_score", stock.get("score", "N/A"))


def _resolve_score_numeric(stock: Dict[str, Any]) -> float:
    score = _resolve_score(stock)
    try:
        return float(score)
    except (TypeError, ValueError):
        return float("-inf")


def detect_stock_query_from_stock_map(
    message: str,
    stock_map: Dict[str, str],
    ticker_map: Dict[str, str],
    format_stock_context_fn: Callable[[str, str], str],
    logger: Any,
) -> Optional[str]:
    """전체 종목 맵에서 종목명/티커 매칭을 시도한다."""
    if not message:
        return None

    ticker_match = _TICKER_REGEX.search(message)
    if ticker_match:
        ticker = ticker_match.group(0)
        if ticker in ticker_map:
            stock_name = ticker_map[ticker]
            logger.info("Detected stock query by ticker: %s (%s)", stock_name, ticker)
            return format_stock_context_fn(stock_name, ticker)

    for stock_name in sorted(stock_map.keys(), key=len, reverse=True):
        if stock_name and stock_name in message:
            ticker = stock_map[stock_name]
            logger.info("Detected stock query by name: %s (%s)", stock_name, ticker)
            return format_stock_context_fn(stock_name, ticker)

    return None


def detect_stock_query_from_vcp_data(
    message: str,
    vcp_stocks: list[Dict[str, Any]],
    format_stock_info_fn: Callable[[Dict[str, Any]], str],
) -> Optional[str]:
    """VCP 캐시에서 종목명/티커를 매칭한다."""
    if not message:
        return None

    ticker_match = _TICKER_REGEX.search(message)
    ticker_query = ticker_match.group(0) if ticker_match else None

    for stock in vcp_stocks or []:
        stock_name = _resolve_name(stock)
        ticker = _resolve_ticker(stock)
        if not stock_name:
            continue

        if stock_name in message:
            return format_stock_info_fn(stock)
        if ticker_query and ticker and ticker_query == ticker:
            return format_stock_info_fn(stock)

    return None


def detect_stock_query(
    message: str,
    get_cached_data_fn: Callable[[], Dict[str, Any]],
    detect_stock_query_from_vcp_data_fn: Callable[[str, list[Dict[str, Any]]], Optional[str]],
) -> Optional[str]:
    """현재 캐시에서 종목 질의 문맥을 찾는다."""
    cached = get_cached_data_fn() or {}
    vcp_stocks = cached.get("vcp_stocks", [])
    return detect_stock_query_from_vcp_data_fn(message, vcp_stocks)


def fallback_response(user_message: str, vcp_data: list[Dict[str, Any]]) -> str:
    """AI 응답 실패 시 텍스트 폴백."""
    normalized = (user_message or "").strip()
    if any(keyword in normalized for keyword in _RECOMMEND_KEYWORDS) and vcp_data:
        ranked = sorted(vcp_data, key=_resolve_score_numeric, reverse=True)
        lines = ["📌 오늘의 수급 상위 종목:"]
        for stock in ranked[:5]:
            stock_name = _resolve_name(stock) or "N/A"
            score = _resolve_score(stock)
            lines.append(f"- **{stock_name}**: {score}점")
        return "\n".join(lines)
    return "질문을 이해하지 못했습니다."


def format_stock_info(stock: Dict[str, Any]) -> str:
    """종목 요약 포맷."""
    name = _resolve_name(stock) or "N/A"
    ticker = _resolve_ticker(stock) or "N/A"
    score = _resolve_score(stock)
    stage = stock.get("supply_demand_stage", stock.get("stage", ""))
    foreign_5d = stock.get("foreign_5d", 0)
    inst_5d = stock.get("inst_5d", 0)
    double_buy = "✅ 쌍끌이" if stock.get("is_double_buy") else "➖ 단일 수급"

    return "\n".join(
        [
            f"**{name}** ({ticker})",
            f"- 수급 점수: {score}점 ({stage})",
            f"- 외국인 5일 순매수: {foreign_5d:,}",
            f"- 기관 5일 순매수: {inst_5d:,}",
            f"- 시그널: {double_buy}",
        ]
    )


__all__ = [
    "detect_stock_query",
    "detect_stock_query_from_stock_map",
    "detect_stock_query_from_vcp_data",
    "fallback_response",
    "format_stock_info",
]
