#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Screener supply score helper functions.
"""

from __future__ import annotations

from typing import Any, Callable


def calculate_supply_score_with_toss(
    *,
    ticker: str,
    toss_collector: Any,
    fallback_fn: Callable[[str], dict[str, int]],
    score_supply_from_toss_trend_fn: Callable[[dict[str, Any] | None], dict[str, int]],
) -> dict[str, int]:
    """Toss 수급 조회를 시도하고 실패 시 CSV fallback을 수행한다."""
    try:
        trend_data = toss_collector.get_investor_trend(ticker, days=5)
        if not trend_data:
            return fallback_fn(ticker)
        return score_supply_from_toss_trend_fn(trend_data)
    except Exception:
        return fallback_fn(ticker)


def calculate_supply_score_from_csv(
    *,
    ticker: str,
    inst_by_ticker: dict[str, Any],
    target_datetime: Any,
    score_supply_from_csv_fn: Callable[[Any, Any], dict[str, int]],
) -> dict[str, int]:
    """CSV 기반 수급 점수를 계산한다."""
    try:
        if not inst_by_ticker:
            return {"score": 0, "foreign_1d": 0, "inst_1d": 0}

        ticker_inst = inst_by_ticker.get(ticker)
        return score_supply_from_csv_fn(ticker_inst=ticker_inst, target_datetime=target_datetime)
    except Exception:
        return {"score": 0, "foreign_1d": 0, "inst_1d": 0}


__all__ = ["calculate_supply_score_with_toss", "calculate_supply_score_from_csv"]

