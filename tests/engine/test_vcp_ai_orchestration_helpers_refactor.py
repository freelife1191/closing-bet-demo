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


def _run_second_provider_fallback(
    providers,
    perplexity_disabled,
    logger,
    second_provider="perplexity",
    skip_gemini=True,
):
    """두 번째 프로바이더 선택을 보기 위한 실행.

    세 스텁이 서로 다른 action 을 돌려주므로 결과 사전만으로 어느 쪽이 실행되었는지
    가려낼 수 있다. skip_gemini 를 끄면 Gemini 가 함께 돌아 tasks 가 비지 않는 상태가
    되는데, 운영에서는 이쪽이 정상이다. 경고 건수를 세는 검사는 이 차이에 따라 결과가
    달라지므로 두 경우를 나누어 본다.
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
            stock_name="폴백 종목",
            stock_data={"ticker": "005930", "skip_gemini": skip_gemini},
            providers=providers,
            second_provider=second_provider,
            perplexity_disabled=perplexity_disabled,
            build_prompt_fn=lambda _name, _data: "PROMPT",
            analyze_with_gemini_fn=_gemini,
            analyze_with_gpt_fn=_gpt,
            analyze_with_perplexity_fn=_perplexity,
            logger=logger,
        )
    )


def test_disabled_perplexity_falls_back_to_gpt():
    """PERPLEXITY_API_KEY 가 없는 환경에서도 두 번째 AI 열이 비지 않아야 한다."""
    logger = _Logger()

    result = _run_second_provider_fallback(
        providers=["gemini", "gpt"],
        perplexity_disabled=True,
        logger=logger,
    )

    assert result["gpt_recommendation"]["action"] == "BUY"
    assert result["perplexity_recommendation"] is None
    assert logger.warnings == []


def test_disabled_perplexity_without_gpt_and_without_gemini_warns():
    """Gemini 까지 건너뛰면 실행할 프로바이더가 하나도 남지 않아 경고가 나온다.

    여기서 세는 경고 1건은 두 번째 프로바이더 선택이 실패했다는 뜻이 아니라 tasks 가
    통째로 비었다는 뜻이다. 둘을 혼동하지 않도록 Gemini 가 도는 경우를 아래에서 따로 본다.
    """
    logger = _Logger()

    result = _run_second_provider_fallback(
        providers=["gemini", "perplexity"],
        perplexity_disabled=True,
        logger=logger,
    )

    assert result["gemini_recommendation"] is None
    assert result["gpt_recommendation"] is None
    assert result["perplexity_recommendation"] is None
    assert len(logger.warnings) == 1


def test_disabled_perplexity_without_gpt_leaves_second_column_silently_empty():
    """GPT 가 허용 목록에 없으면 폴백이 성립하지 않고, 그 사실이 로그에도 남지 않는다.

    경고는 tasks 가 통째로 빌 때만 나온다. 운영에서는 Gemini 가 거의 항상 돌아 tasks 를
    채우므로 두 번째 열만 조용히 빈 채로 남는다. 이 침묵을 없애는 일은 `[VCP-015]` 가
    맡는다. 여기서는 지금 동작을 있는 그대로 고정해, 고쳤을 때 이 검사가 바뀌도록 한다.
    """
    logger = _Logger()

    result = _run_second_provider_fallback(
        providers=["gemini", "perplexity"],
        perplexity_disabled=True,
        logger=logger,
        skip_gemini=False,
    )

    assert result["gemini_recommendation"]["action"] == "HOLD"
    assert result["gpt_recommendation"] is None
    assert result["perplexity_recommendation"] is None
    assert logger.warnings == []


def test_non_perplexity_second_provider_is_not_rerouted_to_gpt():
    """폴백은 second_provider 가 perplexity 일 때만 걸린다.

    normalize_provider_name 은 z.ai 와 zai 를 "zai" 로 정규화하고, 운영 설정의
    VCP_AI_PROVIDERS 에 z.ai 가 들어 있다. 이 오케스트레이터는 zai 를 부르는 경로를
    갖고 있지 않으므로 아무것도 실행하지 않는 것이 맞다. 폴백 조건에서
    second_provider 검사를 빼면 이 설정까지 GPT 로 넘어간다.
    """
    logger = _Logger()

    result = _run_second_provider_fallback(
        providers=["gemini", "gpt"],
        perplexity_disabled=True,
        logger=logger,
        second_provider="zai",
    )

    assert result["gpt_recommendation"] is None
    assert result["perplexity_recommendation"] is None
    assert len(logger.warnings) == 1


def test_available_perplexity_wins_over_gpt_when_both_are_listed():
    """gpt 와 perplexity 가 함께 허용 목록에 있어도 설정한 두 번째 프로바이더를 지킨다.

    VCP_AI_PROVIDERS=gemini,gpt,perplexity 와 VCP_SECOND_PROVIDER=perplexity 는
    .env.example 의 주석이 유효하다고 적어 둔 조합이다. 폴백 조건이 넓어져 이 조합까지
    GPT 로 넘어가면 설정한 프로바이더가 조용히 무시된다.
    """
    logger = _Logger()

    result = _run_second_provider_fallback(
        providers=["gemini", "gpt", "perplexity"],
        perplexity_disabled=False,
        logger=logger,
    )

    assert result["perplexity_recommendation"]["action"] == "SELL"
    assert result["gpt_recommendation"] is None
    assert logger.warnings == []
