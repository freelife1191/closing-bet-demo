#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""[JONGGA-008] 확신도 없음이 응답에서 0 으로 둔갑하지 않는지 검사한다.

응답을 만드는 여섯 자리가 모두 같은 규칙을 써야 한다. 한 자리라도 0 을 채우면
화면은 그 종목에 「AI 가 0% 확신한다」는 막대를 그리고, 사용자는 AI 가 실제로
0 을 낸 경우와 구분하지 못한다.
"""

from __future__ import annotations

import os
import sys

import pandas as pd
import pytest

sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from app.routes import kr_market_jongga_ai_payload_helpers as ai_payload_helpers
from app.routes import kr_market_jongga_normalize_helpers as normalize_helpers
from app.routes import kr_market_jongga_reanalysis_helpers as reanalysis_helpers
from app.routes import kr_market_vcp_signal_helpers as vcp_helpers
from engine.llm_analyzer_parsers import build_result_map
from engine.pandas_utils_safe import safe_confidence


# ---------------------------------------------------------------- 공용 헬퍼


@pytest.mark.parametrize(
    "value, expected",
    [
        (None, None),
        (float("nan"), None),
        ("", None),
        ("   ", None),
        ("분석 실패", None),
        # inf 는 OverflowError 를 내며 그것은 ValueError 가 아니다. json.loads 가
        # `Infinity` 를 통과시키므로 LLM 응답으로 실제 들어올 수 있다.
        (float("inf"), None),
        (float("-inf"), None),
        ("inf", None),
        ("1e400", None),
        (78, 78),
        (78.6, 78),
        ("78", 78),
        ("78%", 78),
        ("1,00", 100),
        (0, 0),
        (150, 100),
        (-5, 0),
    ],
)
def test_safe_confidence_separates_missing_from_zero(value, expected):
    assert safe_confidence(value) == expected


def test_safe_confidence_survives_a_list_input():
    """pd.isna 는 배열을 받으면 배열을 돌려주므로 if 문에서 예외가 난다."""
    assert safe_confidence([1, 2]) is None


# ------------------------------------------------- 1) 종가베팅 시그널 정규화


def test_jongga_normalize_leaves_confidence_empty_when_the_signal_has_none():
    signal = {"ticker": "005930", "ai_action": "BUY", "ai_reason": "수급이 개선되었습니다."}

    normalize_helpers._normalize_jongga_signal_for_frontend(signal)

    assert signal["ai_evaluation"]["confidence"] is None


def test_jongga_normalize_keeps_a_real_zero_verdict():
    signal = {
        "ticker": "005930",
        "ai_action": "HOLD",
        "ai_reason": "판단을 유보합니다.",
        "ai_confidence": 0,
    }

    normalize_helpers._normalize_jongga_signal_for_frontend(signal)

    assert signal["ai_evaluation"]["confidence"] == 0


# --------------------------------------------- 2) 종가베팅 AI 페이로드 추출


def test_jongga_ai_evaluation_from_a_bare_reason_string_has_no_confidence():
    signal = {"score_details": {"ai_evaluation": "사유만 남은 기록입니다."}}

    result = ai_payload_helpers._extract_jongga_ai_evaluation(signal)

    assert result["confidence"] is None
    assert result["action"] == "HOLD"


# ------------------------------------------------- 3) VCP 재분석 결과 추출


def test_vcp_recommendation_extract_returns_no_confidence_when_missing():
    ai_results = {
        "005930": {
            "gemini_recommendation": {
                "action": "BUY",
                "reason": "변동성 수축이 확인됩니다.",
            }
        }
    }

    is_valid, action, confidence, _reason = vcp_helpers._extract_vcp_ai_recommendation(
        ai_results, "005930"
    )

    assert is_valid is True
    assert action == "BUY"
    assert confidence is None


def test_vcp_recommendation_extract_returns_no_confidence_on_failure():
    is_valid, _action, confidence, _reason = vcp_helpers._extract_vcp_ai_recommendation(
        {}, "005930"
    )

    assert is_valid is False
    assert confidence is None


def test_vcp_reanalysis_writes_missing_confidence_as_a_blank_cell():
    """실패한 행의 확신도는 signals_log 에서 0 이 아니라 결측이어야 한다."""
    signals_df = pd.DataFrame(
        [{"ticker": "005930", "ai_action": "N/A", "ai_reason": "분석 실패", "ai_confidence": 0.0}]
    )

    vcp_helpers._apply_vcp_reanalysis_updates(
        signals_df,
        [(0, {"ticker": "005930"})],
        {},
    )

    assert pd.isna(signals_df.at[0, "ai_confidence"])


# ------------------------------------------ 4) CSV 행에서 만드는 gemini 추천


def test_vcp_gemini_recommendation_from_a_row_without_confidence():
    row = {
        "ai_action": "BUY",
        "ai_reason": "수급 개선과 변동성 수축이 확인됩니다.",
        "ai_confidence": float("nan"),
    }

    result = vcp_helpers._build_vcp_gemini_recommendation(row)

    assert result["confidence"] is None


def test_vcp_gemini_recommendation_keeps_a_real_verdict():
    row = {
        "ai_action": "BUY",
        "ai_reason": "수급 개선과 변동성 수축이 확인됩니다.",
        "ai_confidence": 78,
    }

    result = vcp_helpers._build_vcp_gemini_recommendation(row)

    assert result["confidence"] == 78


# ------------------------------------------------ 5) 종가베팅 Gemini 재분석


def test_jongga_reanalysis_leaves_confidence_empty_when_the_result_has_none():
    signals = [{"stock_code": "005930", "stock_name": "삼성전자"}]
    results_map = {"삼성전자": {"action": "BUY", "reason": "실적이 개선되었습니다."}}

    updated = reanalysis_helpers._apply_gemini_reanalysis_results(signals, results_map)

    assert updated == 1
    assert signals[0]["ai_evaluation"]["confidence"] is None


# ------------------------------------- 6) signals_log 의 ai_confidence 열 생성


def test_signal_tracker_leaves_confidence_empty_when_no_recommendation():
    """signals_log 의 ai_confidence 열을 만드는 원천이다. 여기서 0 을 넣으면
    그 값이 CSV 를 거쳐 화면까지 흘러간다."""
    from engine.signal_tracker_ai_helpers import apply_ai_results

    signals_df = pd.DataFrame([{"ticker": "005930"}, {"ticker": "000660"}])
    ai_results = {
        "005930": {
            "gemini_recommendation": {
                "action": "BUY",
                "confidence": "77",
                "reason": "수급이 개선되었습니다.",
            }
        }
    }

    result = apply_ai_results(signals_df, ai_results)

    assert result.loc[0, "ai_confidence"] == 77
    assert result.loc[1, "ai_confidence"] is None or pd.isna(result.loc[1, "ai_confidence"])
    assert result.loc[1, "ai_action"] == "N/A"


# ------------------------------------------------------- 7) LLM 응답 파서


def test_build_result_map_leaves_confidence_empty_when_the_model_omits_it():
    result = build_result_map(
        results_list=[{"name": "삼성전자", "score": 3, "action": "BUY", "reason": "좋습니다."}],
        model_name="gemini-flash-latest",
    )

    assert result["삼성전자"]["confidence"] is None


def test_build_result_map_converts_a_string_confidence_to_a_number():
    """LLM 이 문자열로 내는 경로가 있어 형 변환 없이 흘려보내면 화면까지 간다."""
    result = build_result_map(
        results_list=[
            {"name": "삼성전자", "action": "BUY", "confidence": "80", "reason": "좋습니다."}
        ],
        model_name="gemini-flash-latest",
    )

    assert result["삼성전자"]["confidence"] == 80
