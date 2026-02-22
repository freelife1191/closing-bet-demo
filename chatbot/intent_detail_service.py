#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
의도별 상세 컨텍스트 조합 유틸
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Tuple


def contains_any_keyword(user_message: str, keywords: List[str]) -> bool:
    """문장에 키워드가 하나라도 포함되는지 확인한다."""
    normalized = (user_message or "").lower()
    return any((keyword or "").lower() in normalized for keyword in keywords)


def build_closing_bet_context(
    memory: Any,
    user_id: str,
    fetch_jongga_data_fn: Callable[[], str],
    logger: Any,
) -> Tuple[str, str]:
    """종가베팅 의도 컨텍스트를 생성한다."""
    try:
        memory.add("interest", "종가베팅")
    except Exception:
        pass

    jongga_text = fetch_jongga_data_fn() or "현재 추천 종목이 없습니다."
    logger.info("[User: %s] Closing-bet context prepared", user_id)

    context = "\n".join(
        [
            "\n[종가베팅 추천 종목]",
            str(jongga_text),
        ]
    )
    instruction = (
        "종가베팅 질문입니다. 종가 기준 단기 접근 전략으로 답변하고 "
        "진입 근거/리스크(손절 기준)를 함께 제시하세요."
    )
    return context, instruction


def build_market_gate_context(market_gate_data: Dict[str, Any]) -> str:
    """Market Gate 기반 시장 컨텍스트 텍스트."""
    if not market_gate_data:
        return "\n[Market Gate 상세 분석]\n현재 Market Gate 데이터가 없습니다."

    color = market_gate_data.get("color", "N/A")
    status = market_gate_data.get("status", "N/A")
    total_score = market_gate_data.get("total_score", "N/A")
    reason = market_gate_data.get("gate_reason", "")

    lines = [
        "\n[Market Gate 상세 분석]",
        f"- 색상: {color}",
        f"- 상태: {status}",
        f"- 총점: {total_score}",
    ]
    if reason:
        lines.append(f"- 사유: {reason}")

    sectors = market_gate_data.get("sectors", [])
    if sectors:
        lines.append("- 섹터 동향:")
        for sector in sectors:
            name = sector.get("name", "N/A")
            change_pct = sector.get("change_pct", 0)
            signal = sector.get("signal", "")
            lines.append(f"  - {name}: {change_pct}% ({signal})")

    return "\n".join(lines)


def _find_vcp_row_for_watch(stock_name: str, ticker: str, vcp_data: List[dict]) -> dict | None:
    for row in vcp_data or []:
        row_name = str(row.get("name", "")).strip()
        row_ticker = str(row.get("code") or row.get("ticker") or "").strip()
        if row_name and row_name == stock_name:
            return row
        if ticker and row_ticker and row_ticker == ticker:
            return row
    return None


def build_watchlist_detailed_context(
    watchlist: List[str],
    vcp_data: List[dict],
    stock_map: Dict[str, str],
    format_stock_context_fn: Callable[[str, str], str],
) -> str:
    """관심종목 상세 컨텍스트를 생성한다."""
    lines: list[str] = ["\n[관심종목 상세 분석]"]
    for stock_name in watchlist or []:
        ticker = stock_map.get(stock_name, "")
        detailed = format_stock_context_fn(stock_name, ticker)
        lines.append(detailed)

        matched = _find_vcp_row_for_watch(stock_name, ticker, vcp_data)
        if matched:
            score = matched.get("supply_demand_score", matched.get("score", "N/A"))
            stage = matched.get("supply_demand_stage", matched.get("stage", "N/A"))
            lines.append(f"- VCP 상태: 점수 {score}, 단계 {stage}")
        else:
            lines.append("- VCP 상태: 현재 시그널 데이터 없음")

    return "\n".join(lines)


def build_watchlist_summary_context(watchlist: List[str], vcp_data: List[dict]) -> str:
    """관심종목 VCP 요약 컨텍스트."""
    matched: list[str] = []
    watch_set = {str(item).strip() for item in (watchlist or []) if str(item).strip()}
    if not watch_set:
        return ""

    for row in vcp_data or []:
        name = str(row.get("name", "")).strip()
        if not name or name not in watch_set:
            continue
        score = row.get("supply_demand_score", row.get("score", "N/A"))
        matched.append(f"{name}({score}점)")

    if not matched:
        return ""

    return "\n".join(
        [
            "\n[관심종목 VCP 현황]",
            "- " + ", ".join(matched),
        ]
    )


__all__ = [
    "build_closing_bet_context",
    "build_market_gate_context",
    "build_watchlist_detailed_context",
    "build_watchlist_summary_context",
    "contains_any_keyword",
]

