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
    assert parsed["action"] == "BUY"
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


def test_analyze_with_gemini_429_blocks_model_for_session(monkeypatch):
    calls: list[str] = []

    def _generate_content(*, model, contents):
        del contents
        calls.append(model)
        if model == "gemini-2.0-flash-lite":
            raise RuntimeError("429 resource_exhausted")
        return SimpleNamespace(text='{"action":"BUY","confidence":74,"reason":"ok"}')

    analyzer = object.__new__(VCPMultiAIAnalyzer)
    analyzer.gemini_client = SimpleNamespace(
        models=SimpleNamespace(generate_content=_generate_content)
    )
    analyzer._build_vcp_prompt = lambda *_args, **_kwargs: "prompt"

    async def _fake_to_thread(func, *args, **kwargs):
        return func(*args, **kwargs)

    async def _no_sleep(_seconds):
        return None

    monkeypatch.setattr("engine.vcp_ai_analyzer.asyncio.to_thread", _fake_to_thread)
    monkeypatch.setattr("engine.vcp_ai_analyzer.asyncio.sleep", _no_sleep)

    first = asyncio.run(analyzer._analyze_with_gemini("LG화학", {"ticker": "051910"}))
    second = asyncio.run(analyzer._analyze_with_gemini("고려아연", {"ticker": "010130"}))

    assert first is not None and second is not None
    assert first["action"] == "BUY"
    assert second["action"] == "BUY"
    # 429가 발생한 모델은 세션에서 제외되어 두 번째 종목에서는 재시도하지 않는다.
    assert calls.count("gemini-2.0-flash-lite") == 1


def test_analyze_with_perplexity_429_switches_to_fallback_without_retry(monkeypatch):
    analyzer = object.__new__(VCPMultiAIAnalyzer)
    analyzer.perplexity_disabled = False
    analyzer.perplexity_quota_exhausted = False
    analyzer.perplexity_blocked_reason = None
    analyzer.providers = ["gemini", "perplexity", "zai"]
    analyzer.perplexity_fallback_providers = ["zai"]
    analyzer.zai_client = object()
    analyzer._build_vcp_prompt = lambda *_args, **_kwargs: "prompt"

    monkeypatch.setenv("PERPLEXITY_API_KEY", "dummy-key")
    monkeypatch.setenv("VCP_PERPLEXITY_MODEL", "sonar-pro")

    async def _zai(_name, _data, prompt=None):
        assert prompt == "prompt"
        return {"action": "BUY", "confidence": 81}

    analyzer._analyze_with_zai = _zai

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

    monkeypatch.setattr("engine.vcp_ai_analyzer.httpx.AsyncClient", _FakeAsyncClient)

    result = asyncio.run(analyzer._analyze_with_perplexity("삼성전자", {"ticker": "005930"}))

    assert result is not None
    assert result["action"] == "BUY"
    assert analyzer.perplexity_quota_exhausted is True
    assert analyzer.perplexity_blocked_reason == "429"
    assert _FakeAsyncClient.enter_count == 1
    assert _FakeAsyncClient.post_count == 1


def test_analyze_with_perplexity_503_blocks_session_and_uses_cached_fallback(monkeypatch):
    analyzer = object.__new__(VCPMultiAIAnalyzer)
    analyzer.perplexity_disabled = False
    analyzer.perplexity_quota_exhausted = False
    analyzer.perplexity_blocked_reason = None
    analyzer.providers = ["gemini", "perplexity", "zai"]
    analyzer.perplexity_fallback_providers = ["zai"]
    analyzer.zai_client = object()
    analyzer._build_vcp_prompt = lambda *_args, **_kwargs: "prompt"
    calls = {"http": 0, "zai": 0}

    async def _zai(_name, _data, prompt=None):
        calls["zai"] += 1
        assert prompt == "prompt"
        return {"action": "HOLD", "confidence": 65}

    analyzer._analyze_with_zai = _zai
    monkeypatch.setenv("PERPLEXITY_API_KEY", "dummy-key")

    class _Resp:
        status_code = 503
        text = "service unavailable"

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
            calls["http"] += 1
            return _Resp()

    monkeypatch.setattr("engine.vcp_ai_analyzer.httpx.AsyncClient", _FakeAsyncClient)

    first = asyncio.run(analyzer._analyze_with_perplexity("삼성전자", {"ticker": "005930"}))
    second = asyncio.run(analyzer._analyze_with_perplexity("LG화학", {"ticker": "051910"}))

    assert first is not None and second is not None
    assert analyzer.perplexity_quota_exhausted is True
    assert analyzer.perplexity_blocked_reason == "503"
    assert calls["http"] == 1
    assert calls["zai"] == 2


