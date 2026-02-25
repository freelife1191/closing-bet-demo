#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VCP AI orchestration helper 분해 회귀 테스트
"""

from __future__ import annotations

import asyncio

from engine.vcp_ai_orchestration_helpers import analyze_batch_with_limit, orchestrate_stock_analysis


def test_orchestrate_stock_analysis_merges_provider_results():
    calls = {"prompt": 0}

    def _build_prompt(_name, _data):
        calls["prompt"] += 1
        return "PROMPT"

    async def _gemini(_name, _data, prompt=None):
        assert prompt == "PROMPT"
        return {"action": "BUY"}

    async def _gpt(_name, _data, prompt=None):
        assert prompt == "PROMPT"
        return {"action": "HOLD"}

    async def _perplexity(_name, _data, prompt=None):
        del prompt
        return None

    class _Logger:
        @staticmethod
        def warning(_msg):
            return None

        @staticmethod
        def error(_msg):
            return None

    result = asyncio.run(
        orchestrate_stock_analysis(
            stock_name="삼성전자",
            stock_data={"ticker": "005930"},
            providers=["gemini", "gpt"],
            second_provider="gpt",
            perplexity_disabled=True,
            build_prompt_fn=_build_prompt,
            analyze_with_gemini_fn=_gemini,
            analyze_with_gpt_fn=_gpt,
            analyze_with_perplexity_fn=_perplexity,
            logger=_Logger(),
        )
    )

    assert calls["prompt"] == 1
    assert result["gemini_recommendation"]["action"] == "BUY"
    assert result["gpt_recommendation"]["action"] == "HOLD"


def test_analyze_batch_with_limit_collects_success_count():
    class _Logger:
        @staticmethod
        def info(_msg):
            return None

        @staticmethod
        def error(_msg):
            return None

    async def _analyze(name, stock):
        if name == "B":
            return None
        return {"ticker": stock["ticker"]}

    stocks = [
        {"ticker": "A1", "name": "A"},
        {"ticker": "B1", "name": "B"},
    ]

    results, success_count = asyncio.run(
        analyze_batch_with_limit(
            stocks=stocks,
            concurrency=2,
            analyze_stock_fn=_analyze,
            logger=_Logger(),
        )
    )

    assert success_count == 1
    assert "A1" in results
    assert "B1" not in results


def test_orchestrate_stock_analysis_skips_gemini_when_flag_is_set():
    calls = {"gemini": 0, "perplexity": 0}

    def _build_prompt(_name, _data):
        return "PROMPT"

    async def _gemini(_name, _data, prompt=None):
        del prompt
        calls["gemini"] += 1
        return {"action": "BUY"}

    async def _gpt(_name, _data, prompt=None):
        del prompt
        return None

    async def _perplexity(_name, _data, prompt=None):
        assert prompt == "PROMPT"
        calls["perplexity"] += 1
        return {"action": "SELL"}

    class _Logger:
        @staticmethod
        def warning(_msg):
            return None

        @staticmethod
        def error(_msg):
            return None

    result = asyncio.run(
        orchestrate_stock_analysis(
            stock_name="SKIP 종목",
            stock_data={"ticker": "005930", "skip_gemini": True},
            providers=["gemini", "perplexity"],
            second_provider="perplexity",
            perplexity_disabled=False,
            build_prompt_fn=_build_prompt,
            analyze_with_gemini_fn=_gemini,
            analyze_with_gpt_fn=_gpt,
            analyze_with_perplexity_fn=_perplexity,
            logger=_Logger(),
        )
    )

    assert calls["gemini"] == 0
    assert calls["perplexity"] == 1
    assert result["gemini_recommendation"] is None
    assert result["perplexity_recommendation"]["action"] == "SELL"


def test_orchestrate_stock_analysis_skips_second_provider_when_flag_is_set():
    calls = {"gemini": 0, "gpt": 0}

    def _build_prompt(_name, _data):
        return "PROMPT"

    async def _gemini(_name, _data, prompt=None):
        assert prompt == "PROMPT"
        calls["gemini"] += 1
        return {"action": "BUY"}

    async def _gpt(_name, _data, prompt=None):
        del prompt
        calls["gpt"] += 1
        return {"action": "SELL"}

    async def _perplexity(_name, _data, prompt=None):
        del prompt
        return None

    class _Logger:
        @staticmethod
        def warning(_msg):
            return None

        @staticmethod
        def error(_msg):
            return None

    result = asyncio.run(
        orchestrate_stock_analysis(
            stock_name="SKIP Second",
            stock_data={"ticker": "005930", "skip_second": True},
            providers=["gemini", "gpt"],
            second_provider="gpt",
            perplexity_disabled=False,
            build_prompt_fn=_build_prompt,
            analyze_with_gemini_fn=_gemini,
            analyze_with_gpt_fn=_gpt,
            analyze_with_perplexity_fn=_perplexity,
            logger=_Logger(),
        )
    )

    assert calls["gemini"] == 1
    assert calls["gpt"] == 0
    assert result["gemini_recommendation"]["action"] == "BUY"
    assert result["gpt_recommendation"] is None
