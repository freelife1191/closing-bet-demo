#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VCP detector 회귀 테스트.
"""

from __future__ import annotations

from datetime import datetime, timedelta
import logging

import pandas as pd

from engine.models import ChartData, StockData
from engine.phases_phase1_helpers import analyze_vcp_for_stock
from engine.vcp import detect_vcp_pattern


def _build_vcp_frame() -> pd.DataFrame:
    rows: list[dict[str, float | str]] = []
    base_date = datetime(2026, 1, 1)

    for index in range(60):
        if index < 40:
            high = 104.0
            low = 96.0
            close = 100.0
            volume = 2_000
        elif index < 55:
            high = 102.0
            low = 98.0
            close = 100.0
            volume = 2_000
        else:
            high = 101.0
            low = 100.4
            close = 100.8
            volume = 600

        rows.append(
            {
                "date": (base_date + timedelta(days=index)).strftime("%Y-%m-%d"),
                "open": close,
                "high": high,
                "low": low,
                "close": close,
                "volume": volume,
            }
        )

    rows[30]["high"] = 105.0
    rows[-1]["close"] = 101.2
    rows[-1]["high"] = 101.4
    rows[-1]["low"] = 100.9

    return pd.DataFrame(rows)


def test_detect_vcp_pattern_recognizes_contraction_case():
    frame = _build_vcp_frame()
    result = detect_vcp_pattern(frame, "005930", "테스트")

    assert result.is_vcp is True
    assert result.vcp_score >= 50
    assert result.contraction_ratio <= 0.7
    assert result.entry_price > 0


def test_detect_vcp_pattern_rejects_when_price_is_too_low():
    frame = _build_vcp_frame()
    frame.loc[len(frame) - 1, "close"] = 80.0
    frame.loc[len(frame) - 1, "open"] = 80.0
    frame.loc[len(frame) - 1, "high"] = 81.0
    frame.loc[len(frame) - 1, "low"] = 79.0

    result = detect_vcp_pattern(frame, "005930", "테스트")

    assert result.is_vcp is False
    assert "Price too low" in result.pattern_desc


def test_phase1_helper_populates_stock_vcp_fields():
    frame = _build_vcp_frame()
    charts = ChartData(
        opens=frame["open"].tolist(),
        highs=frame["high"].tolist(),
        lows=frame["low"].tolist(),
        closes=frame["close"].tolist(),
        volumes=frame["volume"].astype(int).tolist(),
        dates=[value.replace("-", "") for value in frame["date"].tolist()],
    )
    stock = StockData(
        code="005930",
        name="테스트",
        market="KOSPI",
        close=float(frame["close"].iloc[-1]),
    )

    vcp_data = analyze_vcp_for_stock(stock=stock, charts=charts, logger=logging.getLogger(__name__))

    assert isinstance(vcp_data, dict)
    assert vcp_data["score"] > 0
    assert vcp_data["ratio"] <= 0.7
    assert hasattr(stock, "vcp_score")
    assert hasattr(stock, "contraction_ratio")
