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
    assert analyzer.perplexity_blocked_reason == "auth-401"
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
    assert analyzer.perplexity_blocked_reason == "auth-or-quota-401"
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
    assert analyzer.perplexity_blocked_reason == "auth-401"
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
                                content='{"action":"BUY","confidence":88,"reason":"VCP 점수와 수급 개선 흐름이 동시에 확인되어 단기 추세 상방 가능성이 높습니다. 다만 전고점 저항 부근에서 거래량이 둔화되면 변동성 확대가 나올 수 있어 분할 진입이 필요합니다."}'
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


def test_analyze_with_zai_switches_model_when_response_quality_is_low(monkeypatch):
    calls: list[str] = []

    def _create(**kwargs):
        model = str(kwargs.get("model"))
        calls.append(model)
        if model == "primary-zai-model":
            return SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(
                            content=(
                                '{"action":"BUY","confidence":81,"reason":"'
                                "Brief explanation in Korean highlighting the VCP pattern and positive institutional/foreign buying"
                                '"}'
                            )
                        )
                    )
                ]
            )
        if model == "glm-4.5-Flash":
            return SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(
                            content='{"action":"BUY","confidence":79,"reason":"VCP 점수와 수급 개선 신호를 근거로 단기 매수 우위가 유지됩니다. 다만 추세 확인 전까지는 거래량 동반 여부를 점검하면서 단계적으로 비중을 확대하는 접근이 바람직합니다."}'
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

    monkeypatch.setenv("ZAI_MODEL", "primary-zai-model")
    monkeypatch.setattr("engine.vcp_ai_analyzer.asyncio.to_thread", _fake_to_thread)

    result = asyncio.run(analyzer._analyze_with_zai("LG화학", {"ticker": "051910"}))

    assert result is not None
    assert result["action"] == "BUY"
    assert result["confidence"] == 79
    assert calls.count("primary-zai-model") >= 1
    assert "glm-4.5-Flash" in calls
    assert any("가" <= ch <= "힣" for ch in result["reason"])


def test_analyze_with_zai_low_quality_model_is_retried_for_next_requests(monkeypatch):
    calls: list[str] = []

    def _create(**kwargs):
        model = str(kwargs.get("model"))
        calls.append(model)
        if model == "primary-zai-model":
            return SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(
                            content=(
                                '{"action":"BUY","confidence":81,"reason":"'
                                "Brief explanation in Korean highlighting the VCP pattern and positive institutional/foreign buying"
                                '"}'
                            )
                        )
                    )
                ]
            )
        if model == "glm-4.5-Flash":
            return SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(
                            content='{"action":"BUY","confidence":77,"reason":"수급 유입과 거래량 수축이 동시에 확인되어 매수 우위 시나리오가 유효합니다. 다만 장중 변동성 확대 시 손절 기준을 명확히 두고 분할 매수로 대응하는 전략이 필요합니다."}'
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

    monkeypatch.setenv("ZAI_MODEL", "primary-zai-model")
    monkeypatch.setattr("engine.vcp_ai_analyzer.asyncio.to_thread", _fake_to_thread)

    first = asyncio.run(analyzer._analyze_with_zai("LG화학", {"ticker": "051910"}))
    first_primary_calls = calls.count("primary-zai-model")
    second = asyncio.run(analyzer._analyze_with_zai("LG이노텍", {"ticker": "011070"}))
    total_primary_calls = calls.count("primary-zai-model")

    assert first is not None and second is not None
    # 모델 전환 전 동일 모델을 최소 3회 증분 재시도하고,
    # 다음 종목에서도 primary 모델을 다시 시도한다.
    assert first_primary_calls >= 3
    assert total_primary_calls > first_primary_calls
    assert calls.count("glm-4.5-Flash") >= 2


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
                        content='{"action":"HOLD","confidence":63,"reason":"VCP 패턴은 유지되지만 수급 강도가 혼조라 추세 확신이 부족합니다. 단기 방향성이 확인될 때까지 관망하며 거래량 회복 여부를 추가 확인하는 전략이 적절합니다."}'
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
                                reasoning_content='{"action":"BUY","confidence":71,"reason":"외국인·기관 수급이 개선되고 변동성 수축이 유지되어 단기 상방 가능성이 높습니다. 다만 전고점 부근에서는 차익 매물 출회 가능성이 있어 분할 진입과 리스크 관리가 필요합니다."}',
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
                            content='{"action":"HOLD","confidence":68,"reason":"VCP 신호는 유효하지만 수급 모멘텀이 강하지 않아 즉시 추격 매수는 부담이 있습니다. 추세 재확인 전까지는 관망하고 거래량 회복 여부를 확인하는 것이 유리합니다."}'
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
    assert "현재 판단은 BUY" in result["reason"]
    from engine.config import app_config
    from engine.vcp_ai_analyzer import ZAI_FALLBACK_MODEL_CHAIN

    model_chain: list[str] = []
    seen_models: set[str] = set()
    for candidate in [str(app_config.ZAI_MODEL or "").strip(), *ZAI_FALLBACK_MODEL_CHAIN]:
        model_name = str(candidate or "").strip()
        if not model_name:
            continue
        key = model_name.lower()
        if key in seen_models:
            continue
        seen_models.add(key)
        model_chain.append(model_name)

    # 각 모델당 최대 3회 시도, 시도마다 본응답+JSON보정 2회 호출
    assert calls["count"] == len(model_chain) * 3 * 2


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
                                content='{"action":"BUY","confidence":73,"reason":"수급 유입과 변동성 수축이 동시에 나타나 단기 매수 우위 시나리오가 성립됩니다. 다만 저항 구간 돌파 실패 가능성을 고려해 분할 진입과 손절 기준을 병행해야 합니다."}'
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
    assert calls.count("primary-zai-model") == 3
    assert "glm-4.5-Flash" in calls


def test_analyze_with_zai_429_does_not_block_model_for_next_requests(monkeypatch):
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
                        content='{"action":"BUY","confidence":72,"reason":"외국인·기관 수급이 개선되고 VCP 패턴도 유지되어 단기 상방 가능성이 높습니다. 다만 추세 확인 전에는 거래량 변화와 지지선 이탈 여부를 함께 점검해야 합니다."}'
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
    first_primary_calls = calls.count("primary-zai-model")
    second = asyncio.run(analyzer._analyze_with_zai("고려아연", {"ticker": "010130"}))
    total_primary_calls = calls.count("primary-zai-model")

    assert first is not None and second is not None
    # 429가 발생해도 동일 모델 최소 3회 재시도 후 다음 모델로 전환하며,
    # 다음 종목에서도 primary 모델을 다시 시도한다.
    assert first_primary_calls == 3
    assert total_primary_calls > first_primary_calls


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
                                content='{"action":"HOLD","confidence":66,"reason":"수급 혼조와 추세 모멘텀 둔화가 함께 나타나 단기 방향성 확신이 부족합니다. 돌파 거래량이 확인될 때까지 관망하며 변동성 확대 구간을 피하는 전략이 적절합니다."}'
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
    assert calls.count("primary-zai-model") == 3
    assert calls.count("glm-4.5-Flash") == 3
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
