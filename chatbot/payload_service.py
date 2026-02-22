#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
챗봇 요청 payload 조립 유틸
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from .prompts import build_system_prompt


def collect_market_context(
    bot: Any,
) -> Tuple[Dict[str, Any], List[dict], Dict[str, Any], Dict[str, Any]]:
    """시장 게이트/캐시 데이터를 프롬프트용 컨텍스트로 정규화한다."""
    market_gate_data = bot._fetch_market_gate() or {}
    cached_data = bot._get_cached_data() or {}

    vcp_data = cached_data.get("vcp_stocks", []) or []
    sector_scores = dict(cached_data.get("sector_scores", {}) or {})

    for sector in market_gate_data.get("sectors", []) or []:
        name = sector.get("name")
        change_pct = sector.get("change_pct")
        if name is not None and change_pct is not None:
            sector_scores[str(name)] = change_pct

    market_data = {
        "kospi": market_gate_data.get("kospi_close"),
        "kosdaq": market_gate_data.get("kosdaq_close"),
        "usd_krw": market_gate_data.get("usd_krw"),
        "market_gate": market_gate_data.get("color", market_gate_data.get("status", "")),
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
    """기본 프롬프트와 추가 컨텍스트를 합성한다."""
    memory_text = ""
    if hasattr(bot.memory, "format_for_prompt"):
        memory_text = bot.memory.format_for_prompt()

    system_prompt = build_system_prompt(
        memory_text=memory_text,
        market_data=market_data,
        vcp_data=vcp_data,
        sector_scores=sector_scores,
        current_model=target_model_name,
        persona=persona,
        watchlist=watchlist,
    )

    stock_query_context = ""
    detect_stock_query_fn = getattr(bot, "_detect_stock_query", None)
    if callable(detect_stock_query_fn):
        stock_query_context = detect_stock_query_fn(user_message) or ""
    if stock_query_context:
        additional_context = f"{additional_context}\n\n[종목 조회 컨텍스트]\n{stock_query_context}"

    if additional_context:
        system_prompt = f"{system_prompt}\n\n{additional_context}"

    return system_prompt


def build_api_history(bot: Any, session_id: str) -> List[dict]:
    """Gemini SDK 전달용 최소 히스토리(role/parts)로 변환."""
    api_history: list[dict] = []
    for message in bot.history.get_messages(session_id):
        role = message.get("role")
        parts = message.get("parts")
        if role is None:
            continue
        api_history.append({"role": role, "parts": parts})
    return api_history


def build_content_parts(
    files: Optional[list],
    system_prompt: str,
    intent_instruction: str,
    user_message: str,
    jongga_context: bool,
) -> List[Any]:
    """멀티모달 요청 body(parts)를 생성한다."""
    content_parts: list[Any] = []
    for file_obj in files or []:
        content_parts.append(file_obj)

    sections = [system_prompt]
    if jongga_context and intent_instruction:
        sections.append(f"[질의 의도 가이드]\n{intent_instruction}")
    sections.append(f"[사용자 메시지]: {user_message}")
    content_parts.append("\n\n".join(sections))
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
    """단일/스트림 공통 요청 payload(history + parts)를 빌드한다."""
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


__all__ = [
    "build_api_history",
    "build_chat_payload",
    "build_content_parts",
    "collect_market_context",
    "compose_system_prompt",
]

