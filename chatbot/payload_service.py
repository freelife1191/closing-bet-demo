#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
챗봇 요청 payload 구성 서비스
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from .prompts import build_system_prompt


def collect_market_context(bot: Any) -> Tuple[Dict[str, Any], List[dict], Dict[str, Any], Dict[str, Any]]:
    """챗봇 프롬프트용 시장/시그널 컨텍스트를 수집한다."""
    market_gate_data = bot._fetch_market_gate()
    data = bot._get_cached_data()
    vcp_data = data.get("vcp_stocks", [])
    sector_scores = data.get("sector_scores", {})

    market_data = {
        "kospi": market_gate_data.get("kospi_close", "N/A"),
        "kosdaq": market_gate_data.get("kosdaq_close", "N/A"),
        "usd_krw": market_gate_data.get("usd_krw", "N/A"),
        "market_gate": market_gate_data.get("color", "UNKNOWN"),
        "market_status": market_gate_data.get("status", ""),
        "total_score": market_gate_data.get("total_score", 0),
    }

    if market_gate_data.get("sectors"):
        sector_scores = {
            sector["name"]: sector["change_pct"]
            for sector in market_gate_data.get("sectors", [])
        }

    return market_gate_data, vcp_data, sector_scores, market_data


def compose_system_prompt(
    bot: Any,
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
    stock_context = bot._detect_stock_query(user_message)
    system_prompt = build_system_prompt(
        memory_text=bot.memory.format_for_prompt(),
        market_data=market_data,
        vcp_data=vcp_data,
        sector_scores=sector_scores,
        current_model=target_model_name,
        persona=persona,
        watchlist=watchlist,
    )

    if stock_context:
        system_prompt += f"\n\n## 질문 대상 종목 상세\n{stock_context}"
    if additional_context:
        system_prompt += additional_context
    return system_prompt


def build_api_history(bot: Any, session_id: str) -> List[dict]:
    """Gemini SDK 전달용 히스토리(role/parts만 유지)."""
    chat_history = bot.history.get_messages(session_id)
    return [{"role": msg["role"], "parts": msg["parts"]} for msg in chat_history]


def build_content_parts(
    files: Optional[list],
    system_prompt: str,
    intent_instruction: str,
    user_message: str,
    jongga_context: bool,
) -> List[Any]:
    """멀티모달 요청 payload(parts) 생성."""
    content_parts: List[Any] = []
    if files:
        for file in files:
            content_parts.append(
                {"mime_type": file["mime_type"], "data": file["data"]}
            )

    resolved_intent = ""
    if jongga_context:
        resolved_intent = intent_instruction

    full_user_content = (
        f"{system_prompt}\n{resolved_intent}\n\n[사용자 메시지]: {user_message}"
    )
    content_parts.append(full_user_content)
    return content_parts


def build_chat_payload(
    bot: Any,
    user_message: str,
    session_id: str,
    target_model_name: str,
    files: Optional[list],
    watchlist: Optional[list],
    persona: Optional[str],
) -> Tuple[List[dict], List[Any]]:
    """챗/스트림 공통 요청 payload(history + parts)를 구성한다."""
    market_gate_data, vcp_data, sector_scores, market_data = bot._collect_market_context()
    additional_context, intent_instruction, jongga_context = bot._build_additional_context(
        user_message=user_message,
        watchlist=watchlist,
        vcp_data=vcp_data,
        market_gate_data=market_gate_data,
    )
    system_prompt = bot._compose_system_prompt(
        user_message=user_message,
        target_model_name=target_model_name,
        market_data=market_data,
        vcp_data=vcp_data,
        sector_scores=sector_scores,
        watchlist=watchlist,
        persona=persona,
        additional_context=additional_context,
    )
    api_history = bot._build_api_history(session_id)
    content_parts = bot._build_content_parts(
        files=files,
        system_prompt=system_prompt,
        intent_instruction=intent_instruction,
        user_message=user_message,
        jongga_context=jongga_context,
    )
    return api_history, content_parts
