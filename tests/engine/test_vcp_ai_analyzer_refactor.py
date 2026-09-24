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


def test_get_available_providers_lists_only_initialized_clients():
    analyzer = object.__new__(VCPMultiAIAnalyzer)
    analyzer.gemini_client = object()
    analyzer.gpt_client = None
    analyzer.zai_client = object()

    assert analyzer.get_available_providers() == ["gemini", "zai"]


def test_analyze_with_gpt_uses_to_thread(monkeypatch):
    analyzer = object.__new__(VCPMultiAIAnalyzer)
    quality_reason = (
        "VCP 점수와 외국인·기관 수급이 동시에 개선되어 단기 매수 우위 시나리오가 유효합니다. "
        "다만 전고점 저항 부근에서 거래량이 둔화될 가능성을 고려해 분할 매수와 손절 기준을 함께 운영하는 전략이 필요합니다."
    )
    payload = (
        '{"action":"BUY","confidence":80,"reason":"' + quality_reason + '"}'
    )
    analyzer.gpt_client = SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(
                create=lambda **_kwargs: SimpleNamespace(
                    choices=[SimpleNamespace(message=SimpleNamespace(content=payload))]
                )
            )
        ),
        responses=SimpleNamespace(
            create=lambda **_kwargs: SimpleNamespace(
                output_text=payload,
                output=[],
            )
        ),
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
    monkeypatch.setenv("VCP_GEMINI_MODEL", "gemini-3.1-flash-lite")
    calls: list[str] = []

    def _generate_content(*, model, contents):
        del contents
        calls.append(model)
        if model == "gemini-3.1-flash-lite":
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
    assert calls.count("gemini-3.1-flash-lite") == 1


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
        if model == "glm-4.6V-Flash":
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
    assert "glm-4.6V-Flash" in calls
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
        if model == "glm-4.6V-Flash":
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
    # 품질 미달 시 동일 모델 반복 없이 즉시 다음 모델로 전환하고,
    # 다음 종목에서도 primary 모델을 다시 시도한다.
    assert first_primary_calls == 1
    assert total_primary_calls > first_primary_calls
    assert calls.count("glm-4.6V-Flash") >= 2


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
    assert result["action"] == "HOLD"
    assert result["confidence"] == 55
    assert "현재 판단은 HOLD" in result["reason"]
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

    # 각 모델당 1회 시도 + JSON 보정 1회 호출
    assert calls["count"] == len(model_chain) * 2


def test_analyze_with_zai_fallback_keeps_unknown_one_day_flow_conservative(monkeypatch):
    def _create(**_kwargs):
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="JSON 형식이 아닌 응답"))]
        )

    analyzer = object.__new__(VCPMultiAIAnalyzer)
    analyzer.zai_client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=_create))
    )
    analyzer._build_vcp_prompt = lambda *_args, **_kwargs: "prompt"

    async def _fake_to_thread(func, *args, **kwargs):
        return func(*args, **kwargs)

    monkeypatch.setattr("engine.vcp_ai_analyzer.asyncio.to_thread", _fake_to_thread)

    result = asyncio.run(
        analyzer._analyze_with_zai(
            "고려아연",
            {
                "ticker": "010130",
                "score": 82,
                "contraction_ratio": 0.74,
                "foreign_5d": 1200,
                "inst_5d": 500,
            },
        )
    )

    assert result is not None
    assert result["action"] == "HOLD"
    assert result["confidence"] == 55
    assert "정보가 부족" in result["reason"]
    assert "1일 수급" not in result["reason"]


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
        if model == "glm-4.6V-Flash":
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
    assert calls.count("primary-zai-model") == 1
    assert "glm-4.6V-Flash" in calls


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
    # 429가 발생하면 동일 모델 반복 없이 다음 모델로 전환하며,
    # 다음 종목에서도 primary 모델을 다시 시도한다.
    assert first_primary_calls == 1
    assert total_primary_calls > first_primary_calls


def test_analyze_with_zai_switches_through_fallback_model_chain(monkeypatch):
    calls: list[str] = []

    def _create(**kwargs):
        model = str(kwargs.get("model"))
        calls.append(model)
        if model == "primary-zai-model":
            raise RuntimeError("status=429 rate limited")
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
    assert calls.count("primary-zai-model") == 1
    assert calls.count("glm-4.6V-Flash") == 1
    assert "glm-4.7" not in calls


