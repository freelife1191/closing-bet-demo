#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LLM Analyzer 파서 분리 회귀 테스트
"""

import os
import sys
import types


sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from engine.llm_analyzer_parsers import (
    build_result_map,
    parse_batch_response,
    parse_json_response,
)


def _logger():
    return types.SimpleNamespace(
        warning=lambda *_a, **_k: None,
        error=lambda *_a, **_k: None,
        debug=lambda *_a, **_k: None,
    )


def test_parse_json_response_injects_normalized_model():
    payload = parse_json_response(
        response_text='{"score": 2, "reason": "ok"}',
        stock_name="삼성전자",
        model_name="gemini-flash-latest",
        logger=_logger(),
    )

    assert payload is not None
    assert payload["score"] == 2
    assert payload["model"] == "Gemini Flash (Latest)"


def test_parse_batch_response_returns_empty_list_on_invalid_json():
    payload = parse_batch_response(
        response_text="not-a-json",
        logger=_logger(),
    )
    assert payload == []


def test_build_result_map_uses_name_key_and_defaults():
    result = build_result_map(
        results_list=[
            {"name": "A", "score": 3, "action": "BUY", "confidence": 88, "reason": "good"},
            {"score": 2},  # name 없음 -> skip
        ],
        model_name="gemini-flash-latest",
    )

    assert "A" in result
    assert result["A"]["action"] == "BUY"
    assert result["A"]["model"] == "Gemini Flash (Latest)"


def test_parse_json_response_handles_markdown_code_fence():
    payload = parse_json_response(
        response_text='```json\n{"score": 1, "reason": "ok"}\n```',
        stock_name="테스트",
        model_name="gemini-2.0-flash",
        logger=_logger(),
    )
    assert payload is not None
    assert payload["score"] == 1


def test_parse_batch_response_handles_markdown_code_fence():
    payload = parse_batch_response(
        response_text='```json\n[{"name":"A","score":2}]\n```',
        logger=_logger(),
    )
    assert isinstance(payload, list)
    assert payload[0]["name"] == "A"
