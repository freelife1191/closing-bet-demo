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
    config = SimpleNamespace(ZAI_API_KEY="zai-key", GOOGLE_API_KEY="google-key")
    resolved = resolve_api_key("zai", "explicit-key", config)
    assert resolved == "explicit-key"


def test_resolve_api_key_uses_provider_specific_defaults():
    config = SimpleNamespace(ZAI_API_KEY="zai-key", GOOGLE_API_KEY="google-key")
    assert resolve_api_key("zai", None, config) == "zai-key"
    assert resolve_api_key("gemini", None, config) == "google-key"


def test_llm_analyzer_init_skips_client_creation_when_key_missing(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    monkeypatch.setenv("GOOGLE_API_KEY", "")

    calls = {"create": 0}

    def _fake_create(self, _api_key):
        calls["create"] += 1

    monkeypatch.setattr(llm_analyzer.LLMAnalyzer, "_create_client", _fake_create, raising=True)

    analyzer = llm_analyzer.LLMAnalyzer()
    assert calls["create"] == 0
    assert analyzer.client is None


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


def test_llm_analyzer_missing_key_warning_emits_once(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    monkeypatch.setenv("GOOGLE_API_KEY", "")

    warning_calls = {"count": 0}

    def _warn(_message):
        warning_calls["count"] += 1

    monkeypatch.setattr(llm_analyzer.logger, "warning", _warn, raising=True)

    analyzer = llm_analyzer.LLMAnalyzer()
    _ = analyzer.client
    _ = analyzer.client

    assert warning_calls["count"] == 1