def test_analyze_with_zai_disables_session_after_prompt_echo_responses(monkeypatch):
    calls: list[str] = []

    def _create(**kwargs):
        model = str(kwargs.get("model"))
        calls.append(model)
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content=(
                            "1.  **Analyze the Request:**\n"
                            "    *   **Role:** Financial data analyst.\n"
                            "    *   **Task:** Analyze the stock and return JSON.\n"
                            "    *   **Constraints:** Output only valid JSON.\n"
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

    monkeypatch.setenv("ZAI_MODEL", "primary-zai-model")
    monkeypatch.setattr("engine.vcp_ai_analyzer.asyncio.to_thread", _fake_to_thread)

    first = asyncio.run(
        analyzer._analyze_with_zai(
            "고영",
            {
                "ticker": "098460",
                "score": 77,
                "contraction_ratio": 0.74,
                "foreign_5d": 1000,
                "inst_5d": 500,
                "foreign_1d": 100,
                "inst_1d": 50,
            },
        )
    )
    first_call_count = len(calls)
    second = asyncio.run(
        analyzer._analyze_with_zai(
            "대덕전자",
            {
                "ticker": "353200",
                "score": 79,
                "contraction_ratio": 0.7,
                "foreign_5d": 900,
                "inst_5d": 400,
                "foreign_1d": 80,
                "inst_1d": 40,
            },
        )
    )

    assert first is not None and second is not None
    assert first["action"] in {"BUY", "HOLD", "SELL"}
    assert second["action"] in {"BUY", "HOLD", "SELL"}
    # 모델 체인 [primary, glm-4.6V-Flash]에 대해 prompt-echo 감지 시
    # 같은 모델로 2회 재시도하므로 모델당 3회 = 총 6회 호출 후 세션 비활성화.
    assert first_call_count == 6
    assert len(calls) == first_call_count


def _build_analyzer_without_clients(monkeypatch, *, providers, second_provider):
    """클라이언트 초기화를 막고 실제 생성자를 태워 provider 배선만 본다."""
    import engine.vcp_ai_analyzer as analyzer_module

    monkeypatch.setenv("VCP_AI_PROVIDERS", providers)
    monkeypatch.setenv("VCP_SECOND_PROVIDER", second_provider)

    monkeypatch.setattr(analyzer_module, "init_gemini_client", lambda *a, **k: None)
    monkeypatch.setattr(analyzer_module, "init_gpt_client", lambda *a, **k: None)
    monkeypatch.setattr(analyzer_module, "init_zai_client", lambda *a, **k: None)

    return analyzer_module.VCPMultiAIAnalyzer()


def test_init_confirms_second_provider_with_fallback_applied(monkeypatch):
    """생성자가 perplexity 설정을 gpt 로 확정한다 [VCP-046].

    resolve_effective_second_provider 자체는 단위 검사로 덮여 있지만, 생성자가 그 결과를
    self.second_provider 로 잇는지는 이 검사만 본다. 이 배선이 `[VCP-015]` 가 고친 결함의
    자리다. 설정값을 그대로 self.second_provider 에 넣던 예전 방식으로 되돌리면 실패한다.
    """
    analyzer = _build_analyzer_without_clients(
        monkeypatch,
        providers="gemini,gpt",
        second_provider="perplexity",
    )

    assert analyzer.second_provider == "gpt"


def test_init_keeps_second_ai_when_env_still_lists_perplexity(monkeypatch):
    """[VCP-046] 옛 운영 구성(gemini,perplexity + perplexity)도 .env 를 고치지 않고 GPT 로 돈다."""
    analyzer = _build_analyzer_without_clients(
        monkeypatch,
        providers="gemini,perplexity",
        second_provider="perplexity",
    )

    assert analyzer.providers == ["gemini", "gpt"]
    assert analyzer.second_provider == "gpt"


def test_init_leaves_second_provider_unset_when_nothing_can_run(monkeypatch):
    """허용 목록에 GPT 가 없으면 두 번째 자리를 비운 채로 둔다."""
    analyzer = _build_analyzer_without_clients(
        monkeypatch,
        providers="gemini",
        second_provider="gpt",
    )

    assert analyzer.second_provider is None


def test_analyze_stock_builds_prompt_once_and_shares_to_providers():
    analyzer = object.__new__(VCPMultiAIAnalyzer)
    analyzer.providers = ["gemini", "gpt"]
    # __init__ 을 거치지 않으므로 resolve_effective_second_provider 의 결과를 직접 심는다.
    analyzer.second_provider = "gpt"

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

    result = asyncio.run(analyzer.analyze_stock("삼성전자", {"ticker": "005930"}))

    assert calls == {"prompt": 1, "gemini": 1, "gpt": 1}
    assert result["gemini_recommendation"]["action"] == "BUY"
    assert result["gpt_recommendation"]["action"] == "HOLD"


def test_status_extraction_preserves_provider_specific_code_handling():
    analyzer = object.__new__(VCPMultiAIAnalyzer)
    error = RuntimeError("provider failure")
    error.code = 429
    assert analyzer._extract_status_code(error) == 429
    assert analyzer._extract_status_code(error, include_code=False) is None
    error.response = SimpleNamespace(status_code=503)
    assert analyzer._extract_status_code(error, include_code=False) == 503
    assert analyzer._extract_status_code(RuntimeError("HTTP 429"), include_code=False) == 429


def test_zai_echo_recovers_on_same_model_without_fallback(monkeypatch):
    import json

    calls = []
    recovered = {"action": "BUY", "confidence": 88, "reason": "VCP 점수와 수급 개선 흐름이 동시에 확인되어 단기 추세 상방 가능성이 높습니다. 다만 전고점 저항 부근에서 거래량이 둔화되면 변동성 확대가 나올 수 있어 분할 진입이 필요합니다."}

    def create(**kwargs):
        calls.append((kwargs["model"], kwargs["temperature"]))
        content = (
            "1. **Analyze the Request:**\n * **Role:** Financial data analyst.\n * **Task:** Analyze the stock.\n * **Constraints:** Output only valid JSON."
            if len(calls) == 1 else json.dumps(recovered, ensure_ascii=False)
        )
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])

    analyzer = object.__new__(VCPMultiAIAnalyzer)
    analyzer.zai_client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    monkeypatch.setenv("ZAI_MODEL", "primary-zai-model")
    result = asyncio.run(analyzer._analyze_with_zai("합성 검증", {"ticker": "005930"}, "synthetic prompt"))
    assert result == recovered
    assert calls == [("primary-zai-model", 0.0), ("primary-zai-model", 0.3)]
    assert not getattr(analyzer, "zai_disabled_reason", "")


