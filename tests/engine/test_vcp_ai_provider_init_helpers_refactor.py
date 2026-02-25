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
    resolve_perplexity_disabled,
)


class _Logger:
    @staticmethod
    def info(_msg):
        return None

    @staticmethod
    def warning(_msg):
        return None

    @staticmethod
    def error(_msg):
        return None


def test_init_clients_return_none_when_provider_not_selected():
    config = SimpleNamespace(GOOGLE_API_KEY="x", OPENAI_API_KEY="y")
    assert init_gemini_client(["gpt"], config, _Logger()) is None
    assert init_gpt_client(["gemini"], config, _Logger()) is None


def test_init_clients_return_none_when_key_missing():
    config = SimpleNamespace(GOOGLE_API_KEY="", OPENAI_API_KEY="")
    assert init_gemini_client(["gemini"], config, _Logger()) is None
    assert init_gpt_client(["gpt"], config, _Logger()) is None


def test_init_zai_client_returns_none_when_key_missing():
    config = SimpleNamespace(ZAI_API_KEY="", ZAI_BASE_URL="https://api.z.ai/v1")
    assert init_zai_client(config, _Logger()) is None


def test_init_zai_client_initializes_openai_compatible_client(monkeypatch):
    captured = {}

    class _FakeOpenAI:
        def __init__(self, api_key=None, base_url=None):
            captured["api_key"] = api_key
            captured["base_url"] = base_url

    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(OpenAI=_FakeOpenAI))

    config = SimpleNamespace(ZAI_API_KEY="zai-key", ZAI_BASE_URL="https://api.z.ai/v1")
    client = init_zai_client(config, _Logger())

    assert isinstance(client, _FakeOpenAI)
    assert captured["api_key"] == "zai-key"
    assert captured["base_url"] == "https://api.z.ai/v1"


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
