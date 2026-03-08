#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VCP GPT second provider 경로 테스트.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import engine.vcp_ai_analyzer as analyzer_module


class DummyOpenAIError(Exception):
    """status_code를 포함한 OpenAI 에러 테스트 더블."""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


class DummyMessage:
    """OpenAI message 더블."""

    def __init__(self, content):
        self.content = content
        self.reasoning_content = None


class DummyChoice:
    """OpenAI choice 더블."""

    def __init__(self, content):
        self.message = DummyMessage(content)


class DummyResponse:
    """OpenAI response 더블."""

    def __init__(self, content):
        self.choices = [DummyChoice(content)]


class DummyResponsesResponse:
    """OpenAI responses API 응답 더블."""

    def __init__(self, content):
        self.output_text = content
        self.output = []


class DummyChatCompletions:
    """chat.completions.create 호출 기록용 더블."""

    def __init__(self, outcomes: list[object]):
        self._outcomes = list(outcomes)
        self.calls: list[dict] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if not self._outcomes:
            raise AssertionError("등록된 GPT 응답이 부족합니다.")

        outcome = self._outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        if callable(outcome):
            outcome = outcome(kwargs)
        return DummyResponse(outcome)


class DummyChat:
    """OpenAI chat 더블."""

    def __init__(self, outcomes: list[object]):
        self.completions = DummyChatCompletions(outcomes)


class DummyResponses:
    """responses.create 호출 기록용 더블."""

    def __init__(self, outcomes: list[object]):
        self._outcomes = list(outcomes)
        self.calls: list[dict] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if not self._outcomes:
            raise AssertionError("등록된 GPT 응답이 부족합니다.")

        outcome = self._outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        if callable(outcome):
            outcome = outcome(kwargs)
        return DummyResponsesResponse(outcome)


class DummyClient:
    """OpenAI client 더블."""

    def __init__(self, outcomes: list[object]):
        self.chat = DummyChat(outcomes)
        self.responses = DummyResponses(outcomes)


def _sample_stock() -> dict:
    return {
        "ticker": "000001",
        "current_price": 12345,
        "score": 81,
        "vcp_score": 88,
        "contraction_ratio": 0.72,
        "foreign_5d": 120000,
        "inst_5d": 80000,
        "foreign_1d": 25000,
        "inst_1d": 11000,
        "skip_gemini": True,
    }


def _build_analyzer(monkeypatch, outcomes: list[object], *, zai_client=None):
    monkeypatch.setenv("VCP_AI_PROVIDERS", "gemini,gpt,z.ai")
    monkeypatch.setenv("VCP_SECOND_PROVIDER", "gpt")
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")
    monkeypatch.setenv("VCP_GPT_MODEL", "gpt-5-nano")
    monkeypatch.setenv("VCP_GPT_FALLBACK_MODEL", "gpt-5-mini")
    monkeypatch.setenv("VCP_GPT_MAX_ATTEMPTS", "3")
    monkeypatch.setenv("VCP_GPT_API_TIMEOUT", "30")

    client = DummyClient(outcomes)
    monkeypatch.setattr(analyzer_module, "init_gemini_client", lambda *args, **kwargs: None)
    monkeypatch.setattr(analyzer_module, "init_gpt_client", lambda *args, **kwargs: client)
    monkeypatch.setattr(analyzer_module, "init_zai_client", lambda *args, **kwargs: zai_client)

    analyzer = analyzer_module.VCPMultiAIAnalyzer()
    return analyzer, client


def test_second_provider_gpt_uses_gpt_5_nano_and_strict_system_prompt(monkeypatch):
    analyzer, client = _build_analyzer(
        monkeypatch,
        [
            '{"action":"BUY","confidence":81,"reason":"[핵심 투자 포인트]\\n• VCP 수축이 안정적으로 진행 중입니다.\\n• 외국인과 기관 수급이 모두 순매수 우위입니다.\\n\\n[리스크 요인]\\n• 단기 변동성 확대 가능성은 남아 있습니다.\\n\\n[종합 의견]\\n수급과 패턴이 동시에 받쳐 주고 있어 단기 추세 매수 관점이 유효합니다."}',
        ],
    )

    result = asyncio.run(analyzer.analyze_stock("테스트종목", _sample_stock()))

    assert result["gpt_recommendation"] is not None
    assert result["gpt_recommendation"]["action"] == "BUY"
    assert result["gpt_recommendation"]["model"] == "gpt-5-nano"
    assert [call["model"] for call in client.responses.calls] == ["gpt-5-nano"]
    assert "max_output_tokens" in client.responses.calls[0]
    assert "temperature" not in client.responses.calls[0]

    system_prompt = client.responses.calls[0]["instructions"]
    assert "JSON 객체 1개만" in system_prompt
    assert "[핵심 투자 포인트]" in system_prompt
    assert "BUY, SELL, or HOLD" in system_prompt


