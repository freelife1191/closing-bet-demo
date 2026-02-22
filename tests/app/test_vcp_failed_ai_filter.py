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

from app.routes.kr_market import _is_vcp_ai_analysis_failed


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
