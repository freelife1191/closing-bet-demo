#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VCP provider init helper 분해 회귀 테스트
"""

from __future__ import annotations

from types import SimpleNamespace

from engine.vcp_ai_provider_init_helpers import (
    init_gemini_client,
    init_gpt_client,
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


def test_resolve_perplexity_disabled_when_required_key_missing():
    assert resolve_perplexity_disabled(["perplexity"], "gpt", has_api_key=False, logger=_Logger()) is True
    assert resolve_perplexity_disabled(["gemini"], "perplexity", has_api_key=False, logger=_Logger()) is True
    assert resolve_perplexity_disabled(["gemini"], "gpt", has_api_key=False, logger=_Logger()) is False

