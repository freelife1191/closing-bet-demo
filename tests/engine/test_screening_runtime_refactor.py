#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Screening runtime 설정 파서 회귀 테스트
"""

from __future__ import annotations

import engine.screening_runtime as screening_runtime


class _DummyScreening:
    def __init__(self, *, signals_to_show, min_score):
        self.VCP_SIGNALS_TO_SHOW = signals_to_show
        self.VCP_MIN_SCORE = min_score


def test_resolve_vcp_signals_to_show_uses_default_when_invalid(monkeypatch):
    monkeypatch.setattr(
        screening_runtime,
        "SCREENING",
        _DummyScreening(signals_to_show="N/A", min_score=60),
    )

    assert screening_runtime.resolve_vcp_signals_to_show(default=20, minimum=1) == 20


def test_resolve_vcp_signals_to_show_applies_minimum(monkeypatch):
    monkeypatch.setattr(
        screening_runtime,
        "SCREENING",
        _DummyScreening(signals_to_show="-3", min_score=60),
    )

    assert screening_runtime.resolve_vcp_signals_to_show(default=20, minimum=0) == 0
    assert screening_runtime.resolve_vcp_signals_to_show(default=20, minimum=1) == 1


def test_resolve_vcp_min_score_supports_comma_formatted_string(monkeypatch):
    monkeypatch.setattr(
        screening_runtime,
        "SCREENING",
        _DummyScreening(signals_to_show=20, min_score="1,234.5"),
    )

    assert screening_runtime.resolve_vcp_min_score(default=60.0) == 1234.5
