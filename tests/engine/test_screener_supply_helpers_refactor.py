#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Screener supply helper 분해 회귀 테스트
"""

from __future__ import annotations

import pandas as pd

from engine.screener_supply_helpers import (
    calculate_supply_score_from_csv,
    calculate_supply_score_with_toss,
)


class _DummyToss:
    def __init__(self, payload=None, raises=False):
        self.payload = payload
        self.raises = raises

    def get_investor_trend(self, _ticker, days=5):
        assert days == 5
        if self.raises:
            raise RuntimeError("boom")
        return self.payload


def test_calculate_supply_score_with_toss_uses_primary_payload():
    result = calculate_supply_score_with_toss(
        ticker="005930",
        toss_collector=_DummyToss(payload={"foreign": 10}),
        fallback_fn=lambda _ticker: {"score": -1},
        score_supply_from_toss_trend_fn=lambda trend: {"score": trend["foreign"]},
    )
    assert result == {"score": 10}


def test_calculate_supply_score_with_toss_falls_back_on_empty_or_error():
    fallback = lambda _ticker: {"score": 0, "foreign_1d": 0, "inst_1d": 0}
    result_empty = calculate_supply_score_with_toss(
        ticker="005930",
        toss_collector=_DummyToss(payload=None),
        fallback_fn=fallback,
        score_supply_from_toss_trend_fn=lambda _trend: {"score": 99},
    )
    result_error = calculate_supply_score_with_toss(
        ticker="005930",
        toss_collector=_DummyToss(raises=True),
        fallback_fn=fallback,
        score_supply_from_toss_trend_fn=lambda _trend: {"score": 99},
    )
    assert result_empty["score"] == 0
    assert result_error["score"] == 0


def test_calculate_supply_score_from_csv_handles_missing_index():
    result = calculate_supply_score_from_csv(
        ticker="005930",
        inst_by_ticker={},
        target_datetime=None,
        score_supply_from_csv_fn=lambda *_a, **_k: {"score": 9},
    )
    assert result["score"] == 0


def test_calculate_supply_score_from_csv_delegates_to_score_fn():
    frame = pd.DataFrame([{"value": 1}])
    result = calculate_supply_score_from_csv(
        ticker="005930",
        inst_by_ticker={"005930": frame},
        target_datetime="2026-02-21",
        score_supply_from_csv_fn=lambda ticker_inst, target_datetime: {
            "score": len(ticker_inst),
            "target": target_datetime,
        },
    )
    assert result["score"] == 1
    assert result["target"] == "2026-02-21"

