#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
intent_context 유틸 회귀 테스트
"""

import os
import sys


sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from chatbot.intent_context import (
    build_additional_context,
    build_news_intent_context,
    build_vcp_intent_context,
    build_watchlist_context_bundle,
    resolve_primary_intent_context,
)


def test_build_vcp_intent_context_uses_fallback_when_empty():
    context, instruction = build_vcp_intent_context(lambda: "")
    assert "현재 분석된 VCP 시그널이 없습니다" in context
    assert "투자 추천과 근거" in instruction


def test_build_news_intent_context_uses_data_when_available():
    context, instruction = build_news_intent_context(lambda: "헤드라인A")
    assert "헤드라인A" in context
    assert "시장에 미칠 영향" in instruction


def test_resolve_primary_intent_context_market_branch():
    context, instruction, jongga = resolve_primary_intent_context(
        user_message="오늘 시장 시황 어때?",
        market_gate_data={"status": "GREEN"},
        contains_any_keyword=lambda message, keys: any(k in message for k in keys),
        build_closing_bet_context=lambda: ("CB", "CBI"),
        build_market_gate_context=lambda data: f"MG-{data.get('status')}",
        build_vcp_intent_context_fn=lambda: ("VCP", "VCPI"),
        build_news_intent_context_fn=lambda: ("NEWS", "NEWSI"),
    )
    assert context == "MG-GREEN"
    assert "Market Gate" in instruction
    assert jongga is False


def test_build_watchlist_context_bundle_detailed_and_summary():
    detailed_context, detailed_instruction = build_watchlist_context_bundle(
        user_message="내 관심종목 분석해줘",
        watchlist=["삼성전자"],
        vcp_data=[],
        contains_any_keyword=lambda message, keys: any(k in message for k in keys),
        build_watchlist_detailed_context=lambda watchlist, vcp: f"DETAIL-{watchlist[0]}",
        build_watchlist_summary_context=lambda watchlist, vcp: "SUMMARY",
    )
    assert detailed_context.startswith("DETAIL-")
    assert "상세히 진단" in detailed_instruction

    summary_context, summary_instruction = build_watchlist_context_bundle(
        user_message="다른 질문",
        watchlist=["삼성전자"],
        vcp_data=[],
        contains_any_keyword=lambda message, keys: any(k in message for k in keys),
        build_watchlist_detailed_context=lambda watchlist, vcp: "DETAIL",
        build_watchlist_summary_context=lambda watchlist, vcp: "SUMMARY",
    )
    assert summary_context == "SUMMARY"
    assert summary_instruction == ""


def test_build_additional_context_overrides_instruction_with_watchlist_instruction():
    additional, instruction, jongga = build_additional_context(
        user_message="msg",
        watchlist=["A"],
        vcp_data=[],
        market_gate_data={},
        resolve_primary_intent_context_fn=lambda message, market: ("INTENT", "BASE", False),
        build_watchlist_context_bundle_fn=lambda message, watchlist, vcp: ("WATCH", "OVERRIDE"),
    )
    assert additional == "INTENTWATCH"
    assert instruction == "OVERRIDE"
    assert jongga is False
