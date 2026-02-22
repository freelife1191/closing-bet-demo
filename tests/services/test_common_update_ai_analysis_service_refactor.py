#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Common Update AI Analysis Service 리팩토링 테스트
"""

from __future__ import annotations

import pandas as pd

from services.common_update_ai_analysis_service import (
    _normalize_ai_target_dataframe,
    _resolve_ai_target_dataframe,
    _select_top_ai_targets,
)


def test_select_top_ai_targets_uses_score_order():
    df = pd.DataFrame(
        [
            {"ticker": "000001", "score": "10"},
            {"ticker": "000002", "score": "42"},
            {"ticker": "000003", "score": None},
            {"ticker": "000004", "score": "30"},
        ]
    )

    selected = _select_top_ai_targets(df, limit=2)

    assert selected["ticker"].tolist() == ["000002", "000004"]


def test_select_top_ai_targets_without_score_falls_back_to_head():
    df = pd.DataFrame([{"ticker": f"{i:06d}"} for i in range(5)])

    selected = _select_top_ai_targets(df, limit=3)

    assert selected["ticker"].tolist() == ["000000", "000001", "000002"]


def test_normalize_ai_target_dataframe_deduplicates_padded_ticker():
    df = pd.DataFrame(
        [
            {"ticker": "5930", "score": 10},
            {"ticker": "005930", "score": 7},
            {"ticker": "660", "score": 20},
        ]
    )

    normalized = _normalize_ai_target_dataframe(
        df,
        logger=type("L", (), {"warning": lambda *_a, **_k: None})(),
    )

    assert normalized["ticker"].tolist() == ["005930", "000660"]


def test_normalize_ai_target_dataframe_returns_empty_when_ticker_missing():
    df = pd.DataFrame([{"code": "005930"}])
    warnings: list[str] = []

    logger = type(
        "L",
        (),
        {"warning": lambda _self, message: warnings.append(str(message))},
    )()

    normalized = _normalize_ai_target_dataframe(df, logger=logger)

    assert normalized.empty
    assert warnings


def test_resolve_ai_target_dataframe_loads_minimum_columns_from_signal_file(tmp_path):
    signals_path = tmp_path / "signals_log.csv"
    signals_path.write_text(
        "signal_date,ticker,score,extra\n"
        "2026-02-20,5930,10,unused\n"
        "2026-02-21,660,30,unused\n",
        encoding="utf-8",
    )

    target_df, analysis_date = _resolve_ai_target_dataframe(
        target_date=None,
        selected_items=[],
        vcp_df=None,
        signals_path=str(signals_path),
        logger=type("L", (), {"info": lambda *_a, **_k: None})(),
    )

    assert analysis_date == "2026-02-21"
    assert set(target_df.columns) == {"signal_date", "ticker", "score"}
    assert len(target_df) == 1
