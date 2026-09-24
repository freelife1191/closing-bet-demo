#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VCP AI analyzer helper 분리 회귀 테스트
"""

import os
import sys

import pytest

sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from engine.vcp_ai_analyzer_helpers import (
    build_vcp_rule_based_recommendation,
    build_vcp_prompt,
    extract_openai_message_text,
    is_prompt_echo_response,
    is_low_quality_recommendation,
    parse_json_response,
)


def test_build_vcp_prompt_includes_stock_name_and_score():
    prompt = build_vcp_prompt("삼성전자", {"score": 77, "current_price": 10000})

    assert "삼성전자" in prompt
    assert "77" in prompt
    assert "JSON" in prompt


def test_build_vcp_prompt_avoids_hardcoded_threshold_and_mentions_score_context():
    prompt = build_vcp_prompt(
        "고영",
        {
            "score": 7,
            "vcp_score": 15,
            "current_price": 33100,
        },
    )

    assert "(최소 60점 이상)" not in prompt
    assert "VCP 패턴 보조 점수" in prompt
    assert "점수의 절대 임계값을 임의로 가정하지 말고" in prompt


def test_parse_json_response_handles_markdown_fenced_json():
    text = "```json\n{\"action\":\"buy\",\"confidence\":88,\"reason\":\"ok\"}\n```"

    parsed = parse_json_response(text)

    assert parsed is not None
    assert parsed["action"] == "BUY"
    assert parsed["confidence"] == 88


def test_is_prompt_echo_response_detects_meta_instruction_restatement():
    meta_text = """
    1.  **Analyze the Request:**
        *   **Role:** Financial data analyst.
        *   **Task:** Analyze the provided stock data and return JSON.
        *   **Constraints:** Output only valid JSON.
    """
    json_text = '{"action":"BUY","confidence":75,"reason":"수급 개선이 확인됩니다."}'

    assert is_prompt_echo_response(meta_text) is True
    assert is_prompt_echo_response(json_text) is False


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
    assert any("가" <= ch <= "힣" for ch in parsed["reason"])


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
        "reason": (
            "VCP 점수 82점과 5일 순매수 전환이 동시에 확인되어 단기 돌파 가능성이 높습니다. "
            "다만 거래량이 급감할 경우 변동성 확대가 나올 수 있어 분할 진입과 손절 관리가 필요합니다."
        ),
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


def test_build_vcp_rule_based_recommendation_never_buys_and_sells_only_on_outflows():
    """[VCP-033] 폴백은 BUY 를 내지 않고, 5일·1일 수급이 모두 순매도일 때만 SELL 이다."""
    inflow_case = build_vcp_rule_based_recommendation(
        stock_name="A",
        stock_data={"score": 83, "contraction_ratio": 0.72, "foreign_5d": 1000, "inst_5d": 400, "foreign_1d": 100, "inst_1d": 50},
    )
    mixed_case = build_vcp_rule_based_recommendation(
        stock_name="B",
        stock_data={"score": 69, "contraction_ratio": 0.9, "foreign_5d": 10, "inst_5d": -5, "foreign_1d": 0, "inst_1d": 0},
    )
    outflow_case = build_vcp_rule_based_recommendation(
        stock_name="C",
        stock_data={"score": 58, "contraction_ratio": 1.03, "foreign_5d": -500, "inst_5d": -300, "foreign_1d": -80, "inst_1d": -40},
    )

    assert inflow_case["action"] == "HOLD"
    assert mixed_case["action"] == "HOLD"
    assert outflow_case["action"] == "SELL"
    assert outflow_case["reason"].endswith("5일·1일 수급이 모두 순매도라 SELL 로 판단합니다.")
    assert {inflow_case["confidence"], mixed_case["confidence"], outflow_case["confidence"]} == {55}


def test_rule_based_fallback_holds_low_composite_score_with_inflows():
    """[VCP-033] 합산 27~53 의 정상 시그널(수급 유입)은 SELL 이 아니라 HOLD 다."""
    result = build_vcp_rule_based_recommendation(
        stock_name="톱텍",
        stock_data={"score": 31, "contraction_ratio": 0.55, "foreign_5d": 120, "inst_5d": 30, "foreign_1d": 5, "inst_1d": 2},
    )

    assert result["action"] == "HOLD"
    assert result["confidence"] == 55
    assert "종합 점수 31.0점" in result["reason"]
    assert "변동성 수축 신호가 유지되는 구간입니다" in result["reason"]
    assert result["reason"].endswith("이 신호를 종합해 현재 판단은 HOLD입니다.")


def test_rule_based_fallback_treats_flat_one_day_flow_as_not_outflow():
    """5일이 순매도여도 1일이 0 이면 순매도가 아니다(`<` 를 `<=` 로 잘못 쓰면 잡힌다)."""
    result = build_vcp_rule_based_recommendation(
        stock_name="A",
        stock_data={"score": 40, "contraction_ratio": 0.6, "foreign_5d": -100, "inst_5d": 0, "foreign_1d": 0, "inst_1d": 0},
    )

    assert result["action"] == "HOLD"
    assert "5일 수급은 순매도 우위입니다. 1일 수급은 중립입니다." in result["reason"]


def test_rule_based_fallback_describes_contraction_without_score():
    """패턴 상태 문장은 수축비만으로 정하고, 0 이하 수축비는 결측으로 본다."""
    strong = build_vcp_rule_based_recommendation(stock_name="A", stock_data={"contraction_ratio": 0.39})
    missing = build_vcp_rule_based_recommendation(stock_name="B", stock_data={"score": 27, "contraction_ratio": 0})

    assert "수축비율 0.39로 변동성 수축 신호가 강한 편입니다." in strong["reason"]
    assert strong["reason"].endswith("정보가 부족하여 보수적으로 HOLD 판단을 유지합니다.")
    assert "종합 점수 27.0점이 확인됩니다." in missing["reason"]
    assert "강한 편" not in missing["reason"] and "수축비율" not in missing["reason"]


@pytest.mark.parametrize(
    "ratio, expected",
    [
        (0.5, "강한 편"),
        (0.7, "유지되는 구간"),
        (0.71, "약화된 구간"),
        (0.4952, "강한 편"),
        (0.5027, "강한 편"),
    ],
)
def test_rule_based_fallback_contraction_boundaries_follow_the_shown_two_decimals(ratio, expected):
    """경계 0.5·0.7 은 포함이고, 문장에 적는 소수 둘째 자리 값으로 판정한다(0.4952 와 0.5027 은 둘 다 「0.50」)."""
    result = build_vcp_rule_based_recommendation(stock_name="A", stock_data={"contraction_ratio": ratio})

    assert f"수축비율 {ratio:.2f}로 변동성 수축 신호가 {expected}" in result["reason"]


def test_rule_based_fallback_treats_negative_contraction_ratio_as_missing():
    result = build_vcp_rule_based_recommendation(stock_name="A", stock_data={"score": 30, "contraction_ratio": -0.1})

    assert "수축비율" not in result["reason"]
    assert "종합 점수 30.0점이 확인됩니다." in result["reason"]


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


@pytest.mark.parametrize(
    "missing_value",
    [None, "", float("nan"), float("inf"), "not-a-number"],
)
def test_rule_based_fallback_keeps_missing_one_day_flow_out_of_reason(missing_value):
    result = build_vcp_rule_based_recommendation(
        stock_name="A",
        stock_data={
            "score": 83,
            "contraction_ratio": 0.72,
            "foreign_5d": 100,
            "inst_5d": 20,
            "foreign_1d": missing_value,
            "inst_1d": 10,
        },
    )

    assert result["action"] == "HOLD"
    assert result["confidence"] == 55
    assert "정보가 부족" in result["reason"]
    assert "1일 수급" not in result["reason"]
    assert all(token not in result["reason"].lower() for token in ("nan", "inf", "점수 0.0", "수축비율 1.00"))


def test_rule_based_fallback_keeps_absent_core_data_as_conservative_hold():
    result = build_vcp_rule_based_recommendation(stock_name="B", stock_data={})

    assert result == {
        "action": "HOLD",
        "confidence": 55,
        "reason": "B는 정보가 부족하여 보수적으로 HOLD 판단을 유지합니다.",
    }


def test_rule_based_fallback_keeps_absent_one_day_fields_out_of_verdict():
    result = build_vcp_rule_based_recommendation(
        stock_name="B",
        stock_data={
            "score": 83,
            "contraction_ratio": 0.72,
            "foreign_5d": 100,
            "inst_5d": 20,
        },
    )

    assert result["action"] == "HOLD"
    assert result["confidence"] == 55
    assert "1일 수급" not in result["reason"]


def test_rule_based_fallback_partial_sell_uses_only_real_negative_evidence():
    low_score = build_vcp_rule_based_recommendation(stock_name="D", stock_data={"score": 58})
    negative_flows = build_vcp_rule_based_recommendation(
        stock_name="E",
        stock_data={"foreign_5d": -10, "inst_5d": -5, "foreign_1d": -3, "inst_1d": -2},
    )

    assert low_score["action"] == "HOLD"
    assert low_score["confidence"] == 55
    assert "종합 점수 58.0점" in low_score["reason"]
    assert negative_flows["action"] == "SELL"
    assert negative_flows["confidence"] == 55
    assert "점수" not in negative_flows["reason"]
    assert "5일 수급은 순매도 우위입니다" in negative_flows["reason"]
    assert "1일 수급은 순매도 우위입니다" in negative_flows["reason"]
    assert negative_flows["reason"].endswith("5일·1일 수급이 모두 순매도라 SELL 로 판단합니다.")


def test_rule_based_fallback_complete_data_verdicts_ignore_score():
    zero_case = build_vcp_rule_based_recommendation(
        stock_name="C",
        stock_data={
            "score": 69,
            "contraction_ratio": 0.90,
            "foreign_5d": 10,
            "inst_5d": -5,
            "foreign_1d": 0,
            "inst_1d": 0,
        },
    )
    buy_case = build_vcp_rule_based_recommendation(
        stock_name="D",
        stock_data={
            "score": 83,
            "contraction_ratio": 0.72,
            "foreign_5d": 1000,
            "inst_5d": 400,
            "foreign_1d": 100,
            "inst_1d": 50,
        },
    )
    sell_case = build_vcp_rule_based_recommendation(
        stock_name="E",
        stock_data={
            "score": 58,
            "contraction_ratio": 1.03,
            "foreign_5d": -500,
            "inst_5d": -300,
            "foreign_1d": -80,
            "inst_1d": -40,
        },
    )

    assert zero_case["action"] == "HOLD"
    assert zero_case["confidence"] == 55
    assert "1일 수급은 중립입니다" in zero_case["reason"]
    assert buy_case["action"] == "HOLD"
    assert buy_case["confidence"] == 55
    assert buy_case["reason"] == (
        "D는 종합 점수 83.0점, 수축비율 0.72로 변동성 수축 신호가 약화된 구간입니다. "
        "5일 수급은 순매수 우위입니다. 1일 수급은 순매수 우위입니다. "
        "이 신호를 종합해 현재 판단은 HOLD입니다."
    )
    assert sell_case["action"] == "SELL"
    assert sell_case["confidence"] == 55


@pytest.mark.parametrize("value", [None, "bad", "", float("inf"), float("-inf"), float("nan")])
def test_invalid_confidence_stays_missing(value):
    """비수치 응답을 0으로 채우면 이 검사가 실패한다."""
    import json

    result = parse_json_response(json.dumps({
        "action": "BUY", "confidence": value,
        "reason": "VCP 점수와 수급을 대조한 합성 분석입니다. 실제 투자 판단이 아닌 회귀 검사입니다.",
    }))
    assert result is not None
    assert result["confidence"] is None
    assert is_low_quality_recommendation(result)


@pytest.mark.parametrize("value, expected", [(0, 0), ("0%", 0), ("75%", 75), (0.9, 0), (100, 100), (-1, 0), (101, 100)])
def test_confidence_preserves_percent_scale_and_real_zero(value, expected):
    import json

    result = parse_json_response(json.dumps({"action": "HOLD", "confidence": value, "reason": "합성 검증 사유"}))
    assert result["confidence"] == expected


@pytest.mark.parametrize("value", [float("inf"), float("-inf"), float("nan"), -1, 101])
def test_raw_nonfinite_or_out_of_range_confidence_is_low_quality(value):
    assert is_low_quality_recommendation({"action": "BUY", "confidence": value, "reason": "합성 검증 사유"})