def _gemini_only_analyzer_with_clock(monkeypatch, generate_content):
    clock = {"now": 0.0}
    # 전역 time.monotonic 을 바꾸므로 asyncio 의 sleep·to_thread 도 가짜로 둔다(실제 타이머가 멈춘다)
    monkeypatch.setattr("engine.vcp_ai_analyzer.time.monotonic", lambda: clock["now"])

    async def _fake_to_thread(func, *args, **kwargs):
        return func(*args, **kwargs)

    async def _no_sleep(_seconds):
        return None

    async def _gemini_only_orchestrate(*, stock_name, stock_data, analyze_with_gemini_fn, **_kwargs):
        return {"gemini_recommendation": await analyze_with_gemini_fn(stock_name, stock_data)}

    monkeypatch.setattr("engine.vcp_ai_analyzer.asyncio.to_thread", _fake_to_thread)
    monkeypatch.setattr("engine.vcp_ai_analyzer.asyncio.sleep", _no_sleep)
    monkeypatch.setattr("engine.vcp_ai_analyzer.orchestrate_stock_analysis_impl", _gemini_only_orchestrate)
    analyzer = object.__new__(VCPMultiAIAnalyzer)
    analyzer.providers, analyzer.second_provider = ["gemini"], None
    analyzer.gemini_client = SimpleNamespace(models=SimpleNamespace(generate_content=generate_content))
    analyzer._build_vcp_prompt = lambda *_args, **_kwargs: "prompt"
    return analyzer, clock


def _flaky_gemini():
    state = {"fail": True, "calls": 0}

    def _generate_content(*, model, contents):
        del model, contents
        state["calls"] += 1
        if state["fail"]:
            raise RuntimeError("429 resource_exhausted")
        return SimpleNamespace(text='{"action":"BUY","confidence":70,"reason":"ok"}')

    return state, _generate_content


