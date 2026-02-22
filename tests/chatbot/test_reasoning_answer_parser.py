#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
추론/답변 파서 회귀 테스트
"""

import os
import sys


sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from chatbot.core import _extract_reasoning_and_answer


def test_extract_reasoning_and_answer_with_explicit_headers():
    text = "[추론 과정]\n데이터를 비교해 결론을 냅니다.\n\n[답변]\n최종 답변입니다."
    reasoning, answer = _extract_reasoning_and_answer(text, is_streaming=False)

    assert "데이터를 비교해 결론" in reasoning
    assert answer == "최종 답변입니다."


def test_extract_reasoning_and_answer_fallback_when_answer_header_missing():
    text = "[추론 과정]\n근거를 먼저 설명한 뒤 결론을 제시합니다.\n최종 답변입니다."
    reasoning, answer = _extract_reasoning_and_answer(text, is_streaming=False)

    assert reasoning == ""
    assert "최종 답변입니다." in answer


def test_extract_reasoning_and_answer_streaming_keeps_reasoning_without_answer_header():
    text = "[추론 과정]\n스트리밍 중 추론 텍스트"
    reasoning, answer = _extract_reasoning_and_answer(text, is_streaming=True)

    assert "스트리밍 중 추론 텍스트" in reasoning
    assert answer == ""
