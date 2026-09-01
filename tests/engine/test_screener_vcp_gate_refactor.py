#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SmartMoneyScreener VCP 게이트 회귀 테스트.
"""

from __future__ import annotations

from types import SimpleNamespace

import pandas as pd

from engine.screener import SmartMoneyScreener


def test_run_screening_requires_vcp_pattern(monkeypatch):
    """총점이 높아도 is_vcp=False면 VCP 결과에서 제외한다."""
    screener = object.__new__(SmartMoneyScreener)
    screener.stocks_df = pd.DataFrame(
        [
            {"ticker": "000001", "name": "수급만강함", "market": "KOSPI"},
            {"ticker": "000002", "name": "진짜VCP", "market": "KOSPI"},
        ]
    )
    screener.prices_df = pd.DataFrame([{"ticker": "000001"}])
    screener.inst_df = pd.DataFrame()
    screener.target_date = None
    screener.market_gate = SimpleNamespace(
        analyze=lambda: {"status": "중립", "is_gate_open": True}
    )

    monkeypatch.setattr(SmartMoneyScreener, "_load_data", lambda _self: None)

    def _fake_analyze(_self, stock):
        ticker = stock["ticker"]
        if ticker == "000001":
            return {
                "ticker": ticker,
                "name": stock["name"],
                "score": 95,
                "market": stock["market"],
                "is_vcp": False,
            }
        return {
            "ticker": ticker,
            "name": stock["name"],
            "score": 61,
            "market": stock["market"],
            "is_vcp": True,
        }

    monkeypatch.setattr(SmartMoneyScreener, "_analyze_stock", _fake_analyze)

    result = screener.run_screening(max_stocks=10)

    assert result["ticker"].tolist() == ["000002"]


def test_run_screening_counts_failed_stocks_against_max_stocks(monkeypatch):
    """분석 중 예외가 난 종목도 max_stocks 예산을 소모해야 한다."""
    screener = object.__new__(SmartMoneyScreener)
    screener.stocks_df = pd.DataFrame(
        [{"ticker": f"00000{i}", "name": f"종목{i}", "market": "KOSPI"} for i in range(1, 6)]
    )
    screener.prices_df = pd.DataFrame([{"ticker": "000001"}])
    screener.inst_df = pd.DataFrame()
    screener.target_date = None
    screener.market_gate = SimpleNamespace(
        analyze=lambda: {"status": "중립", "is_gate_open": True}
    )

    monkeypatch.setattr(SmartMoneyScreener, "_load_data", lambda _self: None)

    analyzed = []

    def _always_raises(_self, stock):
        analyzed.append(stock["ticker"])
        raise RuntimeError("분석 실패")

    monkeypatch.setattr(SmartMoneyScreener, "_analyze_stock", _always_raises)

    result = screener.run_screening(max_stocks=2)

    assert result.empty
    assert len(analyzed) == 2
