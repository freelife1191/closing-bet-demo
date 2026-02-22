#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
daily_suggestions_service 회귀 테스트
"""

import os
import sys
from types import SimpleNamespace


sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from chatbot.daily_suggestions_service import generate_daily_suggestions


class _FakeMemory:
    def __init__(self):
        self.saved = []

    def add(self, key, value):
        self.saved.append((key, value))


class _FakeBot:
    def __init__(self):
        self.client = None
        self.current_model_name = "gemini-2.0-flash-lite"
        self.memory = _FakeMemory()
        self.cached = None
        self.response_text = '[{"title":"시장","prompt":"질문"}]'
        self.raise_error = None
        self.jongga_calls = 0
        self.last_prompt_kwargs = None

    def _build_daily_suggestions_cache_key(self, watchlist, persona):
        return f"k:{watchlist}:{persona}"

    def _get_cached_daily_suggestions(self, cache_key, now):
        _ = (cache_key, now)
        return self.cached

    def _fetch_market_gate(self):
        return {"status": "GREEN", "total_score": 7}

    def _fetch_vcp_ai_analysis(self):
        return "VCP_DATA"

    def _fetch_latest_news(self):
        return "NEWS_DATA"

    def _fetch_jongga_data(self):
        self.jongga_calls += 1
        return "JONGGA_DATA"

    def _build_watchlist_suggestions_text(self, watchlist):
        return f"WATCH:{watchlist}"

    def _build_daily_suggestions_prompt(self, **kwargs):
        self.last_prompt_kwargs = kwargs
        return f"PROMPT:{kwargs.get('market_summary')}"

    def _default_daily_suggestions(self):
        return [{"title": "fallback"}]


def test_generate_daily_suggestions_returns_cached_value_first():
    bot = _FakeBot()
    bot.cached = [{"title": "cached"}]

    result = generate_daily_suggestions(bot, watchlist=["A"], persona="vcp")

    assert result == [{"title": "cached"}]
    assert bot.memory.saved == []


def test_generate_daily_suggestions_returns_empty_when_client_missing():
    bot = _FakeBot()
    bot.client = None

    result = generate_daily_suggestions(bot, watchlist=["A"], persona="vcp")

    assert result == []


def test_generate_daily_suggestions_success_saves_cache():
    bot = _FakeBot()
    bot.client = SimpleNamespace(
        models=SimpleNamespace(
            generate_content=lambda **kwargs: SimpleNamespace(text=bot.response_text)
        )
    )

    result = generate_daily_suggestions(bot, watchlist=["A"], persona="vcp")

    assert result[0]["title"] == "시장"
    assert len(bot.memory.saved) == 1
    assert bot.memory.saved[0][1][0]["prompt"] == "질문"


def test_generate_daily_suggestions_prefetches_jongga_once_for_non_vcp():
    bot = _FakeBot()
    bot.client = SimpleNamespace(
        models=SimpleNamespace(
            generate_content=lambda **kwargs: SimpleNamespace(text=bot.response_text)
        )
    )

    result = generate_daily_suggestions(bot, watchlist=["A"], persona=None)

    assert result[0]["title"] == "시장"
    assert bot.jongga_calls == 1
    assert bot.last_prompt_kwargs is not None
    assert bot.last_prompt_kwargs.get("jongga_text") == "JONGGA_DATA"


def test_generate_daily_suggestions_returns_default_on_error():
    bot = _FakeBot()

    def _raise(**kwargs):
        _ = kwargs
        raise RuntimeError("boom")

    bot.client = SimpleNamespace(
        models=SimpleNamespace(generate_content=_raise)
    )

    result = generate_daily_suggestions(bot, watchlist=["A"], persona="vcp")
    assert result == [{"title": "fallback"}]
