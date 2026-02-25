#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SignalTracker AI 헬퍼 리팩토링 테스트
"""

from __future__ import annotations

import pandas as pd
import engine.signal_tracker_ai_helpers as ai_helpers_module

from engine.signal_tracker_ai_helpers import (
    apply_ai_results,
    build_ai_batch_payload,
    cap_ai_target_signals,
)


def test_cap_ai_target_signals_keeps_top_scores():
    signals_df = pd.DataFrame(
        [{"ticker": f"{i:06d}", "score": i, "entry_price": 100} for i in range(25)]
    )
    capped = cap_ai_target_signals(signals_df, limit=20)

    assert len(capped) == 20
    assert int(capped["score"].min()) == 5
    assert int(capped["score"].max()) == 24


def test_cap_ai_target_signals_without_score_uses_head_fallback():
    signals_df = pd.DataFrame([{"ticker": f"{i:06d}"} for i in range(25)])
    capped = cap_ai_target_signals(signals_df, limit=20)

    assert len(capped) == 20
    assert capped.iloc[0]["ticker"] == "000000"
    assert capped.iloc[-1]["ticker"] == "000019"


def test_build_ai_batch_payload_maps_fields():
    signals_df = pd.DataFrame(
        [
            {
                "ticker": "000001",
                "name": "테스트주",
                "entry_price": 12345,
                "score": 77,
                "vcp_score": 15,
                "contraction_ratio": 0.45,
                "foreign_5d": 100,
                "inst_5d": 200,
            }
        ]
    )

    payload = build_ai_batch_payload(signals_df)
    assert len(payload) == 1
    assert payload[0]["ticker"] == "000001"
    assert payload[0]["current_price"] == 12345
    assert payload[0]["score"] == 77


def test_apply_ai_results_sets_fallback_when_missing():
    signals_df = pd.DataFrame(
        [
            {"ticker": "000001", "name": "A"},
            {"ticker": "000002", "name": "B"},
        ]
    )
    ai_results = {
        "000001": {
            "gemini_recommendation": {
                "action": "BUY",
                "confidence": 85,
                "reason": "추세 양호",
            }
        }
    }

    merged = apply_ai_results(signals_df, ai_results)
    row1 = merged[merged["ticker"] == "000001"].iloc[0]
    assert row1["ai_action"] == "BUY"
    assert int(row1["ai_confidence"]) == 85

    row2 = merged[merged["ticker"] == "000002"].iloc[0]
    assert row2["ai_action"] == "N/A"
    assert int(row2["ai_confidence"]) == 0
    assert row2["ai_reason"] == "분석 실패"


def test_apply_ai_results_preserves_existing_columns_and_row_count():
    signals_df = pd.DataFrame(
        [
            {"ticker": "000001", "name": "A", "score": 10},
            {"ticker": "000002", "name": "B", "score": 20},
        ]
    )
    ai_results = {"000001": {"gemini_recommendation": {"action": "HOLD", "confidence": 50, "reason": "중립"}}}

    merged = apply_ai_results(signals_df, ai_results)

    assert len(merged) == 2
    assert merged["score"].tolist() == [10, 20]
    assert merged.iloc[0]["ai_action"] == "HOLD"
    assert merged.iloc[1]["ai_action"] == "N/A"


def test_cap_ai_target_signals_handles_non_numeric_scores():
    signals_df = pd.DataFrame(
        [
            {"ticker": "000001", "score": "10"},
            {"ticker": "000002", "score": "not-number"},
            {"ticker": "000003", "score": "30"},
        ]
    )

    capped = cap_ai_target_signals(signals_df, limit=2)

    assert set(capped["ticker"].tolist()) == {"000001", "000003"}


def test_cap_ai_target_signals_uses_runtime_limit_when_limit_not_provided(monkeypatch):
    signals_df = pd.DataFrame([{"ticker": f"{i:06d}", "score": i} for i in range(5)])
    monkeypatch.setattr(
        ai_helpers_module,
        "resolve_vcp_signals_to_show",
        lambda **_kwargs: 2,
    )

    capped = cap_ai_target_signals(signals_df)

    assert len(capped) == 2
    assert capped["ticker"].tolist() == ["000004", "000003"]
