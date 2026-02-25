#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VCP AI Analyzer 성능/회귀 보강 테스트
"""

import asyncio
import os
import sys
from types import SimpleNamespace


sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from engine.vcp_ai_analyzer import VCPMultiAIAnalyzer


def test_parse_json_response_normalizes_action_for_embedded_json():
    analyzer = object.__new__(VCPMultiAIAnalyzer)
    payload = "analysis...\n{\"action\":\"strong_buy\",\"confidence\":77,\"reason\":\"r\"}\n"

    parsed = analyzer._parse_json_response(payload)

    assert parsed is not None
    assert parsed["action"] == "HOLD"
    assert parsed["confidence"] == 77


def test_get_available_providers_excludes_perplexity_when_disabled(monkeypatch):
    analyzer = object.__new__(VCPMultiAIAnalyzer)
    analyzer.gemini_client = object()
    analyzer.gpt_client = None
    analyzer.perplexity_disabled = True

    monkeypatch.setenv("PERPLEXITY_API_KEY", "dummy")
    providers = analyzer.get_available_providers()

    assert providers == ["gemini"]


def test_analyze_with_gpt_uses_to_thread(monkeypatch):
    analyzer = object.__new__(VCPMultiAIAnalyzer)
    analyzer.gpt_client = SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(
                create=lambda **_kwargs: SimpleNamespace(
                    choices=[SimpleNamespace(message=SimpleNamespace(content='{"action":"BUY","confidence":80}'))]
                )
            )
        )
    )
    analyzer._build_vcp_prompt = lambda *_args, **_kwargs: "prompt"
    called = {"to_thread": 0}

    async def _fake_to_thread(func, *args, **kwargs):
        called["to_thread"] += 1
        return func(*args, **kwargs)

    monkeypatch.setattr("engine.vcp_ai_analyzer.asyncio.to_thread", _fake_to_thread)

    result = asyncio.run(analyzer._analyze_with_gpt("삼성전자", {"score": 70}))

    assert called["to_thread"] == 1
    assert result is not None
    assert result["action"] == "BUY"


def test_analyze_with_perplexity_reuses_single_async_client_for_retries(monkeypatch):
    analyzer = object.__new__(VCPMultiAIAnalyzer)
    analyzer.perplexity_disabled = False
    analyzer._build_vcp_prompt = lambda *_args, **_kwargs: "prompt"

    monkeypatch.setenv("PERPLEXITY_API_KEY", "dummy-key")
    monkeypatch.setenv("VCP_PERPLEXITY_MODEL", "sonar-pro")

    class _Resp:
        def __init__(self, status_code, payload=None, text=""):
            self.status_code = status_code
            self._payload = payload or {}
            self.text = text

        def json(self):
            return self._payload

    class _FakeAsyncClient:
        enter_count = 0
        post_count = 0

        def __init__(self, timeout=60.0):
            self.timeout = timeout
            self._responses = [
                _Resp(429, text="rate limit"),
                _Resp(200, payload={"choices": [{"message": {"content": '{"action":"BUY","confidence":81}'}}]}),
            ]

        async def __aenter__(self):
            _FakeAsyncClient.enter_count += 1
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, _url, headers=None, json=None):
            del headers, json
            _FakeAsyncClient.post_count += 1
            return self._responses.pop(0)

    async def _no_sleep(_seconds):
        return None

    monkeypatch.setattr("engine.vcp_ai_analyzer.httpx.AsyncClient", _FakeAsyncClient)
    monkeypatch.setattr("engine.vcp_ai_analyzer.asyncio.sleep", _no_sleep)
    monkeypatch.setattr("engine.vcp_ai_analyzer.random.randint", lambda _a, _b: 0)

    result = asyncio.run(analyzer._analyze_with_perplexity("삼성전자", {"ticker": "005930"}))

    assert result is not None
    assert result["action"] == "BUY"
    assert _FakeAsyncClient.enter_count == 1
    assert _FakeAsyncClient.post_count == 2


def test_analyze_with_perplexity_disables_provider_on_auth_error(monkeypatch):
    analyzer = object.__new__(VCPMultiAIAnalyzer)
    analyzer.perplexity_disabled = False
    analyzer._build_vcp_prompt = lambda *_args, **_kwargs: "prompt"

    monkeypatch.setenv("PERPLEXITY_API_KEY", "dummy-key")

    class _Resp:
        status_code = 401
        text = "unauthorized"

        @staticmethod
        def json():
            return {}

    class _FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            del args, kwargs

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, _url, headers=None, json=None):
            del headers, json
            return _Resp()

    monkeypatch.setattr("engine.vcp_ai_analyzer.httpx.AsyncClient", _FakeAsyncClient)

    result = asyncio.run(analyzer._analyze_with_perplexity("삼성전자", {"ticker": "005930"}))

    assert result is None
    assert analyzer.perplexity_disabled is True


def test_analyze_with_perplexity_falls_back_to_zai_after_repeated_429(monkeypatch):
    analyzer = object.__new__(VCPMultiAIAnalyzer)
    analyzer.perplexity_disabled = False
    analyzer.perplexity_quota_exhausted = False
    analyzer.zai_client = object()
    analyzer._build_vcp_prompt = lambda *_args, **_kwargs: "prompt"

    async def _zai(_name, _data, prompt=None):
        assert prompt == "prompt"
        return {"action": "SELL", "confidence": 55}

    analyzer._analyze_with_zai = _zai

    monkeypatch.setenv("PERPLEXITY_API_KEY", "dummy-key")

    class _Resp:
        status_code = 429
        text = "rate limit"

        @staticmethod
        def json():
            return {}

    class _FakeAsyncClient:
        post_count = 0

        def __init__(self, *args, **kwargs):
            del args, kwargs

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, _url, headers=None, json=None):
            del headers, json
            _FakeAsyncClient.post_count += 1
            return _Resp()

    async def _no_sleep(_seconds):
        return None

    monkeypatch.setattr("engine.vcp_ai_analyzer.httpx.AsyncClient", _FakeAsyncClient)
    monkeypatch.setattr("engine.vcp_ai_analyzer.asyncio.sleep", _no_sleep)
    monkeypatch.setattr("engine.vcp_ai_analyzer.random.randint", lambda _a, _b: 0)

    result = asyncio.run(analyzer._analyze_with_perplexity("삼성전자", {"ticker": "005930"}))

    assert result is not None
    assert result["action"] == "SELL"
    assert analyzer.perplexity_quota_exhausted is True
    assert _FakeAsyncClient.post_count == 4


def test_analyze_with_perplexity_uses_cached_quota_fallback_without_http(monkeypatch):
    analyzer = object.__new__(VCPMultiAIAnalyzer)
    analyzer.perplexity_disabled = False
    analyzer.perplexity_quota_exhausted = True
    analyzer.zai_client = object()
    analyzer._build_vcp_prompt = lambda *_args, **_kwargs: "prompt"
    calls = {"zai": 0}

    async def _zai(_name, _data, prompt=None):
        calls["zai"] += 1
        assert prompt == "prompt"
        return {"action": "BUY", "confidence": 77}

    analyzer._analyze_with_zai = _zai
    monkeypatch.setenv("PERPLEXITY_API_KEY", "dummy-key")

    class _ShouldNotCallAsyncClient:
        def __init__(self, *args, **kwargs):
            raise AssertionError("httpx.AsyncClient should not be used when quota cache is active")

    monkeypatch.setattr("engine.vcp_ai_analyzer.httpx.AsyncClient", _ShouldNotCallAsyncClient)

    result = asyncio.run(analyzer._analyze_with_perplexity("삼성전자", {"ticker": "005930"}))

    assert result is not None
    assert result["action"] == "BUY"
    assert calls["zai"] == 1


def test_analyze_stock_builds_prompt_once_and_shares_to_providers(monkeypatch):
    analyzer = object.__new__(VCPMultiAIAnalyzer)
    analyzer.providers = ["gemini", "gpt"]
    analyzer.perplexity_disabled = True

    calls = {"prompt": 0, "gemini": 0, "gpt": 0}

    def _build_prompt(_name, _data):
        calls["prompt"] += 1
        return "SHARED_PROMPT"

    async def _gemini(_name, _data, prompt=None):
        calls["gemini"] += 1
        assert prompt == "SHARED_PROMPT"
        return {"action": "BUY", "confidence": 70}

    async def _gpt(_name, _data, prompt=None):
        calls["gpt"] += 1
        assert prompt == "SHARED_PROMPT"
        return {"action": "HOLD", "confidence": 60}

    analyzer._build_vcp_prompt = _build_prompt
    analyzer._analyze_with_gemini = _gemini
    analyzer._analyze_with_gpt = _gpt
    analyzer._analyze_with_perplexity = lambda *_a, **_k: None

    monkeypatch.setenv("VCP_SECOND_PROVIDER", "gpt")
    result = asyncio.run(analyzer.analyze_stock("삼성전자", {"ticker": "005930"}))

    assert calls == {"prompt": 1, "gemini": 1, "gpt": 1}
    assert result["gemini_recommendation"]["action"] == "BUY"
    assert result["gpt_recommendation"]["action"] == "HOLD"
