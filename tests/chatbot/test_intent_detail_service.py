#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
intent_detail_service 유틸 회귀 테스트
"""

import os
import sys


sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from chatbot.intent_detail_service import (
    build_closing_bet_context,
    build_market_gate_context,
    build_watchlist_detailed_context,
    build_watchlist_summary_context,
    contains_any_keyword,
)


class _FakeMemory:
    def __init__(self):
        self.saved = []

    def add(self, key, value):
        self.saved.append((key, value))


class _FakeLogger:
    def __init__(self):
        self.events = []

    def info(self, message, *args):
        self.events.append((message, args))


def test_contains_any_keyword_returns_true_on_match():
    assert contains_any_keyword("오늘 시장 시황", ["시황", "수급"]) is True
    assert contains_any_keyword("질문", ["시장", "수급"]) is False


def test_build_closing_bet_context_saves_interest_and_uses_data():
    memory = _FakeMemory()
    logger = _FakeLogger()

    context, instruction = build_closing_bet_context(
        memory=memory,
        user_id="u1",
        fetch_jongga_data_fn=lambda: "A종목",
        logger=logger,
    )
    assert ("interest", "종가베팅") in memory.saved
    assert "A종목" in context
    assert isinstance(instruction, str)


def test_build_market_gate_context_formats_fields():
    text = build_market_gate_context(
        {
            "color": "GREEN",
            "status": "상승",
            "total_score": 8,
            "gate_reason": "수급 양호",
            "sectors": [{"name": "반도체", "change_pct": 1.23, "signal": "강세"}],
        }
    )
    assert "GREEN" in text
    assert "수급 양호" in text
    assert "반도체" in text


def test_build_watchlist_detailed_context_includes_vcp_state():
    text = build_watchlist_detailed_context(
        watchlist=["삼성전자"],
        vcp_data=[{"code": "005930", "score": 91}],
        stock_map={"삼성전자": "005930"},
        format_stock_context_fn=lambda name, ticker: f"{name}:{ticker}",
    )
    assert "삼성전자:005930" in text
    assert "VCP 상태" in text


def test_build_watchlist_summary_context_handles_empty_and_match():
    empty = build_watchlist_summary_context(["A"], [{"name": "B", "score": 1}])
    assert empty == ""

    matched = build_watchlist_summary_context(
        ["A"], [{"name": "A", "code": "0001", "score": 77}]
    )
    assert "A(77점)" in matched
