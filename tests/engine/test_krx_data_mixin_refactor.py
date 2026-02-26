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


def test_get_stock_name_caches_pykrx_lookup(monkeypatch, tmp_path):
    fake_stock = _FakeStock()
    fake_pykrx = types.ModuleType("pykrx")
    fake_pykrx.stock = fake_stock
    monkeypatch.setitem(sys.modules, "pykrx", fake_pykrx)
    monkeypatch.setattr(
        KRXCollector,
        "_stock_name_sqlite_context",
        classmethod(
            lambda cls, ticker: (
                str(tmp_path / f"{str(ticker).zfill(6)}.snapshot"),
                (41, 41),
            )
        ),
    )

    collector = KRXCollector()
    collector._stock_name_cache.clear()

    name1 = collector._get_stock_name("5930")
    name2 = collector._get_stock_name("005930")

    assert name1 == "삼성전자"
    assert name2 == "삼성전자"
    assert fake_stock.calls == 1


def test_get_stock_name_reuses_sqlite_snapshot_after_memory_clear(monkeypatch, tmp_path):
    collector = KRXCollector()
    collector._stock_name_cache.clear()

    monkeypatch.setattr(
        KRXCollector,
        "_stock_name_sqlite_context",
        classmethod(
            lambda cls, ticker: (
                str(tmp_path / f"{str(ticker).zfill(6)}.snapshot"),
                (91, 91),
            )
        ),
    )

    calls = {"count": 0}

    def _fake_get_market_ticker_name(_ticker: str) -> str:
        calls["count"] += 1
        return "삼성전자"

    fake_pykrx = types.ModuleType("pykrx")
    fake_pykrx.stock = types.SimpleNamespace(get_market_ticker_name=_fake_get_market_ticker_name)
    monkeypatch.setitem(sys.modules, "pykrx", fake_pykrx)

    first = collector._get_stock_name("5930")
    assert first == "삼성전자"
    assert calls["count"] == 1

    collector._stock_name_cache.clear()
    fake_pykrx.stock.get_market_ticker_name = lambda _ticker: (_ for _ in ()).throw(
        AssertionError("SQLite snapshot hit이면 pykrx 재조회가 발생하면 안 됩니다.")
    )

    second = collector._get_stock_name("005930")
    assert second == "삼성전자"
    assert calls["count"] == 1


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


def test_get_latest_market_date_reuses_sqlite_snapshot_after_memory_clear(monkeypatch, tmp_path):
    collector = KRXCollector()
    KRXCollector.clear_latest_market_date_cache()

    monkeypatch.setattr(
        KRXCollector,
        "_latest_market_date_cache_token",
        classmethod(lambda cls, _now: "20260226:postclose"),
    )
    monkeypatch.setattr(
        KRXCollector,
        "_latest_market_date_sqlite_context",
        classmethod(
            lambda cls, cache_token: (
                str(tmp_path / f"{cache_token}.snapshot"),
                (81, 81),
            )
        ),
    )

    calls = {"count": 0}

    def _fake_get_index_ohlcv_by_date(*_args, **_kwargs):
        calls["count"] += 1
        index = pd.to_datetime(["2026-02-25"])
        return pd.DataFrame({"종가": [2600]}, index=index)

    fake_pykrx = types.ModuleType("pykrx")
    fake_pykrx.stock = types.SimpleNamespace(get_index_ohlcv_by_date=_fake_get_index_ohlcv_by_date)
    monkeypatch.setitem(sys.modules, "pykrx", fake_pykrx)

    first = collector._get_latest_market_date()
    assert first == "20260225"
    assert calls["count"] == 1

    KRXCollector.clear_latest_market_date_cache()
    fake_pykrx.stock.get_index_ohlcv_by_date = lambda *_a, **_k: (_ for _ in ()).throw(
        AssertionError("SQLite snapshot hit이면 pykrx 재조회가 발생하면 안 됩니다.")
    )

    second = collector._get_latest_market_date()
    assert second == "20260225"
    assert calls["count"] == 1
