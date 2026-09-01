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

from engine.config import app_config
from engine.llm_analyzer import GeminiRetryStrategy
from engine.llm_analyzer_retry import (
    GEMINI_RETRY_MODEL_CHAIN,
    build_gemini_retry_model_chain,
    build_model_chain,
)
from engine.vcp_ai_analyzer import VCPMultiAIAnalyzer


EXPECTED_CHAIN = [
    "gemini-3.5-flash-lite",
    "gemini-3.7-flash",
    "gemini-3.1-pro-preview",
    "gemini-2.5-flash-lite",
    "gemini-2.5-flash",
    "gemini-2.5-pro",
]

EXPECTED_ANALYSIS_CHAIN = [
    "gemini-3.7-flash",
    "gemini-3.5-flash-lite",
    "gemini-3.1-pro-preview",
    "gemini-2.5-flash-lite",
    "gemini-2.5-flash",
    "gemini-2.5-pro",
]


class RecordingModels:
    """요청 모델 순서를 기록하는 테스트 더블"""

    def __init__(self, outcomes):
        self._outcomes = outcomes
        self.calls = []

    def generate_content(self, model: str, contents: str, config=None):
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
    strategy = GeminiRetryStrategy(SimpleNamespace(models=models), model="gemini-3.7-flash")

    with patch("engine.llm_analyzer_retry.asyncio.sleep", _no_sleep), patch(
        "engine.llm_analyzer_retry.random.uniform", return_value=0.0
    ):
        result = asyncio.run(strategy.execute("prompt", timeout=3.0, model="gemini-3.7-flash"))

    assert result == '{"ok": true}'
    assert models.calls == EXPECTED_ANALYSIS_CHAIN[:4]
    assert strategy.get_model_name() == EXPECTED_ANALYSIS_CHAIN[3]


def test_vcp_analyzer_retries_in_requested_model_order(monkeypatch):
    """VCP Gemini 재시도는 지정된 모델 순서를 따라야 한다."""
    monkeypatch.setenv("VCP_GEMINI_MODEL", "gemini-3.7-flash")
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
    assert models.calls == EXPECTED_ANALYSIS_CHAIN[:4]


def test_base_chain_definition_stays_pinned():
    """설정 모델을 제외한 나머지 소진 순서는 고정되어야 한다."""
    assert GEMINI_RETRY_MODEL_CHAIN == EXPECTED_CHAIN


def test_llm_and_vcp_runtime_chains_match_when_configured_models_agree(monkeypatch):
    """두 경로를 같은 모델로 설정하면 실제 재시도 체인도 같아야 한다."""
    monkeypatch.setenv("GEMINI_MODEL", "gemini-3.7-flash")
    monkeypatch.setenv("VCP_GEMINI_MODEL", "gemini-3.7-flash")

    llm_chain = GeminiRetryStrategy(
        SimpleNamespace(models=None),
        model=app_config.GEMINI_MODEL,
    )._model_chain
    vcp_chain = build_gemini_retry_model_chain(app_config.VCP_GEMINI_MODEL)

    assert llm_chain == EXPECTED_ANALYSIS_CHAIN
    assert vcp_chain == EXPECTED_ANALYSIS_CHAIN


def test_runtime_chains_diverge_when_configured_models_differ(monkeypatch):
    """설정 모델이 갈라지면 체인 선두도 갈라진다."""
    monkeypatch.setenv("GEMINI_MODEL", "gemini-3.7-flash")
    monkeypatch.setenv("VCP_GEMINI_MODEL", "gemini-2.5-pro")

    llm_chain = build_gemini_retry_model_chain(app_config.GEMINI_MODEL)
    vcp_chain = build_gemini_retry_model_chain(app_config.VCP_GEMINI_MODEL)

    assert llm_chain[0] == "gemini-3.7-flash"
    assert vcp_chain[0] == "gemini-2.5-pro"
    assert llm_chain != vcp_chain


def test_build_gemini_retry_model_chain_prioritizes_configured_model():
    """설정 모델을 첫 번째로 두고 기본 체인의 중복을 제거해야 한다."""
    assert build_gemini_retry_model_chain("gemini-3.7-flash") == EXPECTED_ANALYSIS_CHAIN


def test_build_gemini_retry_model_chain_drops_blocked_models():
    """세션에서 제외된 모델은 체인에서 빠져야 한다."""
    chain = build_gemini_retry_model_chain(
        "gemini-3.7-flash",
        blocked_models=["gemini-3.7-flash", "gemini-2.5-pro"],
    )

    assert "gemini-3.7-flash" not in chain
    assert "gemini-2.5-pro" not in chain
    assert chain[0] == "gemini-3.5-flash-lite"


def test_build_model_chain_is_shared_by_gemini_and_zai_paths():
    """Gemini/Z.ai 두 경로가 같은 체인 구성 규칙을 쓴다."""
    from engine.vcp_ai_analyzer import ZAI_FALLBACK_MODEL_CHAIN

    assert build_gemini_retry_model_chain("gemini-3.7-flash") == build_model_chain(
        "gemini-3.7-flash", GEMINI_RETRY_MODEL_CHAIN
    )
    assert build_model_chain("glm-5.3-flash", ZAI_FALLBACK_MODEL_CHAIN) == [
        "glm-5.3-flash",
        *ZAI_FALLBACK_MODEL_CHAIN,
    ]


def test_build_model_chain_skips_blank_primary_and_is_case_insensitive():
    """빈 설정 모델은 무시하고, 대소문자만 다른 중복은 제거한다."""
    assert build_model_chain("  ", ["a-model", "b-model"]) == ["a-model", "b-model"]
    assert build_model_chain("A-MODEL", ["a-model", "b-model"]) == ["A-MODEL", "b-model"]
