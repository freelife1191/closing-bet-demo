#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
의도/관심종목 상세 컨텍스트 빌더 서비스
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Tuple


def contains_any_keyword(user_message: str, keywords: List[str]) -> bool:
    """문자열에 키워드 중 하나라도 포함되는지 확인."""
    return any(keyword in user_message for keyword in keywords)


def build_closing_bet_context(
    memory: Any,
    user_id: str,
    fetch_jongga_data_fn: Callable[[], str],
    logger: Any,
) -> Tuple[str, str]:
    """종가베팅 의도 컨텍스트/지시문 생성."""
    memory.add("interest", "종가베팅")
    logger.info("Auto-saved interest: 종가베팅 for user %s", user_id)

    jongga_data = fetch_jongga_data_fn()
    if jongga_data:
        context_text = f"\n\n## [종가베팅 추천 종목]\n{jongga_data}"
    else:
        context_text = "\n\n## [종가베팅 데이터]\n현재 추천할 만한 종가베팅 시그널이 없습니다."

    from .prompts import INTENT_PROMPTS

    intent_instruction = INTENT_PROMPTS.get("closing_bet", "")
    return context_text, intent_instruction


def build_market_gate_context(market_gate_data: Dict[str, Any]) -> str:
    """시장/마켓게이트 질문용 컨텍스트 생성."""
    if not market_gate_data:
        return ""

    gate_color = market_gate_data.get("color", "UNKNOWN")
    gate_status = market_gate_data.get("status", "")
    gate_score = market_gate_data.get("total_score", 0)
    gate_reason = market_gate_data.get("gate_reason", "")

    sectors = market_gate_data.get("sectors", [])[:5]
    sectors_text = "\n".join(
        [f"  - {s['name']}: {s['change_pct']:+.2f}% ({s['signal']})" for s in sectors]
    )

    return f"""
## [Market Gate 상세 분석]
- **상태**: {gate_color} ({gate_status})
- **점수**: {gate_score}점
- **판단 근거**: {gate_reason}

### 주요 지수


### 섹터 동향
{sectors_text}
"""


def build_watchlist_detailed_context(
    watchlist: List[str],
    vcp_data: List[dict],
    stock_map: Dict[str, str],
    format_stock_context_fn: Callable[[str, str], str],
) -> str:
    """관심종목 상세 컨텍스트 생성."""
    watchlist_context = "\n\n## [내 관심종목 상세 분석 데이터]\n"
    for stock_name in watchlist:
        ticker = stock_map.get(stock_name)
        if not ticker:
            ticker = stock_name if stock_name.isdigit() else None

        if ticker:
            stock_detail = format_stock_context_fn(stock_name, ticker)
            watchlist_context += stock_detail + "\n"
            match = next((s for s in vcp_data if s.get("code") == ticker), None)
            if match:
                watchlist_context += (
                    f"-> [VCP 상태]: 현재 VCP 패턴 포착됨 ({match.get('score')}점)\n"
                )
        else:
            watchlist_context += f"- {stock_name}: (종목 코드를 찾을 수 없음)\n"
    return watchlist_context


def build_watchlist_summary_context(
    watchlist: List[str],
    vcp_data: List[dict],
) -> str:
    """관심종목 VCP 요약 컨텍스트 생성."""
    summary = []
    for stock_name in watchlist:
        match = next(
            (
                stock
                for stock in vcp_data
                if stock.get("name") == stock_name or stock.get("code") == stock_name
            ),
            None,
        )
        if match:
            summary.append(f"{stock_name}({match.get('score', 0)}점)")

    if not summary:
        return ""
    return f"\n\n## [관심종목 VCP 요약]\n{', '.join(summary)}\n"
