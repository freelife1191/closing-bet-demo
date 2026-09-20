#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""[JONGGA-028] 종가 AI 판정 원천의 우선순위를 고정한다."""

import math

from app.routes.kr_market_jongga_ai_payload_helpers import (
    _build_ai_signal_from_jongga_signal,
    _extract_jongga_ai_evaluation,
)


def test_jongga_ai_evaluation_prefers_valid_top_level_verdict_and_reason():
    signal = {
        "stock_code": "000660",
        "stock_name": "SK하이닉스",
        "ai_evaluation": {"action": "HOLD", "confidence": 0, "reason": "새 판정 사유"},
        "score": {
            "total": 15,
            "llm_reason": "오래된 본문 사유",
            "ai_evaluation": {"action": "BUY", "confidence": 91, "reason": "오래된 score 사유"},
        },
        "score_details": {
            "ai_evaluation": {"action": "SELL", "confidence": 88, "reason": "오래된 details 사유"},
        },
    }

    evaluation = _extract_jongga_ai_evaluation(signal)
    ai_signal = _build_ai_signal_from_jongga_signal(
        signal,
        include_without_ai=False,
        allow_numeric_score_fallback=True,
    )

    assert evaluation == {"action": "HOLD", "confidence": 0, "reason": "새 판정 사유"}
    assert ai_signal["gemini_recommendation"] == evaluation


def test_jongga_ai_evaluation_keeps_the_first_reason_only_verdict_as_hold():
    signal = {
        "ai_evaluation": {"action": "UNKNOWN", "confidence": 0, "reason": "잘못된 최신 판정"},
        "score": {"llm_reason": "호환용 오래된 본문 사유"},
        "score_details": {"ai_evaluation": {"action": "BUY", "reason": "더 오래된 판정"}},
    }

    evaluation = _extract_jongga_ai_evaluation(signal)

    assert evaluation == {
        "action": "HOLD",
        "confidence": 0,
        "reason": "잘못된 최신 판정",
    }


def test_jongga_ai_evaluation_uses_legacy_reason_only_for_the_first_valid_action():
    signal = {
        "ai_evaluation": {"action": "HOLD", "confidence": 0, "reason": ""},
        "score": {
            "llm_reason": "호환용 오래된 본문 사유",
            "ai_evaluation": {"action": "BUY", "confidence": 91, "reason": "더 오래된 판정"},
        },
    }

    assert _extract_jongga_ai_evaluation(signal) == {
        "action": "HOLD",
        "confidence": 0,
        "reason": "호환용 오래된 본문 사유",
    }


def test_jongga_ai_evaluation_accepts_a_bare_reason_at_its_original_priority():
    signal = {
        "ai_evaluation": "최상위 사유만 남은 판정",
        "score": {"ai_evaluation": {"action": "BUY", "reason": "오래된 매수 판정"}},
    }

    assert _extract_jongga_ai_evaluation(signal) == {
        "action": "HOLD",
        "confidence": None,
        "reason": "최상위 사유만 남은 판정",
    }


def test_jongga_ai_evaluation_ignores_non_string_actions_and_reasons():
    signal = {
        "ai_evaluation": {"action": ["BUY"], "reason": {"text": "잘못된 사유"}},
        "score": {"ai_evaluation": {"action": "SELL", "reason": "다음 유효한 판정"}},
        "score_details": {"ai_evaluation": {"action": 123, "reason": ["잘못된 세부 사유"]}},
    }

    assert _extract_jongga_ai_evaluation(signal) == {
        "action": "SELL",
        "reason": "다음 유효한 판정",
    }


def test_jongga_ai_evaluation_skips_an_invalid_action_without_a_string_reason():
    signal = {
        "ai_evaluation": {"action": "UNKNOWN", "reason": ""},
        "score": {"ai_evaluation": {"action": "BUY", "reason": "다음 유효한 판정"}},
    }

    assert _extract_jongga_ai_evaluation(signal) == {
        "action": "BUY",
        "reason": "다음 유효한 판정",
    }


def test_jongga_ai_evaluation_keeps_only_normalized_transport_fields():
    signal = {
        "ai_evaluation": {
            "action": "BUY",
            "reason": "수급이 개선되었습니다.",
            "confidence": 82.5,
            "model": "gemini-3.7-flash",
            "provider_payload": {"unsafe": "metadata"},
        },
    }

    assert _extract_jongga_ai_evaluation(signal) == {
        "action": "BUY",
        "reason": "수급이 개선되었습니다.",
        "confidence": 82.5,
        "model": "gemini-3.7-flash",
    }


def test_jongga_ai_evaluation_discards_malformed_reason_confidence_and_model_values():
    malformed_values = [True, {"value": 80}, math.nan, math.inf, -math.inf]

    for confidence in malformed_values:
        signal = {
            "ai_evaluation": {
                "action": "BUY",
                "reason": {},
                "confidence": confidence,
                "model": {},
            },
        }

        assert _extract_jongga_ai_evaluation(signal) == {"action": "BUY"}


def test_jongga_ai_evaluation_preserves_string_or_null_confidence_only():
    for confidence in ("80", None):
        signal = {
            "ai_evaluation": {
                "action": "BUY",
                "reason": "근거",
                "confidence": confidence,
                "model": "gemini",
            },
        }

        assert _extract_jongga_ai_evaluation(signal) == {
            "action": "BUY",
            "reason": "근거",
            "confidence": confidence,
            "model": "gemini",
        }


def test_jongga_ai_evaluation_drops_integers_outside_the_javascript_number_range():
    for confidence in (10**400, -(10**400)):
        signal = {
            "ai_evaluation": {
                "action": "BUY",
                "reason": "근거",
                "confidence": confidence,
            },
        }

        assert _extract_jongga_ai_evaluation(signal) == {
            "action": "BUY",
            "reason": "근거",
        }
