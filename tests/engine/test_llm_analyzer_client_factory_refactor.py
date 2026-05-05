#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LLM analyzer client factory/초기화 분해 회귀 테스트
"""

from __future__ import annotations

from types import SimpleNamespace

from engine import llm_analyzer
from engine.llm_analyzer_client_factory import resolve_api_key


def test_resolve_api_key_prefers_explicit_source():
    config = SimpleNamespace(ZAI_API_KEY="zai-key")
    resolved = resolve_api_key("zai", "explicit-key", config)
    assert resolved == "explicit-key"


def test_resolve_api_key_uses_provider_specific_defaults(monkeypatch):
    """Vertex AI 전환 후 Gemini는 ADC 기반이라 명시적 키가 비어 있어야 한다.

    Vertex가 환경에 구성되어 있으면 'vertex' sentinel, 아니면 '' 반환.
    """
    config = SimpleNamespace(ZAI_API_KEY="zai-key")
    assert resolve_api_key("zai", None, config) == "zai-key"

    # Vertex 미구성 환경: 빈 문자열
    monkeypatch.setattr(
        "engine.genai_client.vertex_configured", lambda: False, raising=False
    )
    assert resolve_api_key("gemini", None, config) == ""

    # Vertex 구성 환경: 'vertex' sentinel
    monkeypatch.setattr(
        "engine.genai_client.vertex_configured", lambda: True, raising=False
    )
    assert resolve_api_key("gemini", None, config) == "vertex"


def test_llm_analyzer_init_skips_zai_creation_when_key_missing(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "zai")
    monkeypatch.setenv("ZAI_API_KEY", "")

    calls = {"create": 0}

    def _fake_create(self, _api_key):
        calls["create"] += 1

    monkeypatch.setattr(llm_analyzer.LLMAnalyzer, "_create_client", _fake_create, raising=True)

    analyzer = llm_analyzer.LLMAnalyzer()
    assert calls["create"] == 0
    assert analyzer.client is None
