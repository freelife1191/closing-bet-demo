#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gemini 모델 재시도 체인 회귀 테스트
"""

import asyncio
import os
import sys
from types import SimpleNamespace
from unittest.mock import patch


sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from engine.llm_analyzer import GeminiRetryStrategy, GEMINI_RETRY_MODEL_CHAIN as LLM_CHAIN
from engine.vcp_ai_analyzer import VCPMultiAIAnalyzer, GEMINI_RETRY_MODEL_CHAIN as VCP_CHAIN


EXPECTED_CHAIN = [
    "gemini-2.0-flash-lite",
    "gemini-2.5-flash-lite",
    "gemini-2.0-flash",
    "gemini-2.5-flash",
    "gemini-3-flash-preview",
]


class RecordingModels:
    """요청 모델 순서를 기록하는 테스트 더블"""

    def __init__(self, outcomes):
        self._outcomes = outcomes
        self.calls = []

    def generate_content(self, model: str, contents: str):
        self.calls.append(model)
        idx = len(self.calls) - 1
        outcome = self._outcomes[idx]
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


async def _no_sleep(_: float) -> None:
    return None


def test_llm_retry_strategy_retries_in_requested_model_order():
    """종가베팅 Gemini 재시도는 지정된 모델 순서를 따라야 한다."""
    models = RecordingModels(
        [
            RuntimeError("429 RATE_LIMIT"),
            RuntimeError("503 UNAVAILABLE"),
            RuntimeError("analysis failure"),
            SimpleNamespace(text='{"ok": true}', model_version=None),
        ]
    )
    strategy = GeminiRetryStrategy(SimpleNamespace(models=models), model="gemini-2.0-flash")

    with patch("engine.llm_analyzer_retry.asyncio.sleep", _no_sleep), patch(
        "engine.llm_analyzer_retry.random.uniform", return_value=0.0
    ):
        result = asyncio.run(strategy.execute("prompt", timeout=3.0, model="gemini-2.0-flash"))

    assert result == '{"ok": true}'
    assert models.calls == EXPECTED_CHAIN[:4]
    assert strategy.get_model_name() == EXPECTED_CHAIN[3]


def test_vcp_analyzer_retries_in_requested_model_order():
    """VCP Gemini 재시도는 지정된 모델 순서를 따라야 한다."""
    models = RecordingModels(
        [
            RuntimeError("429 RESOURCE_EXHAUSTED"),
            RuntimeError("503 UNAVAILABLE"),
            RuntimeError("analysis failure"),
            SimpleNamespace(
                text='{"action":"BUY","confidence":77,"reason":"테스트"}',
                model_version=None,
            ),
        ]
    )

    analyzer = object.__new__(VCPMultiAIAnalyzer)
    analyzer.gemini_client = SimpleNamespace(models=models)

    with patch("engine.vcp_ai_analyzer.asyncio.sleep", _no_sleep), patch(
        "engine.vcp_ai_analyzer.random.randint", return_value=0
    ):
        result = asyncio.run(analyzer._analyze_with_gemini("테스트", {"score": 70}))

    assert result is not None
    assert result["action"] == "BUY"
    assert models.calls == EXPECTED_CHAIN[:4]


def test_llm_and_vcp_retry_chain_definition_match():
    """종가베팅/VCP 두 경로의 체인 정의가 일치해야 한다."""
    assert LLM_CHAIN == EXPECTED_CHAIN
    assert VCP_CHAIN == EXPECTED_CHAIN
