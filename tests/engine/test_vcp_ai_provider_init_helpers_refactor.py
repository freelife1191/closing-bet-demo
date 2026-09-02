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
    resolve_effective_second_provider,
    resolve_perplexity_disabled,
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


def test_resolve_perplexity_disabled_when_required_key_missing():
    assert resolve_perplexity_disabled(["perplexity"], "gpt", has_api_key=False, logger=_Logger()) is True
    assert resolve_perplexity_disabled(["gemini"], "perplexity", has_api_key=False, logger=_Logger()) is True
    assert resolve_perplexity_disabled(["gemini"], "gpt", has_api_key=False, logger=_Logger()) is False


def test_resolve_effective_second_provider_falls_back_to_gpt():
    """PERPLEXITY_API_KEY 가 없어도 두 번째 자리를 GPT 가 이어받는다."""
    logger = _Logger()

    assert (
        resolve_effective_second_provider(
            providers=["gemini", "gpt"],
            second_provider="perplexity",
            perplexity_disabled=True,
            logger=logger,
        )
        == "gpt"
    )
    assert logger.warnings == []


def test_resolve_effective_second_provider_warns_when_gpt_is_not_listed():
    """폴백할 GPT 가 허용 목록에 없으면 None 을 돌려주고 그 사실을 로그에 남긴다.

    `[VCP-003]` 시점에는 이 상황이 조용히 지나가 두 번째 열이 왜 비었는지 알 방법이
    없었다. 경고가 사라지면 그 침묵이 되살아난다.
    """
    logger = _Logger()

    assert (
        resolve_effective_second_provider(
            providers=["gemini", "perplexity"],
            second_provider="perplexity",
            perplexity_disabled=True,
            logger=logger,
        )
        is None
    )
    assert len(logger.warnings) == 1
    assert "VCP_SECOND_PROVIDER" in logger.warnings[0]


def test_resolve_effective_second_provider_keeps_available_perplexity():
    """쓸 수 있는 Perplexity 를 GPT 로 바꿔치지 않는다.

    허용 목록에 gpt 가 없는 조합으로 둔다. gpt 를 함께 넣으면 아래
    backed_by_gpt_only 검사와 같은 갈래를 두 번 보게 되어, "perplexity 가 목록에 있으면
    실행한다" 는 판정을 아무 검사도 단독으로 덮지 못한다.
    """
    logger = _Logger()

    assert (
        resolve_effective_second_provider(
            providers=["gemini", "perplexity"],
            second_provider="perplexity",
            perplexity_disabled=False,
            logger=logger,
        )
        == "perplexity"
    )
    assert logger.warnings == []


def test_resolve_effective_second_provider_allows_perplexity_backed_by_gpt_only():
    """Perplexity 는 자체 fallback 체인이 있어 providers 에 gpt 만 있어도 실행한다."""
    assert (
        resolve_effective_second_provider(
            providers=["gemini", "gpt"],
            second_provider="perplexity",
            perplexity_disabled=False,
            logger=_Logger(),
        )
        == "perplexity"
    )


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
            perplexity_disabled=False,
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
            perplexity_disabled=False,
            logger=_Logger(),
        )
        == "gpt"
    )
