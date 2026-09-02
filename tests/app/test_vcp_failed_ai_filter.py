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
from app.routes.kr_market_helpers import (
    _build_vcp_gemini_recommendation,
    _merge_ai_data_into_vcp_signals,
)


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


def test_cache_without_a_recommendation_keeps_the_one_built_from_csv():
    """추천이 빠진 캐시가 CSV 에서 만든 정상 추천을 지우면 안 된다.

    캐시에는 gemini_recommendation 을 담는 형식과 ai_action 만 담는 형식이 함께
    존재한다. 뒤의 형식이 들어왔을 때 조건 없이 대입하면 화면의 추천이 사라진다.
    """
    csv_recommendation = {
        "action": "BUY",
        "confidence": 78,
        "reason": "수급이 개선되었습니다.",
        "news_sentiment": "positive",
    }
    signals = [{"ticker": "005930", "gemini_recommendation": csv_recommendation}]
    ai_data_map = {"005930": {"ticker": "005930", "ai_action": "BUY", "ai_reason": "수급 개선"}}

    assert _merge_ai_data_into_vcp_signals(signals, ai_data_map) == 1
    assert signals[0]["gemini_recommendation"] == csv_recommendation


def test_failed_recommendation_in_cache_does_not_reach_the_response():
    """캐시의 실패 기록은 CSV 경로와 같은 기준으로 걸러야 한다.

    _build_vcp_gemini_recommendation 이 막아 둔 실패 추천이 이 경로로 되살아나면
    화면은 그 종목에 관망 배지를 단다.
    """
    signals = [{"ticker": "005930", "gemini_recommendation": None}]
    ai_data_map = {
        "005930": {
            "gemini_recommendation": {"action": "N/A", "confidence": 0, "reason": "분석 실패"},
        }
    }

    assert _merge_ai_data_into_vcp_signals(signals, ai_data_map) == 1
    assert signals[0]["gemini_recommendation"] is None


def test_valid_cache_recommendation_still_overwrites_and_news_is_merged():
    """정상 추천은 그대로 반영되고 뉴스 병합도 유지된다."""
    cached = {"action": "SELL", "confidence": 65, "reason": "거래대금이 급감했습니다."}
    signals = [{"ticker": "005930", "gemini_recommendation": None}]
    ai_data_map = {"005930": {"gemini_recommendation": cached, "news": [{"title": "기사"}]}}

    assert _merge_ai_data_into_vcp_signals(signals, ai_data_map) == 1
    assert signals[0]["gemini_recommendation"] == cached
    assert signals[0]["news"] == [{"title": "기사"}]


def test_gpt_and_perplexity_follow_the_same_rule():
    """세 프로바이더 모두 같은 문턱을 넘어야 화면까지 나간다."""
    valid = {"action": "HOLD", "confidence": 55, "reason": "추가 확인이 필요합니다."}
    signals = [{"ticker": "005930"}]
    ai_data_map = {
        "005930": {
            "gpt_recommendation": valid,
            "perplexity_recommendation": {"action": "N/A", "confidence": 0, "reason": "분석 실패"},
        }
    }

    _merge_ai_data_into_vcp_signals(signals, ai_data_map)

    assert signals[0]["gpt_recommendation"] == valid
    assert "perplexity_recommendation" not in signals[0]


def test_fresher_cache_recommendation_replaces_an_existing_valid_one():
    """정상 추천끼리는 캐시 값이 이긴다.

    "덮어쓰지 않는다" 를 기존 값이 있으면 건드리지 않는다는 뜻으로 잘못 읽으면
    재분석으로 갱신된 추천이 화면에 반영되지 않는다.
    """
    stale = {"action": "HOLD", "confidence": 50, "reason": "지난 분석의 사유입니다."}
    fresh = {"action": "BUY", "confidence": 80, "reason": "재분석에서 매수로 바뀐 사유입니다."}
    signals = [{"ticker": "005930", "gemini_recommendation": stale}]

    _merge_ai_data_into_vcp_signals(signals, {"005930": {"gemini_recommendation": fresh}})

    assert signals[0]["gemini_recommendation"] == fresh
