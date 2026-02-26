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
    build_vcp_rule_based_recommendation,
    build_perplexity_request,
    build_vcp_prompt,
    extract_openai_message_text,
    extract_perplexity_response_text,
    is_low_quality_recommendation,
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


def test_parse_json_response_handles_nested_and_json_like_payload():
    nested_text = '분석 결과: {"result": {"action":"SELL","confidence":"61","reason":"약세"}}'
    parsed_nested = parse_json_response(nested_text)

    assert parsed_nested is not None
    assert parsed_nested["action"] == "SELL"
    assert parsed_nested["confidence"] == 61

    json_like_text = "{'action': 'buy', 'confidence': 72, 'reason': 'ok'}"
    parsed_json_like = parse_json_response(json_like_text)

    assert parsed_json_like is not None
    assert parsed_json_like["action"] == "BUY"
    assert parsed_json_like["confidence"] == 72


def test_parse_json_response_pattern_fallback_handles_truncated_payload():
    text = 'action: "관망", confidence: "70%", reason: "변동성 축소 구간"'

    parsed = parse_json_response(text)

    assert parsed is not None
    assert parsed["action"] == "HOLD"
    assert parsed["confidence"] == 70
    assert "변동성" in parsed["reason"]


def test_parse_json_response_normalizes_english_reason_to_korean():
    text = (
        '{"action":"BUY","confidence":82,'
        '"reason":"Brief explanation in Korean highlighting the VCP pattern and positive institutional/foreign buying"}'
    )

    parsed = parse_json_response(text)

    assert parsed is not None
    assert parsed["action"] == "BUY"
    assert parsed["confidence"] == 82
    assert "Brief explanation in Korean" not in parsed["reason"]
    assert any("가" <= ch <= "힣" for ch in parsed["reason"])


def test_parse_json_response_replaces_placeholder_korean_reason():
    text = (
        '{"action":"HOLD","confidence":70,'
        '"reason":"기술적 분석 요약 (한국어, 2-3문장)"}'
    )

    parsed = parse_json_response(text)

    assert parsed is not None
    assert parsed["action"] == "HOLD"
    assert parsed["confidence"] == 70
    assert "기술적 분석 요약" not in parsed["reason"]
    assert any("가" <= ch <= "힣" for ch in parsed["reason"])


def test_is_low_quality_recommendation_detects_generic_reason_fallback():
    low_quality = {
        "action": "BUY",
        "confidence": 80,
        "reason": "VCP 패턴과 수급 흐름을 종합할 때 매수 관점이 우세합니다.",
    }
    high_quality = {
        "action": "BUY",
        "confidence": 80,
        "reason": "VCP 점수 82점과 5일 순매수 전환을 근거로 단기 돌파 가능성이 높습니다.",
    }

    assert is_low_quality_recommendation(low_quality) is True
    assert is_low_quality_recommendation(high_quality) is False


def test_parse_json_response_handles_narrative_recommendation_without_json():
    text = """
    Position Recommendation:
    Therefore, a BUY position appears reasonable.

    Confidence Assessment:
    I would assign a confidence level of 75% to this recommendation.
    """

    parsed = parse_json_response(text)

    assert parsed is not None
    assert parsed["action"] == "BUY"
    assert parsed["confidence"] == 75


def test_parse_json_response_handles_korean_narrative_recommendation_without_json():
    text = """
    최종 의견: 현재 구간에서는 관망이 적절합니다.
    신뢰도는 68% 수준으로 판단합니다.
    """

    parsed = parse_json_response(text)

    assert parsed is not None
    assert parsed["action"] == "HOLD"
    assert parsed["confidence"] == 68


def test_parse_json_response_recovers_confidence_from_vcp_score_narrative():
    text = """
    이 데이터를 기반으로 기술적 분석을 진행합니다.
    VCP 시그널 점수: 64.0점이며 패턴은 유지되고 있습니다.
    현재 구간은 매수 신호로 해석될 수 있습니다.
    """

    parsed = parse_json_response(text)

    assert parsed is not None
    assert parsed["action"] == "BUY"
    assert parsed["confidence"] == 64
    assert any("가" <= ch <= "힣" for ch in parsed["reason"])


def test_parse_json_response_ignores_ambiguous_narrative_actions():
    text = """
    Recommendation: BUY or SELL both could be possible.
    Confidence level: 80%
    """

    parsed = parse_json_response(text)

    assert parsed is None


def test_extract_openai_message_text_handles_segmented_content():
    content = [
        {"type": "text", "text": '{"action":"HOLD",'},
        {"type": "output_text", "output_text": '"confidence":64,"reason":"중립"}'},
    ]

    extracted = extract_openai_message_text(content)

    assert '"action":"HOLD"' in extracted
    assert '"confidence":64' in extracted


def test_extract_openai_message_text_handles_reasoning_content_only():
    content = {
        "reasoning_content": '{"action":"BUY","confidence":79,"reason":"수급 개선"}'
    }

    extracted = extract_openai_message_text(content)

    assert '"action":"BUY"' in extracted


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


def test_build_vcp_rule_based_recommendation_changes_by_signal_state():
    buy_case = build_vcp_rule_based_recommendation(
        stock_name="A",
        stock_data={
            "score": 83,
            "contraction_ratio": 0.72,
            "foreign_5d": 1000,
            "inst_5d": 400,
            "foreign_1d": 100,
            "inst_1d": 50,
        },
    )
    hold_case = build_vcp_rule_based_recommendation(
        stock_name="B",
        stock_data={
            "score": 69,
            "contraction_ratio": 0.9,
            "foreign_5d": 10,
            "inst_5d": -5,
            "foreign_1d": 0,
            "inst_1d": 0,
        },
    )
    sell_case = build_vcp_rule_based_recommendation(
        stock_name="C",
        stock_data={
            "score": 58,
            "contraction_ratio": 1.03,
            "foreign_5d": -500,
            "inst_5d": -300,
            "foreign_1d": -80,
            "inst_1d": -40,
        },
    )

    assert buy_case["action"] == "BUY"
    assert hold_case["action"] == "HOLD"
    assert sell_case["action"] == "SELL"
    assert buy_case["confidence"] > hold_case["confidence"]


def test_build_vcp_rule_based_recommendation_handles_nan_without_literal_nan_text():
    result = build_vcp_rule_based_recommendation(
        stock_name="올릭스",
        stock_data={
            "score": 77,
            "contraction_ratio": 1.49,
            "foreign_5d": 119099532900,
            "inst_5d": 0,
            "foreign_1d": "nan",
            "inst_1d": 0,
        },
    )

    assert result["action"] in {"BUY", "SELL", "HOLD"}
    assert "nan" not in result["reason"].lower()
    assert "올릭스는" in result["reason"]
    assert "수급은" in result["reason"]