def test_analyze_with_perplexity_auth_401_marks_quota_cache_and_fallbacks(monkeypatch):
    analyzer = object.__new__(VCPMultiAIAnalyzer)
    analyzer.perplexity_disabled = False
    analyzer.perplexity_quota_exhausted = False
    analyzer.providers = ["gemini", "perplexity", "zai"]
    analyzer.perplexity_fallback_providers = ["zai"]
    analyzer._build_vcp_prompt = lambda *_args, **_kwargs: "prompt"
    analyzer.zai_client = object()

    monkeypatch.setenv("PERPLEXITY_API_KEY", "dummy-key")

    async def _zai(_name, _data, prompt=None):
        assert prompt == "prompt"
        return {"action": "HOLD", "confidence": 61}

    analyzer._analyze_with_zai = _zai

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

    assert result is not None
    assert result["action"] == "HOLD"
    assert analyzer.perplexity_quota_exhausted is True
    assert analyzer.perplexity_disabled is False


def test_analyze_with_perplexity_ambiguous_401_marks_quota_and_fallbacks(monkeypatch):
    analyzer = object.__new__(VCPMultiAIAnalyzer)
    analyzer.perplexity_disabled = False
    analyzer.perplexity_quota_exhausted = False
    analyzer.providers = ["gemini", "perplexity", "zai"]
    analyzer.perplexity_fallback_providers = ["zai"]
    analyzer.zai_client = object()
    analyzer.gpt_client = None
    analyzer._build_vcp_prompt = lambda *_args, **_kwargs: "prompt"

    async def _zai(_name, _data, prompt=None):
        assert prompt == "prompt"
        return {"action": "BUY", "confidence": 67}

    analyzer._analyze_with_zai = _zai

    monkeypatch.setenv("PERPLEXITY_API_KEY", "dummy-key")

    class _Resp:
        status_code = 401
        text = "<html><center><h1>401 Authorization Required</h1></center><hr><center>openresty</center>"

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

    assert result is not None
    assert result["action"] == "BUY"
    assert analyzer.perplexity_quota_exhausted is True
    assert analyzer.perplexity_disabled is False


def test_analyze_with_perplexity_after_first_401_uses_session_cached_fallback(monkeypatch):
    analyzer = object.__new__(VCPMultiAIAnalyzer)
    analyzer.perplexity_disabled = False
    analyzer.perplexity_quota_exhausted = False
    analyzer.providers = ["gemini", "perplexity", "zai"]
    analyzer.perplexity_fallback_providers = ["zai"]
    analyzer.zai_client = object()
    analyzer._build_vcp_prompt = lambda *_args, **_kwargs: "prompt"
    calls = {"http": 0, "zai": 0}

    async def _zai(_name, _data, prompt=None):
        calls["zai"] += 1
        assert prompt == "prompt"
        return {"action": "BUY", "confidence": 67}

    analyzer._analyze_with_zai = _zai
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
            calls["http"] += 1
            return _Resp()

    monkeypatch.setattr("engine.vcp_ai_analyzer.httpx.AsyncClient", _FakeAsyncClient)

    first = asyncio.run(analyzer._analyze_with_perplexity("삼성전자", {"ticker": "005930"}))
    second = asyncio.run(analyzer._analyze_with_perplexity("LG화학", {"ticker": "051910"}))

    assert first is not None and second is not None
    assert analyzer.perplexity_quota_exhausted is True
    assert calls["http"] == 1
    assert calls["zai"] == 2


def test_analyze_with_perplexity_falls_back_to_zai_after_repeated_429(monkeypatch):
    analyzer = object.__new__(VCPMultiAIAnalyzer)
    analyzer.perplexity_disabled = False
    analyzer.perplexity_quota_exhausted = False
    analyzer.perplexity_blocked_reason = None
    analyzer.providers = ["gemini", "perplexity", "zai"]
    analyzer.perplexity_fallback_providers = ["zai"]
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

    monkeypatch.setattr("engine.vcp_ai_analyzer.httpx.AsyncClient", _FakeAsyncClient)

    result = asyncio.run(analyzer._analyze_with_perplexity("삼성전자", {"ticker": "005930"}))

    assert result is not None
    assert result["action"] == "SELL"
    assert analyzer.perplexity_quota_exhausted is True
    assert analyzer.perplexity_blocked_reason == "429"
    assert _FakeAsyncClient.post_count == 1


