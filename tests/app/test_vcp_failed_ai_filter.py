#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VCP 실패 AI 재분석 대상 판별 회귀 테스트
"""

import os
import sys


sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

import pandas as pd

from app.routes.kr_market import _is_vcp_ai_analysis_failed
from app.routes.kr_market_helpers import _build_vcp_gemini_recommendation


def test_failed_when_action_and_reason_missing():
    row = {"ai_action": None, "ai_reason": None, "ai_confidence": 0}
    assert _is_vcp_ai_analysis_failed(row) is True


def test_failed_when_action_is_na_and_reason_is_failure_marker():
    row = {"ai_action": "N/A", "ai_reason": "분석 실패", "ai_confidence": 0}
    assert _is_vcp_ai_analysis_failed(row) is True


def test_failed_when_reason_is_placeholder():
    row = {"ai_action": "HOLD", "ai_reason": "No analysis available.", "ai_confidence": 55}
    assert _is_vcp_ai_analysis_failed(row) is True


def test_not_failed_when_action_and_reason_are_valid():
    row = {"ai_action": "BUY", "ai_reason": "수급 개선과 변동성 수축이 확인됩니다.", "ai_confidence": 78}
    assert _is_vcp_ai_analysis_failed(row) is False


def test_not_failed_when_hold_has_meaningful_reason():
    row = {"ai_action": "HOLD", "ai_reason": "패턴은 형성 중이며 추가 확인이 필요합니다.", "ai_confidence": 62}
    assert _is_vcp_ai_analysis_failed(row) is False


def test_failed_row_does_not_produce_a_recommendation():
    """실패 행은 두 필드가 채워져 있어도 추천 객체를 만들지 않는다.

    재분석이 실패하면 action 에 "N/A" 가, reason 에 "분석 실패" 가 기록된다.
    값의 존재만 보고 통과시키면 화면이 이 행에 관망 배지를 단다.
    """
    row = {"ai_action": "N/A", "ai_reason": "분석 실패", "ai_confidence": 0}
    assert _build_vcp_gemini_recommendation(row) is None


def test_recommendation_is_built_from_a_dataframe_row():
    """응답을 조립하는 경로는 itertuples 가 만드는 namedtuple 을 넘긴다.

    판별이 dict 만 받으면 정상 행까지 실패로 보아 추천이 모두 사라진다.
    """
    signals_df = pd.DataFrame(
        [
            {"ai_action": "BUY", "ai_reason": "수급이 개선되었습니다.", "ai_confidence": 78},
            {"ai_action": "N/A", "ai_reason": "분석 실패", "ai_confidence": 0},
        ]
    )
    valid_row, failed_row = list(signals_df.itertuples(index=False))

    assert _is_vcp_ai_analysis_failed(valid_row) is False
    assert _build_vcp_gemini_recommendation(valid_row) == {
        "action": "BUY",
        "confidence": 78,
        "reason": "수급이 개선되었습니다.",
        "news_sentiment": "positive",
    }
    assert _is_vcp_ai_analysis_failed(failed_row) is True
    assert _build_vcp_gemini_recommendation(failed_row) is None


def test_failed_when_reason_is_nan():
    """CSV 의 빈 사유 칸은 NaN 으로 들어오며 사유가 없는 것으로 봐야 한다.

    NaN 을 그대로 문자열로 만들면 "nan" 이 되어 실질적인 사유로 통과한다.
    """
    signals_df = pd.DataFrame(
        [{"ai_action": "HOLD", "ai_reason": float("nan"), "ai_confidence": 55}]
    )
    (row,) = signals_df.itertuples(index=False)

    assert _is_vcp_ai_analysis_failed(row) is True
    assert _build_vcp_gemini_recommendation(row) is None


def test_recommendation_normalizes_the_action_it_reports():
    """판정과 같은 형태로 내보내야 화면이 배지 표에서 찾을 수 있다.

    실패 여부는 대문자로 바꾼 값으로 재면서 원본을 그대로 내보내면, "buy " 처럼
    공백이 붙은 정상 매수 의견이 화면에서 미분석으로 표시된다.
    """
    row = {"ai_action": "buy ", "ai_reason": "수급이 개선되었습니다.", "ai_confidence": 78}

    assert _is_vcp_ai_analysis_failed(row) is False
    assert _build_vcp_gemini_recommendation(row)["action"] == "BUY"

