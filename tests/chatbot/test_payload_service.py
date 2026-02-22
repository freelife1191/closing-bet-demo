#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
payload_service 유틸 회귀 테스트
"""

import os
import sys


sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from chatbot.payload_service import (
    build_api_history,
    build_chat_payload,
    build_content_parts,
    collect_market_context,
)


class _FakeHistory:
    def __init__(self):
        self.messages = []

    def get_messages(self, session_id):
        _ = session_id
        return self.messages


class _FakeMemory:
    def format_for_prompt(self):
        return "MEM"


class _FakeBot:
    def __init__(self):
        self.history = _FakeHistory()
        self.memory = _FakeMemory()
        self.stock_query = ""

    def _fetch_market_gate(self):
        return {
            "kospi_close": 2600,
            "kosdaq_close": 850,
            "usd_krw": 1380,
            "color": "GREEN",
            "status": "상승",
            "total_score": 8,
            "sectors": [{"name": "반도체", "change_pct": 1.2}],
        }

    def _get_cached_data(self):
        return {"vcp_stocks": [{"name": "A"}], "sector_scores": {"기본": 0.1}}

    def _detect_stock_query(self, user_message):
        _ = user_message
        return self.stock_query

    def _collect_market_context(self):
        return collect_market_context(self)

    def _build_additional_context(self, **kwargs):
        _ = kwargs
        return "ADD", "INST", False

    def _compose_system_prompt(self, **kwargs):
        return "SYS"

    def _build_api_history(self, session_id):
        return build_api_history(self, session_id)

    def _build_content_parts(self, **kwargs):
        return build_content_parts(**kwargs)


def test_collect_market_context_overrides_sector_scores_from_market_gate():
    bot = _FakeBot()
    market_gate_data, vcp_data, sector_scores, market_data = collect_market_context(bot)
    assert market_gate_data["color"] == "GREEN"
    assert vcp_data[0]["name"] == "A"
    assert sector_scores["반도체"] == 1.2
    assert market_data["market_gate"] == "GREEN"


def test_build_api_history_keeps_role_and_parts_only():
    bot = _FakeBot()
    bot.history.messages = [
        {"role": "user", "parts": "hi", "extra": 1},
        {"role": "model", "parts": "hello", "extra": 2},
    ]
    result = build_api_history(bot, "s1")
    assert result == [{"role": "user", "parts": "hi"}, {"role": "model", "parts": "hello"}]


def test_build_content_parts_includes_intent_only_for_jongga():
    files = [{"mime_type": "text/plain", "data": "abc"}]
    with_intent = build_content_parts(files, "SYS", "INST", "Q", True)
    without_intent = build_content_parts(files, "SYS", "INST", "Q", False)

    assert with_intent[0]["mime_type"] == "text/plain"
    assert "INST" in with_intent[-1]
    assert "INST" not in without_intent[-1]


def test_build_chat_payload_orchestrates_substeps():
    bot = _FakeBot()
    bot.history.messages = [{"role": "user", "parts": "prev"}]
    api_history, parts = build_chat_payload(
        bot=bot,
        user_message="질문",
        session_id="s1",
        target_model_name="gemini-2.0-flash-lite",
        files=[],
        watchlist=None,
        persona=None,
    )
    assert api_history == [{"role": "user", "parts": "prev"}]
    assert parts[-1].endswith("[사용자 메시지]: 질문")