def test_analyze_with_perplexity_fallback_uses_gpt_when_configured(monkeypatch):
    analyzer = object.__new__(VCPMultiAIAnalyzer)
    analyzer.perplexity_disabled = False
    analyzer.perplexity_quota_exhausted = True
    analyzer.zai_client = None
    analyzer.gpt_client = object()
    analyzer.providers = ["gemini", "gpt"]
    analyzer.perplexity_fallback_providers = ["gpt"]
    analyzer._build_vcp_prompt = lambda *_args, **_kwargs: "prompt"
    calls = {"gpt": 0}

    async def _gpt(_name, _data, prompt=None):
        calls["gpt"] += 1
        assert prompt == "prompt"
        return {"action": "SELL", "confidence": 55}

    analyzer._analyze_with_gpt = _gpt
    monkeypatch.setenv("PERPLEXITY_API_KEY", "dummy-key")

    result = asyncio.run(analyzer._analyze_with_perplexity("삼성전자", {"ticker": "005930"}))

    assert result is not None
    assert result["action"] == "SELL"
    assert calls["gpt"] == 1


def test_analyze_with_perplexity_uses_cached_quota_fallback_without_http(monkeypatch):
    analyzer = object.__new__(VCPMultiAIAnalyzer)
    analyzer.perplexity_disabled = False
    analyzer.perplexity_quota_exhausted = True
    analyzer.providers = ["gemini", "perplexity", "zai"]
    analyzer.perplexity_fallback_providers = ["zai"]
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


def test_analyze_with_perplexity_does_not_fallback_when_provider_not_in_vcp_ai_providers(monkeypatch):
    analyzer = object.__new__(VCPMultiAIAnalyzer)
    analyzer.perplexity_disabled = False
    analyzer.perplexity_quota_exhausted = True
    analyzer.providers = ["gemini", "perplexity"]
    analyzer.perplexity_fallback_providers = []
    analyzer.zai_client = object()
    analyzer.gpt_client = object()
    analyzer._build_vcp_prompt = lambda *_args, **_kwargs: "prompt"
    calls = {"zai": 0, "gpt": 0}

    async def _zai(_name, _data, prompt=None):
        calls["zai"] += 1
        return {"action": "BUY", "confidence": 70}

    async def _gpt(_name, _data, prompt=None):
        calls["gpt"] += 1
        return {"action": "BUY", "confidence": 70}

    analyzer._analyze_with_zai = _zai
    analyzer._analyze_with_gpt = _gpt
    monkeypatch.setenv("PERPLEXITY_API_KEY", "dummy-key")

    result = asyncio.run(analyzer._analyze_with_perplexity("삼성전자", {"ticker": "005930"}))

    assert result is None
    assert calls == {"zai": 0, "gpt": 0}


def test_analyze_with_zai_uses_openai_client(monkeypatch):
    analyzer = object.__new__(VCPMultiAIAnalyzer)
    analyzer.zai_client = SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(
                create=lambda **_kwargs: SimpleNamespace(
                    choices=[
                        SimpleNamespace(
                            message=SimpleNamespace(
                                content='{"action":"BUY","confidence":88,"reason":"ok"}'
                            )
                        )
                    ]
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
    result = asyncio.run(analyzer._analyze_with_zai("삼성전자", {"ticker": "005930"}))

    assert result is not None
    assert result["action"] == "BUY"
    assert called["to_thread"] == 1


def test_analyze_with_zai_retries_when_first_response_not_json(monkeypatch):
    calls = {"count": 0}

    def _create(**_kwargs):
        calls["count"] += 1
        if calls["count"] == 1:
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content="..."))]
            )
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content='{"action":"HOLD","confidence":63,"reason":"재시도 성공"}'
                    )
                )
            ]
        )

    analyzer = object.__new__(VCPMultiAIAnalyzer)
    analyzer.zai_client = SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(
                create=_create
            )
        )
    )
    analyzer._build_vcp_prompt = lambda *_args, **_kwargs: "prompt"

    async def _fake_to_thread(func, *args, **kwargs):
        return func(*args, **kwargs)

    monkeypatch.setattr("engine.vcp_ai_analyzer.asyncio.to_thread", _fake_to_thread)

    result = asyncio.run(analyzer._analyze_with_zai("LG화학", {"ticker": "051910"}))

    assert result is not None
    assert result["action"] == "HOLD"
    assert calls["count"] == 2