def test_gemini_block_from_last_stock_of_batch_expires_before_next_day(monkeypatch):
    # [VCP-041] 1일차 마지막 종목에서 체인 전체가 429 로 막혀도 2일차 첫 종목은 다시 호출한다.
    state, generate_content = _flaky_gemini()
    analyzer, clock = _gemini_only_analyzer_with_clock(monkeypatch, generate_content)

    day1 = asyncio.run(analyzer.analyze_stock("A", {"ticker": "000001"}))
    assert day1["gemini_recommendation"] is None
    assert analyzer.gemini_blocked_models

    state.update(fail=False, calls=0)
    clock["now"] = 86_400.0
    day2 = asyncio.run(analyzer.analyze_stock("B", {"ticker": "000002"}))

    assert day2["gemini_recommendation"]["action"] == "BUY"
    assert state["calls"] == 1


def test_gemini_block_holds_within_ttl(monkeypatch):
    # TTL 안에서는 429 폭주 중인 모델을 다시 부르지 않는다.
    state, generate_content = _flaky_gemini()
    analyzer, clock = _gemini_only_analyzer_with_clock(monkeypatch, generate_content)
    asyncio.run(analyzer.analyze_stock("A", {"ticker": "000001"}))

    state.update(fail=False, calls=0)
    clock["now"] = 599.0
    result = asyncio.run(analyzer.analyze_stock("B", {"ticker": "000002"}))

    assert result["gemini_recommendation"] is None
    assert state["calls"] == 0


def test_analyze_stock_expires_gpt_blocks(monkeypatch):
    # 재분석 진행률 경로는 analyze_batch 를 거치지 않으므로 가드는 analyze_stock 에 있어야 한다.
    monkeypatch.setattr("engine.vcp_ai_analyzer.time.monotonic", lambda: 601.0)

    async def _fake_orchestrate(**_kwargs):
        return {}

    monkeypatch.setattr("engine.vcp_ai_analyzer.orchestrate_stock_analysis_impl", _fake_orchestrate)
    analyzer = object.__new__(VCPMultiAIAnalyzer)
    analyzer.providers, analyzer.second_provider = ["gemini", "gpt"], "gpt"
    analyzer.gemini_blocked_models = {"gemini-x"}
    analyzer.gpt_quota_exhausted, analyzer.gpt_blocked_reason = True, "quota-like-402"
    analyzer.zai_disabled_reason = "prompt-echo responses"
    analyzer._session_blocks_since = 0.0

    asyncio.run(analyzer.analyze_stock("A", {"ticker": "000001"}))

    assert analyzer.gemini_blocked_models == set()
    assert analyzer.gpt_quota_exhausted is False and analyzer.gpt_blocked_reason is None
    assert analyzer.zai_disabled_reason is None
    assert analyzer._session_blocks_since is None


def test_expire_session_blocks_resets_clock_when_nothing_blocked(monkeypatch):
    # 빈 상태에서 옛 시각이 남으면 다음 차단이 곧바로 풀린다.
    monkeypatch.setattr("engine.vcp_ai_analyzer.time.monotonic", lambda: 1000.0)
    analyzer = object.__new__(VCPMultiAIAnalyzer)
    analyzer._session_blocks_since = 0.0
    analyzer._expire_session_blocks()
    assert analyzer._session_blocks_since is None


def test_expire_session_blocks_clears_zai_disabled_reason(monkeypatch):
    # Z.ai 메타 응답 비활성화도 다른 플래그처럼 10분 뒤 풀려야 한다 [VCP-045].
    clock = {"now": 0.0}
    monkeypatch.setattr("engine.vcp_ai_analyzer.time.monotonic", lambda: clock["now"])
    analyzer = object.__new__(VCPMultiAIAnalyzer)
    analyzer.zai_disabled_reason = "prompt-echo responses"

    analyzer._expire_session_blocks()
    assert analyzer._session_blocks_since == 0.0
    assert analyzer.zai_disabled_reason == "prompt-echo responses"

    clock["now"] = 600.0
    analyzer._expire_session_blocks()
    assert analyzer.zai_disabled_reason is None
    assert analyzer._session_blocks_since is None
