#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VCP provider init helper 분해 회귀 테스트
"""

from __future__ import annotations

import sys
from types import SimpleNamespace

from engine.vcp_ai_provider_init_helpers import (
    init_gemini_client,
    init_gpt_client,
    init_zai_client,
    normalize_provider_list,
    normalize_provider_name,
    drop_removed_providers,
    resolve_effective_second_provider,
)


class _Logger:
    """헬퍼가 남긴 경고를 모아 두는 테스트용 로거."""

    def __init__(self):
        self.warnings: list[str] = []

    def info(self, _msg):
        return None

    def warning(self, msg):
        self.warnings.append(str(msg))

    @staticmethod
    def error(_msg):
        return None


def test_init_clients_return_none_when_provider_not_selected():
    config = SimpleNamespace(
        GOOGLE_GENAI_USE_VERTEXAI=True,
        GOOGLE_CLOUD_PROJECT="proj",
        GOOGLE_CLOUD_LOCATION="global",
        OPENAI_API_KEY="y",
    )
    assert init_gemini_client(["gpt"], config, _Logger()) is None
    assert init_gpt_client(["gemini"], config, _Logger()) is None


def test_init_clients_return_none_when_key_missing():
    config = SimpleNamespace(
        GOOGLE_GENAI_USE_VERTEXAI=False,
        GOOGLE_CLOUD_PROJECT="",
        GOOGLE_CLOUD_LOCATION="",
        OPENAI_API_KEY="",
    )
    assert init_gemini_client(["gemini"], config, _Logger()) is None
    assert init_gpt_client(["gpt"], config, _Logger()) is None


def test_init_zai_client_returns_none_when_key_missing():
    config = SimpleNamespace(ZAI_API_KEY="", ZAI_BASE_URL="https://api.z.ai/v1")
    assert init_zai_client(config, _Logger()) is None


def test_init_zai_client_returns_none_when_vcp_zai_fallback_disabled(monkeypatch):
    captured = {"called": False}

    class _FakeOpenAI:
        def __init__(self, **_kwargs):
            captured["called"] = True

    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(OpenAI=_FakeOpenAI))

    config = SimpleNamespace(
        ZAI_API_KEY="zai-key",
        ZAI_BASE_URL="https://api.z.ai/v1",
        VCP_ZAI_FALLBACK_ENABLED=False,
    )

    assert init_zai_client(config, _Logger()) is None
    assert captured["called"] is False


def test_init_zai_client_initializes_openai_compatible_client(monkeypatch):
    captured = {}

    class _FakeOpenAI:
        def __init__(self, api_key=None, base_url=None, timeout=None):
            captured["api_key"] = api_key
            captured["base_url"] = base_url
            captured["timeout"] = timeout

    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(OpenAI=_FakeOpenAI))

    config = SimpleNamespace(
        ZAI_API_KEY="zai-key",
        ZAI_BASE_URL="https://api.z.ai/v1",
        VCP_ZAI_API_TIMEOUT=240,
    )
    client = init_zai_client(config, _Logger())

    assert isinstance(client, _FakeOpenAI)
    assert captured["api_key"] == "zai-key"
    assert captured["base_url"] == "https://api.z.ai/v1"
    assert captured["timeout"] == 240.0


def test_init_zai_client_returns_none_when_openai_missing(monkeypatch):
    monkeypatch.delitem(sys.modules, "openai", raising=False)
    real_import = __import__

    def _fake_import(name, *args, **kwargs):
        if name == "openai":
            raise ModuleNotFoundError("No module named 'openai'")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", _fake_import)
    config = SimpleNamespace(ZAI_API_KEY="zai-key", ZAI_BASE_URL="https://api.z.ai/v1")

    client = init_zai_client(config, _Logger())

    assert client is None


def test_normalize_provider_aliases():
    assert normalize_provider_name("z.ai") == "zai"
    assert normalize_provider_name("openai") == "gpt"
    assert normalize_provider_name("perplexity") == "perplexity"
    assert normalize_provider_list(["gemini", "z.ai", "openai", "zai"]) == [
        "gemini",
        "zai",
        "gpt",
    ]


def test_resolve_effective_second_provider_maps_perplexity_to_gpt():
    """[VCP-046] 운영 .env 에 perplexity 가 남아 있어도 GPT 로 실행하고 그 사실을 남긴다."""
    logger = _Logger()

    assert (
        resolve_effective_second_provider(
            providers=["gemini", "gpt"],
            second_provider="perplexity",
            gpt_ready=True,
            logger=logger,
        )
        == "gpt"
    )
    assert len(logger.warnings) == 1
    assert "perplexity" in logger.warnings[0]


def test_resolve_effective_second_provider_warns_twice_when_gpt_is_not_listed():
    """perplexity 를 gpt 로 바꿨는데 목록에 gpt 가 없으면 두 번째 자리를 비운다.

    `[VCP-003]` 때처럼 두 번째 열이 조용히 비지 않도록 비운 사실도 따로 경고한다.
    """
    logger = _Logger()

    assert (
        resolve_effective_second_provider(
            providers=["gemini"],
            second_provider="perplexity",
            gpt_ready=True,
            logger=logger,
        )
        is None
    )
    assert len(logger.warnings) == 2
    assert "VCP_SECOND_PROVIDER" in logger.warnings[1]


def test_resolve_effective_second_provider_leaves_slot_empty_without_gpt_client():
    """[VCP-048] 목록에 gpt 가 있어도 클라이언트가 없으면 두 번째 자리를 비운다.

    gpt 로 확정하면 재분석이 채워질 수 없는 gpt_recommendation 을 기다려 같은 행을 매번 다시 잡는다.
    """
    logger = _Logger()

    assert (
        resolve_effective_second_provider(
            providers=["gemini", "gpt"],
            second_provider="gpt",
            gpt_ready=False,
            logger=logger,
        )
        is None
    )
    assert len(logger.warnings) == 1
    assert "OPENAI_API_KEY" in logger.warnings[0]


def test_drop_removed_providers_replaces_perplexity_with_gpt():
    """[VCP-046] 운영 .env 를 고치지 않아도 두 번째 AI 가 계속 돌도록 perplexity 자리를 gpt 가 잇는다."""
    logger = _Logger()

    assert drop_removed_providers(["gemini", "perplexity", "gpt"], logger) == ["gemini", "gpt"]
    assert len(logger.warnings) == 1
    assert drop_removed_providers(["gemini", "perplexity"], _Logger()) == ["gemini", "gpt"]
    assert drop_removed_providers(["gemini"], _Logger()) == ["gemini"]
    assert drop_removed_providers(["gemini", "gpt"], _Logger()) == ["gemini", "gpt"]


def test_resolve_effective_second_provider_rejects_unsupported_provider():
    """오케스트레이터가 부르는 경로가 없는 provider 는 실행하지 않는다.

    운영 설정의 VCP_AI_PROVIDERS 에 z.ai 가 들어 있는데, 이것은 GPT 의 fallback 대상이지
    두 번째 자리에 직접 놓을 수 있는 provider 가 아니다.
    """
    logger = _Logger()

    assert (
        resolve_effective_second_provider(
            providers=["gemini", "gpt", "zai"],
            second_provider="zai",
            gpt_ready=True,
            logger=logger,
        )
        is None
    )
    assert len(logger.warnings) == 1


def test_resolve_effective_second_provider_normalizes_aliases():
    """openai 별칭도 gpt 로 정규화한 뒤에 판정한다."""
    assert (
        resolve_effective_second_provider(
            providers=["gemini", "openai"],
            second_provider="openai",
            gpt_ready=True,
            logger=_Logger(),
        )
        == "gpt"
    )