def test_analyze_with_zai_uses_reasoning_content_when_content_is_blank(monkeypatch):
    analyzer = object.__new__(VCPMultiAIAnalyzer)
    analyzer.zai_client = SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(
                create=lambda **_kwargs: SimpleNamespace(
                    choices=[
                        SimpleNamespace(
                            message=SimpleNamespace(
                                content="   ",
                                reasoning_content='{"action":"BUY","confidence":71,"reason":"fallback"}',
                            )
                        )
                    ]
                )
            )
        )
    )
    analyzer._build_vcp_prompt = lambda *_args, **_kwargs: "prompt"

    async def _fake_to_thread(func, *args, **kwargs):
        return func(*args, **kwargs)

    monkeypatch.setattr("engine.vcp_ai_analyzer.asyncio.to_thread", _fake_to_thread)

    result = asyncio.run(analyzer._analyze_with_zai("현대차", {"ticker": "005380"}))

    assert result is not None
    assert result["action"] == "BUY"
    assert result["confidence"] == 71


def test_analyze_with_zai_repairs_non_json_response_with_followup_call(monkeypatch):
    calls = {"count": 0}

    def _create(**kwargs):
        calls["count"] += 1
        messages = kwargs.get("messages", [])
        first_system = messages[0]["content"] if messages else ""
        if "convert stock analysis text into strict json only" in str(first_system).lower():
            return SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(
                            content='{"action":"HOLD","confidence":68,"reason":"보정 성공"}'
                        )
                    )
                ]
            )
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content=(
                            "Let me analyze this stock first.\n"
                            "VCP score is high and supply is stable.\n"
                            "I will provide detailed reasoning."
                        )
                    )
                )
            ]
        )

    analyzer = object.__new__(VCPMultiAIAnalyzer)
    analyzer.zai_client = SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(
                create=_create
            )
        )
    )
    analyzer._build_vcp_prompt = lambda *_args, **_kwargs: "prompt"

    async def _fake_to_thread(func, *args, **kwargs):
        return func(*args, **kwargs)

    monkeypatch.setattr("engine.vcp_ai_analyzer.asyncio.to_thread", _fake_to_thread)

    result = asyncio.run(analyzer._analyze_with_zai("LG화학", {"ticker": "051910"}))

    assert result is not None
    assert result["action"] == "HOLD"
    assert result["confidence"] == 68
    assert calls["count"] == 2


def test_analyze_with_zai_uses_rule_based_fallback_when_all_parsing_fails(monkeypatch):
    calls = {"count": 0}

    def _create(**_kwargs):
        calls["count"] += 1
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content=(
                            "Let me analyze the stock and provide a detailed narrative "
                            "without strict JSON format."
                        )
                    )
                )
            ]
        )

    analyzer = object.__new__(VCPMultiAIAnalyzer)
    analyzer.zai_client = SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(
                create=_create
            )
        )
    )
    analyzer._build_vcp_prompt = lambda *_args, **_kwargs: "prompt"

    async def _fake_to_thread(func, *args, **kwargs):
        return func(*args, **kwargs)

    monkeypatch.setattr("engine.vcp_ai_analyzer.asyncio.to_thread", _fake_to_thread)

    stock_data = {
        "ticker": "010130",
        "score": 82,
        "contraction_ratio": 0.74,
        "foreign_5d": 1200,
        "inst_5d": 500,
        "foreign_1d": 100,
        "inst_1d": 50,
    }
    result = asyncio.run(analyzer._analyze_with_zai("고려아연", stock_data))

    assert result is not None
    assert result["action"] == "BUY"
    assert result["confidence"] >= 60
    assert "규칙 기반 보정 결과" in result["reason"]
    assert calls["count"] == 4


def test_analyze_with_zai_uses_rule_based_fallback_when_exception_occurs(monkeypatch):
    def _create(**_kwargs):
        raise RuntimeError("z.ai temporary timeout")

    analyzer = object.__new__(VCPMultiAIAnalyzer)
    analyzer.zai_client = SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(
                create=_create
            )
        )
    )
    analyzer._build_vcp_prompt = lambda *_args, **_kwargs: "prompt"

    async def _fake_to_thread(func, *args, **kwargs):
        return func(*args, **kwargs)

    async def _no_sleep(_seconds):
        return None

    monkeypatch.setattr("engine.vcp_ai_analyzer.asyncio.to_thread", _fake_to_thread)
    monkeypatch.setattr("engine.vcp_ai_analyzer.asyncio.sleep", _no_sleep)

    stock_data = {
        "ticker": "051910",
        "score": 80,
        "contraction_ratio": 0.75,
        "foreign_5d": 1000,
        "inst_5d": 500,
        "foreign_1d": 100,
        "inst_1d": 80,
    }
    result = asyncio.run(analyzer._analyze_with_zai("LG화학", stock_data))

    assert result is not None
    assert result["action"] in {"BUY", "HOLD", "SELL"}
    assert isinstance(result["confidence"], int)


