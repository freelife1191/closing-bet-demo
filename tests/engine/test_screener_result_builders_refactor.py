#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Screener result builder 분해 회귀 테스트
"""

from __future__ import annotations

from engine.screener_result_builders import build_screening_result, build_signal_item


def test_build_screening_result_calculates_change_pct_and_maps_fields():
    result = build_screening_result(
        stock={"ticker": "005930", "name": "삼성전자", "market": "KOSPI"},
        total_score=88.0,
        supply_result={"foreign_5d": 10, "inst_5d": 20, "foreign_1d": 3, "inst_1d": 4},
        entry_price=70000,
        contraction_ratio=0.55,
        vcp_score=8,
        first_close=100.0,
        last_close=110.0,
    )

    assert result["ticker"] == "005930"
    assert result["score"] == 88.0
    assert result["change_pct"] == 10.0
    assert result["current_price"] == 110.0
    assert result["vcp_score"] == 8


def test_build_signal_item_uses_target_date_and_defaults():
    row = type(
        "Row",
        (),
        {
            "ticker": "5930",
            "name": "삼성전자",
            "entry_price": 70100,
            "score": 80,
            "foreign_net_5d": 11,
            "inst_net_5d": 12,
            "market": "KOSPI",
            "change_pct": 1.5,
            "contraction_ratio": 0.7,
        },
    )()

    signal = build_signal_item(row, "2026-02-21")
    assert signal["ticker"] == "005930"
    assert signal["signal_date"] == "2026-02-21"
    assert signal["foreign_5d"] == 11
    assert signal["inst_5d"] == 12

