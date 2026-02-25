#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VCP AI analyzer helper 분리 회귀 테스트
"""

import os
import sys


sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from engine.vcp_ai_analyzer_helpers import (
    build_perplexity_request,
    build_vcp_prompt,
    extract_perplexity_response_text,
    is_perplexity_quota_exceeded,
    parse_json_response,
)


def test_build_vcp_prompt_includes_stock_name_and_score():
    prompt = build_vcp_prompt("삼성전자", {"score": 77, "current_price": 10000})

    assert "삼성전자" in prompt
    assert "77" in prompt
    assert "JSON" in prompt


def test_parse_json_response_handles_markdown_fenced_json():
    text = "```json\n{\"action\":\"buy\",\"confidence\":88,\"reason\":\"ok\"}\n```"

    parsed = parse_json_response(text)

    assert parsed is not None
    assert parsed["action"] == "BUY"
    assert parsed["confidence"] == 88


def test_perplexity_request_and_response_helpers():
    url, headers, payload = build_perplexity_request(
        prompt="hello",
        api_key="secret",
        model="sonar-pro",
    )

    assert "perplexity.ai" in url
    assert headers["Authorization"] == "Bearer secret"
    assert payload["model"] == "sonar-pro"
    assert payload["messages"][1]["content"] == "hello"

    text = extract_perplexity_response_text(
        {"choices": [{"message": {"content": "{\"action\":\"HOLD\",\"confidence\":60}"}}]}
    )
    assert text == "{\"action\":\"HOLD\",\"confidence\":60}"


def test_is_perplexity_quota_exceeded_detects_quota_like_errors():
    assert is_perplexity_quota_exceeded(402, "payment required") is True
    assert is_perplexity_quota_exceeded(429, "Quota exceeded for this month") is True
    assert is_perplexity_quota_exceeded(403, "insufficient credits") is True
    assert is_perplexity_quota_exceeded(429, "temporary network issue") is False
