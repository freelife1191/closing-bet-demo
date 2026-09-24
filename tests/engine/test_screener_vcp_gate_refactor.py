#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SmartMoneyScreener VCP 게이트 회귀 테스트.
"""

from __future__ import annotations

from types import SimpleNamespace

import pandas as pd
import pytest

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

    # 전 종목 실패는 [VCP-053] 부터 빈 결과가 아니라 예외다. 예산 소모는 그대로 확인한다
    with pytest.raises(RuntimeError, match="분석 가능한 종목"):
        screener.run_screening(max_stocks=2)

    assert len(analyzed) == 2


def test_run_screening_keeps_vcp_stock_below_composite_score(monkeypatch):
    """[VCP-032] is_vcp=True 면 합산 점수가 낮아도 결과에 남고, 점수는 정렬에만 쓴다."""
    screener = object.__new__(SmartMoneyScreener)
    screener.stocks_df = pd.DataFrame(
        [
            {"ticker": "000001", "name": "수급약한VCP", "market": "KOSPI"},
            {"ticker": "000002", "name": "수급중간VCP", "market": "KOSDAQ"},
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
        return {
            "ticker": stock["ticker"],
            "name": stock["name"],
            "score": 12 if stock["ticker"] == "000001" else 45,
            "market": stock["market"],
            "is_vcp": True,
        }

    monkeypatch.setattr(SmartMoneyScreener, "_analyze_stock", _fake_analyze)

    result = screener.run_screening(max_stocks=10)

    assert result["ticker"].tolist() == ["000002", "000001"]


def _gate_screener(monkeypatch, *, prices_df, analyze=None):
    screener = object.__new__(SmartMoneyScreener)
    screener.stocks_df = pd.DataFrame([{"ticker": "000001", "name": "종목", "market": "KOSPI"}])
    screener.prices_df = prices_df
    screener.inst_df = pd.DataFrame()
    screener.target_date = None
    screener.market_gate = SimpleNamespace(
        analyze=analyze or (lambda: {"status": "중립", "is_gate_open": True})
    )
    monkeypatch.setattr(SmartMoneyScreener, "_load_data", lambda _self: None)
    return screener


def test_run_screening_raises_when_market_gate_fails(monkeypatch):
    """[VCP-049] 실패를 빈 결과로 돌려주면 호출자가 「시그널 없음」으로 보고 그 날짜 행을 지운다."""
    def _boom():
        raise RuntimeError("gate down")

    screener = _gate_screener(monkeypatch, prices_df=pd.DataFrame([{"ticker": "000001"}]), analyze=_boom)
    with pytest.raises(RuntimeError, match="gate down"):
        screener.run_screening(max_stocks=10)


def test_run_screening_raises_when_prices_are_empty(monkeypatch):
    """[VCP-049] 가격 파일이 없으면 로더가 빈 프레임을 준다. 이것도 0건이 아니라 실패다."""
    screener = _gate_screener(monkeypatch, prices_df=pd.DataFrame())
    with pytest.raises(RuntimeError):
        screener.run_screening(max_stocks=10)


def test_run_screening_returns_empty_when_no_stock_passes(monkeypatch):
    """[VCP-049] 조건 충족 종목이 실제로 없으면 종전처럼 빈 프레임이다."""
    screener = _gate_screener(monkeypatch, prices_df=pd.DataFrame([{"ticker": "000001"}]))
    monkeypatch.setattr(
        SmartMoneyScreener, "_analyze_stock", lambda _self, stock: {**stock, "score": 50, "is_vcp": False}
    )
    assert screener.run_screening(max_stocks=10).empty


def test_run_screening_raises_when_no_candidate_can_be_analyzed(monkeypatch):
    """[VCP-053] 가격이 20행 미만이라 전 종목이 분석 전에 빠지면 0건이 아니라 실패다."""
    screener = _gate_screener(monkeypatch, prices_df=pd.DataFrame([{"ticker": "000001"}]))
    screener._target_datetime = None
    screener._prices_by_ticker = {"000001": pd.DataFrame({"close": [100.0] * 5})}
    with pytest.raises(RuntimeError, match="분석 가능한 종목"):
        screener.run_screening(max_stocks=10)


def test_run_screening_raises_when_vcp_detection_fails_for_all(monkeypatch):
    """[VCP-053] VCP 판정 예외를 is_vcp=False 로 삼키면 체계적 오류가 「시그널 없음」이 된다."""
    screener = _gate_screener(monkeypatch, prices_df=pd.DataFrame([{"ticker": "000001"}]))
    screener._target_datetime = None
    screener._prices_by_ticker = {"000001": _frame_with_high([110.0] * 30)}
    monkeypatch.setattr(SmartMoneyScreener, "_calculate_supply_score", lambda _self, _ticker: {"score": 0})
    called = []

    def _boom(*_args, **_kwargs):
        called.append(True)
        raise ValueError("vcp broken")

    monkeypatch.setattr("engine.vcp.detect_vcp_pattern", _boom)
    with pytest.raises(RuntimeError, match="분석 가능한 종목"):
        screener.run_screening(max_stocks=10)
    # 유효 행 검사([VCP-056])를 지나 판정까지 갔어야 이 테스트가 판정 예외를 검사한다
    assert called


def _frame_with_high(high):
    return pd.DataFrame({"high": high, "low": [90.0] * 30, "close": [100.0] * 30, "volume": [1_000] * 30})


def test_run_screening_raises_when_all_high_values_are_missing(monkeypatch):
    """[VCP-056] 행이 20개 넘어도 high 가 전부 비면 판정이 「무효 프레임」 결과로 끝나 분석 수에 들어갔다."""
    screener = _gate_screener(monkeypatch, prices_df=pd.DataFrame([{"ticker": "000001"}]))
    screener._target_datetime = None
    screener._prices_by_ticker = {"000001": _frame_with_high([float("nan")] * 30)}
    monkeypatch.setattr(SmartMoneyScreener, "_calculate_supply_score", lambda _self, _ticker: {"score": 0})
    with pytest.raises(RuntimeError, match="분석 가능한 종목"):
        screener.run_screening(max_stocks=10)


def test_run_screening_analyzes_when_enough_rows_remain_valid(monkeypatch):
    """[VCP-056] 일부 행만 비고 유효 행이 20 이상이면 종전처럼 분석한다."""
    screener = _gate_screener(monkeypatch, prices_df=pd.DataFrame([{"ticker": "000001"}]))
    screener._target_datetime = None
    screener._prices_by_ticker = {"000001": _frame_with_high([float("nan")] * 10 + [110.0] * 20)}
    monkeypatch.setattr(SmartMoneyScreener, "_calculate_supply_score", lambda _self, _ticker: {"score": 0})
    assert screener.run_screening(max_stocks=10).empty
