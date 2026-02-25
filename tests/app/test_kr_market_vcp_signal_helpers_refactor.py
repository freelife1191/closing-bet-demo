#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KR Market VCP 시그널 헬퍼 리팩토링 회귀 테스트
"""

from __future__ import annotations

import app.routes.kr_market_vcp_signal_helpers as vcp_helpers


def test_sort_and_limit_vcp_signals_uses_runtime_limit_when_not_provided(monkeypatch):
    monkeypatch.setattr(vcp_helpers, "resolve_vcp_signals_to_show", lambda **_kwargs: 1)
    signals = [{"score": 10}, {"score": 30}, {"score": 20}]

    result = vcp_helpers._sort_and_limit_vcp_signals(signals)

    assert len(result) == 1
    assert result[0]["score"] == 30


def test_build_vcp_signal_from_row_respects_runtime_min_score(monkeypatch):
    monkeypatch.setattr(vcp_helpers, "resolve_vcp_min_score", lambda **_kwargs: 70.0)
    row = {
        "ticker": "005930",
        "name": "삼성전자",
        "signal_date": "2026-02-24",
        "market": "KOSPI",
        "status": "OPEN",
        "score": 69.9,
    }

    assert vcp_helpers._build_vcp_signal_from_row(row) is None