def test_analyze_with_zai_switches_model_on_429_failure_response(monkeypatch):
    calls: list[str] = []

    def _create(**kwargs):
        model = str(kwargs.get("model"))
        calls.append(model)
        if model == "primary-zai-model":
            raise RuntimeError("Request failed with status code 429")
        if model == "glm-4.5-Flash":
            return SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(
                            content='{"action":"BUY","confidence":73,"reason":"fallback model success"}'
                        )
                    )
                ]
            )
        raise AssertionError(f"Unexpected model call: {model}")

    analyzer = object.__new__(VCPMultiAIAnalyzer)
    analyzer.zai_client = SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(
                create=_create
            )
        )
    )
    analyzer._build_vcp_prompt = lambda *_args, **_kwargs: "prompt"

    async def _fake_to_thread(func, *args, **kwargs):
        return func(*args, **kwargs)

    async def _no_sleep(_seconds):
        return None

    monkeypatch.setenv("ZAI_MODEL", "primary-zai-model")
    monkeypatch.setattr("engine.vcp_ai_analyzer.asyncio.to_thread", _fake_to_thread)
    monkeypatch.setattr("engine.vcp_ai_analyzer.asyncio.sleep", _no_sleep)

    result = asyncio.run(analyzer._analyze_with_zai("LG화학", {"ticker": "051910"}))

    assert result is not None
    assert result["action"] == "BUY"
    assert calls.count("primary-zai-model") == 1
    assert "glm-4.5-Flash" in calls


def test_analyze_with_zai_429_blocks_model_for_next_requests(monkeypatch):
    calls: list[str] = []

    def _create(**kwargs):
        model = str(kwargs.get("model"))
        calls.append(model)
        if model == "primary-zai-model":
            raise RuntimeError("status=429")
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content='{"action":"BUY","confidence":72,"reason":"ok"}'
                    )
                )
            ]
        )

    analyzer = object.__new__(VCPMultiAIAnalyzer)
    analyzer.zai_client = SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(
                create=_create
            )
        )
    )
    analyzer._build_vcp_prompt = lambda *_args, **_kwargs: "prompt"

    async def _fake_to_thread(func, *args, **kwargs):
        return func(*args, **kwargs)

    async def _no_sleep(_seconds):
        return None

    monkeypatch.setenv("ZAI_MODEL", "primary-zai-model")
    monkeypatch.setattr("engine.vcp_ai_analyzer.asyncio.to_thread", _fake_to_thread)
    monkeypatch.setattr("engine.vcp_ai_analyzer.asyncio.sleep", _no_sleep)

    first = asyncio.run(analyzer._analyze_with_zai("LG화학", {"ticker": "051910"}))
    second = asyncio.run(analyzer._analyze_with_zai("고려아연", {"ticker": "010130"}))

    assert first is not None and second is not None
    # 429 모델은 세션에서 제외되어 두 번째 호출에서는 더 이상 사용되지 않는다.
    assert calls.count("primary-zai-model") == 1


def test_analyze_with_zai_switches_through_fallback_model_chain(monkeypatch):
    calls: list[str] = []

    def _create(**kwargs):
        model = str(kwargs.get("model"))
        calls.append(model)
        if model == "primary-zai-model":
            raise RuntimeError("status=429 rate limited")
        if model == "glm-4.5-Flash":
            raise RuntimeError("Service Unavailable (503)")
        if model == "glm-4.6V-Flash":
            return SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(
                            content='{"action":"HOLD","confidence":66,"reason":"third model success"}'
                        )
                    )
                ]
            )
        raise AssertionError(f"Unexpected model call: {model}")

    analyzer = object.__new__(VCPMultiAIAnalyzer)
    analyzer.zai_client = SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(
                create=_create
            )
        )
    )
    analyzer._build_vcp_prompt = lambda *_args, **_kwargs: "prompt"

    async def _fake_to_thread(func, *args, **kwargs):
        return func(*args, **kwargs)

    async def _no_sleep(_seconds):
        return None

    monkeypatch.setenv("ZAI_MODEL", "primary-zai-model")
    monkeypatch.setattr("engine.vcp_ai_analyzer.asyncio.to_thread", _fake_to_thread)
    monkeypatch.setattr("engine.vcp_ai_analyzer.asyncio.sleep", _no_sleep)

    result = asyncio.run(analyzer._analyze_with_zai("고려아연", {"ticker": "010130"}))

    assert result is not None
    assert result["action"] == "HOLD"
    assert calls.count("primary-zai-model") == 1
    assert calls.count("glm-4.5-Flash") == 1
    assert "glm-4.6V-Flash" in calls


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
