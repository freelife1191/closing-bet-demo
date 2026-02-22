#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Signal Tracker AI 분석 헬퍼.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import pandas as pd


def cap_ai_target_signals(signals_df: pd.DataFrame, limit: int = 20) -> pd.DataFrame:
    """AI 분석 대상을 score 기준 상위 N개로 제한."""
    if len(signals_df) <= limit:
        return signals_df
    if "score" not in signals_df.columns:
        return signals_df.head(limit)
    scores = pd.to_numeric(signals_df["score"], errors="coerce").fillna(0)
    top_indices = scores.nlargest(limit).index
    return signals_df.loc[top_indices]


def build_ai_batch_payload(signals_df: pd.DataFrame) -> list[dict[str, Any]]:
    """AI 배치 분석 입력 payload를 생성."""
    payload: list[dict[str, Any]] = []
    for row in signals_df.itertuples(index=False):
        payload.append(
            {
                "ticker": getattr(row, "ticker", None),
                "name": getattr(row, "name", None),
                "current_price": getattr(row, "entry_price", None),
                "score": getattr(row, "score", 0),
                "vcp_score": getattr(row, "vcp_score", 0),
                "contraction_ratio": getattr(row, "contraction_ratio", 0),
                "foreign_5d": getattr(row, "foreign_5d", None),
                "inst_5d": getattr(row, "inst_5d", None),
            }
        )
    return payload


def apply_ai_results(
    signals_df: pd.DataFrame,
    ai_results: Mapping[str, dict[str, Any]],
) -> pd.DataFrame:
    """AI 분석 결과를 시그널 프레임에 병합."""
    if signals_df.empty:
        return signals_df.copy()

    result = signals_df.copy()
    if "ticker" in result.columns:
        ticker_series = result["ticker"]
    else:
        ticker_series = pd.Series([None] * len(result), index=result.index)

    actions: list[Any] = []
    confidences: list[Any] = []
    reasons: list[Any] = []

    for ticker in ticker_series:
        ai_payload = ai_results.get(ticker, {}) if isinstance(ai_results, Mapping) else {}
        gemini = (
            ai_payload.get("gemini_recommendation")
            if isinstance(ai_payload, Mapping)
            else None
        )

        if isinstance(gemini, Mapping):
            actions.append(gemini.get("action"))
            confidences.append(gemini.get("confidence"))
            reasons.append(gemini.get("reason"))
        else:
            actions.append("N/A")
            confidences.append(0)
            reasons.append("분석 실패")

    result["ai_action"] = actions
    result["ai_confidence"] = confidences
    result["ai_reason"] = reasons
    return result
