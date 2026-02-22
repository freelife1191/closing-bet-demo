#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
generator 후보/선별 개수 정합성 테스트
"""

import os
import sys


sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from engine.generator import _normalize_total_candidates


def test_normalize_total_candidates_keeps_greater_value():
    """후보 수는 최종 선별 수보다 작아지면 안 된다."""
    assert _normalize_total_candidates(12, 8) == 12
    assert _normalize_total_candidates(7, 8) == 8
    assert _normalize_total_candidates(None, 5) == 5