def test_second_provider_gpt_switches_to_gpt_5_mini_on_429(monkeypatch):
    analyzer, client = _build_analyzer(
        monkeypatch,
        [
            DummyOpenAIError("rate limited", status_code=429),
            '{"action":"HOLD","confidence":64,"reason":"[핵심 투자 포인트]\\n• VCP 형태는 유지되지만 오늘 수급 강도는 다소 둔화되었습니다.\\n• 추격 매수보다는 눌림 확인이 더 적절합니다.\\n\\n[리스크 요인]\\n• 단기 거래량 감소가 이어질 수 있습니다.\\n\\n[종합 의견]\\n방향성은 살아 있지만 즉시 매수보다 관망이 더 합리적인 구간입니다."}',
        ],
    )

    result = asyncio.run(analyzer.analyze_stock("테스트종목", _sample_stock()))

    assert result["gpt_recommendation"] is not None
    assert result["gpt_recommendation"]["model"] == "gpt-5-mini"
    assert [call["model"] for call in client.responses.calls] == ["gpt-5-nano", "gpt-5-mini"]


def test_second_provider_gpt_repairs_invalid_json_response(monkeypatch):
    analyzer, client = _build_analyzer(
        monkeypatch,
        [
            "이 응답은 JSON 형식이 아닙니다. 종합적으로 보면 매수 쪽 해석이 가능합니다.",
            '{"action":"BUY","confidence":77,"reason":"[핵심 투자 포인트]\\n• 변동성 수축과 5일 누적 수급이 동시에 우호적입니다.\\n• 오늘 수급도 순매수로 유지돼 추세 연속성 기대가 가능합니다.\\n\\n[리스크 요인]\\n• 단기 과열 시 눌림이 나타날 수 있습니다.\\n\\n[종합 의견]\\n즉시 추격보다는 분할 접근이 유효하지만 전체 판단은 매수 우위입니다."}',
        ],
    )

    result = asyncio.run(analyzer.analyze_stock("테스트종목", _sample_stock()))

    assert result["gpt_recommendation"] is not None
    assert result["gpt_recommendation"]["action"] == "BUY"
    assert result["gpt_recommendation"]["model"] == "gpt-5-nano"
    assert len(client.responses.calls) == 2
    assert "정규화" in client.responses.calls[1]["instructions"]


def test_second_provider_gpt_falls_back_to_zai_on_quota_exhausted(monkeypatch):
    analyzer, client = _build_analyzer(
        monkeypatch,
        [
            DummyOpenAIError("insufficient_quota: credit exhausted", status_code=429),
        ],
        zai_client=object(),
    )

    calls = []

    async def _fake_analyze_with_zai(stock_name, stock_data, prompt=None):
        calls.append(
            {
                "stock_name": stock_name,
                "ticker": stock_data["ticker"],
                "prompt": prompt,
            }
        )
        return {
            "action": "BUY",
            "confidence": 74,
            "reason": "[핵심 투자 포인트]\n• z.ai fallback 경로입니다.\n• GPT 크레딧 소진으로 대체 응답을 사용합니다.\n\n[리스크 요인]\n• GPT 원응답 부재.\n\n[종합 의견]\nz.ai 기준으로 매수 우위입니다.",
            "model": "glm-4.6V-Flash",
        }

    analyzer._analyze_with_zai = _fake_analyze_with_zai

    result = asyncio.run(analyzer.analyze_stock("테스트종목", _sample_stock()))

    assert result["gpt_recommendation"] is not None
    assert result["gpt_recommendation"]["model"] == "glm-4.6V-Flash"
    assert len(calls) == 1
    assert [call["model"] for call in client.responses.calls] == ["gpt-5-nano"]
