#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KRX collector data mixin 리팩토링 테스트
"""

from __future__ import annotations

import sys
import types

import pandas as pd

from engine.collectors.krx import KRXCollector
from engine.collectors.krx_data_mixin import KRXCollectorDataMixin


class _DummyCollector(KRXCollectorDataMixin):
    def __init__(self):
        self.name_calls: list[str] = []

    def _get_stock_name(self, ticker: str) -> str:
        normalized = str(ticker).zfill(6)
        self.name_calls.append(normalized)
        return f"NAME-{normalized}"

    def _get_sector(self, ticker: str) -> str:
        return "테스트"

    def _get_latest_market_date(self) -> str:  # pragma: no cover - 인터페이스 충족용
        return "20260221"


class _FakeStock:
    def __init__(self):
        self.calls = 0

    def get_market_ticker_name(self, ticker: str) -> str:
        self.calls += 1
        return "삼성전자"


def test_process_ohlcv_dataframe_uses_internal_stock_name_lookup(monkeypatch):
    class _FailingStock:
        def get_market_ticker_name(self, _ticker):
            raise AssertionError("_process_ohlcv_dataframe는 pykrx 직접 조회를 사용하면 안 됩니다.")

    fake_pykrx = types.ModuleType("pykrx")
    fake_pykrx.stock = _FailingStock()
    monkeypatch.setitem(sys.modules, "pykrx", fake_pykrx)

    collector = _DummyCollector()

    df = pd.DataFrame(
        {
            "종가": [55_000, 65_000],
            "거래대금": [120_000_000_000, 110_000_000_000],
            "등락률": [3.2, 5.1],
            "거래량": [1_000_000, 1_200_000],
            "시가총액": [1_000_000_000_000, 900_000_000_000],
        },
        index=["005930", "000660"],
    )

    result = collector._process_ohlcv_dataframe(df, market="KOSPI", top_n=1)

    assert len(result) == 1
    assert result[0].code == "000660"
    assert result[0].name == "NAME-000660"
    assert collector.name_calls == ["000660"]


def test_get_stock_name_caches_pykrx_lookup(monkeypatch):
    fake_stock = _FakeStock()
    fake_pykrx = types.ModuleType("pykrx")
    fake_pykrx.stock = fake_stock
    monkeypatch.setitem(sys.modules, "pykrx", fake_pykrx)

    collector = KRXCollector()

    name1 = collector._get_stock_name("5930")
    name2 = collector._get_stock_name("005930")

    assert name1 == "삼성전자"
    assert name2 == "삼성전자"
    assert fake_stock.calls == 1


def test_process_ohlcv_dataframe_handles_non_numeric_fields_gracefully():
    collector = _DummyCollector()
    df = pd.DataFrame(
        {
            "종가": ["65000"],
            "거래대금": ["120000000000"],
            "등락률": ["5.1"],
            "거래량": ["invalid"],
            "시가총액": ["invalid"],
        },
        index=["660"],
    )

    result = collector._process_ohlcv_dataframe(df, market="KOSPI", top_n=1)

    assert len(result) == 1
    assert result[0].code == "000660"
    assert result[0].volume == 0
    assert result[0].marcap == 0
