#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VCP AI orchestration helper 분해 회귀 테스트
"""

from __future__ import annotations

import asyncio

from engine.vcp_ai_orchestration_helpers import analyze_batch_with_limit, orchestrate_stock_analysis


class _Logger:
    """오케스트레이터가 남긴 경고를 모아 두는 테스트용 로거."""

    def __init__(self):
        self.warnings: list[str] = []

    def warning(self, msg):
        self.warnings.append(str(msg))

    def error(self, _msg):
        return None

    def info(self, _msg):
        return None


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

    result = asyncio.run(
        orchestrate_stock_analysis(
            stock_name="삼성전자",
            stock_data={"ticker": "005930"},
            providers=["gemini", "gpt"],
            second_provider="gpt",
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

    result = asyncio.run(
        orchestrate_stock_analysis(
            stock_name="SKIP 종목",
            stock_data={"ticker": "005930", "skip_gemini": True},
            providers=["gemini", "perplexity"],
            second_provider="perplexity",
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

    result = asyncio.run(
        orchestrate_stock_analysis(
            stock_name="SKIP Second",
            stock_data={"ticker": "005930", "skip_second": True},
            providers=["gemini", "gpt"],
            second_provider="gpt",
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


def _run_with_second_provider(second_provider, providers):
    """확정된 second_provider 하나만 바꿔 가며 오케스트레이터의 선택을 본다.

    세 스텁이 서로 다른 action 을 돌려주므로 결과 사전만으로 어느 쪽이 실행되었는지
    가려낼 수 있다. 폴백과 실행 가능 여부 판정은 resolve_effective_second_provider 가
    맡으므로, 여기서는 오케스트레이터가 받은 값을 고쳐 쓰지 않는지만 본다.
    """

    async def _gemini(_name, _data, prompt=None):
        del prompt
        return {"action": "HOLD"}

    async def _gpt(_name, _data, prompt=None):
        del prompt
        return {"action": "BUY"}

    async def _perplexity(_name, _data, prompt=None):
        del prompt
        return {"action": "SELL"}

    return asyncio.run(
        orchestrate_stock_analysis(
            stock_name="확정값 종목",
            stock_data={"ticker": "005930"},
            providers=providers,
            second_provider=second_provider,
            build_prompt_fn=lambda _name, _data: "PROMPT",
            analyze_with_gemini_fn=_gemini,
            analyze_with_gpt_fn=_gpt,
            analyze_with_perplexity_fn=_perplexity,
            logger=_Logger(),
        )
    )


def test_orchestrator_leaves_second_column_empty_when_provider_is_none():
    """실행할 두 번째 provider 가 없으면 None 이 넘어오고 그 자리를 비운다."""
    result = _run_with_second_provider(None, ["gemini", "gpt", "perplexity"])

    assert result["gemini_recommendation"]["action"] == "HOLD"
    assert result["gpt_recommendation"] is None
    assert result["perplexity_recommendation"] is None


def test_orchestrator_warns_when_no_provider_runs_at_all():
    """Gemini 도 두 번째 provider 도 돌지 않으면 경고를 남기고 빈 결과를 돌려준다.

    이 경고는 실행할 AI 가 하나도 없다는 뜻이고, 두 번째 자리만 비는 상황과 다르다.
    후자는 resolve_effective_second_provider 가 초기화 시점에 따로 알린다.
    """
    logger = _Logger()

    result = asyncio.run(
        orchestrate_stock_analysis(
            stock_name="빈 종목",
            stock_data={"ticker": "005930", "skip_gemini": True},
            providers=["gemini"],
            second_provider=None,
            build_prompt_fn=lambda _name, _data: "PROMPT",
            analyze_with_gemini_fn=_unreachable_provider,
            analyze_with_gpt_fn=_unreachable_provider,
            analyze_with_perplexity_fn=_unreachable_provider,
            logger=logger,
        )
    )

    assert result["gemini_recommendation"] is None
    assert result["gpt_recommendation"] is None
    assert result["perplexity_recommendation"] is None
    assert len(logger.warnings) == 1


async def _unreachable_provider(_name, _data, prompt=None):
    del prompt
    raise AssertionError("실행 가능한 provider 가 없을 때는 아무 provider 도 부르지 않아야 한다")


def test_orchestrator_follows_resolved_provider_without_rechecking_providers():
    """확정값이 perplexity 면 providers 목록을 다시 따지지 않고 그대로 실행한다.

    실행 가능 여부는 resolve_effective_second_provider 가 이미 판정했다. 여기서 한 번 더
    거르면 두 곳의 규칙이 갈려 `[VCP-003]` 과 같은 어긋남이 다시 생긴다.
    """
    result = _run_with_second_provider("perplexity", ["gemini", "gpt"])

    assert result["perplexity_recommendation"]["action"] == "SELL"
    assert result["gpt_recommendation"] is None
