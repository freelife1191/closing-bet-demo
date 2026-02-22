#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Screener result builder helpers.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any


def build_screening_result(
    *,
    stock: dict[str, Any],
    total_score: float,
    supply_result: dict[str, Any],
    entry_price: float,
    contraction_ratio: float,
    vcp_score: int,
    first_close: float,
    last_close: float,
) -> dict[str, Any]:
    """스크리닝 종목 결과 payload를 구성한다."""
    change_pct = 0 if first_close == 0 else (last_close - first_close) / first_close * 100
    return {
        "ticker": stock["ticker"],
        "name": stock["name"],
        "score": total_score,
        "foreign_net_5d": supply_result.get("foreign_5d", 0),
        "inst_net_5d": supply_result.get("inst_5d", 0),
        "foreign_net_1d": supply_result.get("foreign_1d", 0),
        "inst_net_1d": supply_result.get("inst_1d", 0),
        "market": stock["market"],
        "entry_price": entry_price,
        "current_price": last_close,
        "change_pct": change_pct,
        "market_status": "UNKNOWN",
        "contraction_ratio": contraction_ratio,
        "vcp_score": vcp_score,
    }


def build_signal_item(row: Any, signal_date: str | None) -> dict[str, Any]:
    """스크리닝 결과 row를 시그널 payload로 변환한다."""
    return {
        "ticker": str(getattr(row, "ticker", "")).zfill(6),
        "name": getattr(row, "name", ""),
        "signal_date": signal_date or datetime.now().strftime("%Y-%m-%d"),
        "entry_price": getattr(row, "entry_price", 0),
        "status": "OPEN",
        "score": getattr(row, "score", 0),
        "foreign_5d": getattr(row, "foreign_net_5d", 0),
        "inst_5d": getattr(row, "inst_net_5d", 0),
        "market": getattr(row, "market", "UNKNOWN"),
        "change_pct": getattr(row, "change_pct", 0),
        "contraction_ratio": getattr(row, "contraction_ratio", 0),
    }


__all__ = ["build_screening_result", "build_signal_item"]

