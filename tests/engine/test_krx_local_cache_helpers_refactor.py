#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KRX 로컬 CSV 캐시 리팩토링 테스트
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
import time
import types

import pandas as pd

from engine.collectors.krx_data_mixin import KRXCollectorDataMixin
import engine.collectors.krx_local_data_mixin as krx_local_data_mixin
from engine.collectors.krx_local_cache_helpers import CsvCacheEntry, read_csv_cached


class _DummyCollector(KRXCollectorDataMixin):
    def __init__(self, data_dir: str):
        self._local_data_dir = data_dir

    def _get_latest_market_date(self) -> str:  # pragma: no cover - 인터페이스 충족용
        return "20260221"

    def _get_sector(self, ticker: str) -> str:  # pragma: no cover - 인터페이스 충족용
        return "테스트"

    def _get_stock_name(self, ticker: str) -> str:  # pragma: no cover - 인터페이스 충족용
        return ticker


def test_read_csv_cached_uses_cache_and_invalidates_on_mtime(monkeypatch, tmp_path):
    csv_path = tmp_path / "sample.csv"
    pd.DataFrame([{"a": 1}, {"a": 2}]).to_csv(csv_path, index=False)

    cache: dict[str, CsvCacheEntry] = {}
    calls = {"count": 0}
    original_read_csv = pd.read_csv

    def _counting_read_csv(*args, **kwargs):
        calls["count"] += 1
        return original_read_csv(*args, **kwargs)

    monkeypatch.setattr(pd, "read_csv", _counting_read_csv)

    first = read_csv_cached(
        cache=cache,
        path=str(csv_path),
        cache_key="default",
        logger=logging.getLogger(__name__),
    )
    second = read_csv_cached(
        cache=cache,
        path=str(csv_path),
        cache_key="default",
        logger=logging.getLogger(__name__),
    )

    assert calls["count"] == 1
    assert len(first) == 2
    assert len(second) == 2

    pd.DataFrame([{"a": 1}, {"a": 2}, {"a": 3}]).to_csv(csv_path, index=False)
    now = time.time()
    os.utime(csv_path, (now + 2, now + 2))

    third = read_csv_cached(
        cache=cache,
        path=str(csv_path),
        cache_key="default",
        logger=logging.getLogger(__name__),
    )

    assert calls["count"] == 2
    assert len(third) == 3


def test_load_from_local_csv_reuses_cached_files(monkeypatch, tmp_path):
    pd.DataFrame(
        [
            {
                "ticker": "000001",
                "date": "2026-02-21",
                "open": 1000,
                "close": 1100,
                "volume": 2_000_000,
            }
        ]
    ).to_csv(tmp_path / "daily_prices.csv", index=False)

    pd.DataFrame(
        [
            {"ticker": "000001", "name": "테스트", "market": "KOSPI"},
        ]
    ).to_csv(tmp_path / "korean_stocks_list.csv", index=False)

    collector = _DummyCollector(str(tmp_path))
    calls = {"count": 0}
    original_read_csv = pd.read_csv

    def _counting_read_csv(*args, **kwargs):
        calls["count"] += 1
        return original_read_csv(*args, **kwargs)

    monkeypatch.setattr(pd, "read_csv", _counting_read_csv)

    first = collector._load_from_local_csv("KOSPI", top_n=5, target_date="20260221")
    second = collector._load_from_local_csv("KOSPI", top_n=5, target_date="20260221")

    assert len(first) == 1
    assert len(second) == 1
    assert calls["count"] == 2  # daily_prices.csv + korean_stocks_list.csv 최초 1회씩만 로드


def test_load_from_local_csv_converts_cached_date_column_once(monkeypatch, tmp_path):
    pd.DataFrame(
        [
            {
                "ticker": "000001",
                "date": "2026-02-21",
                "open": 1000,
                "close": 1100,
                "volume": 2_000_000,
            }
        ]
    ).to_csv(tmp_path / "daily_prices.csv", index=False)
    pd.DataFrame(
        [{"ticker": "000001", "name": "테스트", "market": "KOSPI"}]
    ).to_csv(tmp_path / "korean_stocks_list.csv", index=False)

    collector = _DummyCollector(str(tmp_path))
    calls = {"count": 0}
    original_to_datetime = krx_local_data_mixin.pd.to_datetime

    def _counted_to_datetime(*args, **kwargs):
        calls["count"] += 1
        return original_to_datetime(*args, **kwargs)

    monkeypatch.setattr(krx_local_data_mixin.pd, "to_datetime", _counted_to_datetime)

    _ = collector._load_from_local_csv("KOSPI", top_n=5, target_date=None)
    _ = collector._load_from_local_csv("KOSPI", top_n=5, target_date=None)

    assert calls["count"] == 1


def test_load_from_local_csv_reuses_stock_lookup_map_without_repadding(monkeypatch, tmp_path):
    pd.DataFrame(
        [
            {
                "ticker": "000001",
                "date": "2026-02-21",
                "open": 1000,
                "close": 1100,
                "volume": 2_000_000,
            }
        ]
    ).to_csv(tmp_path / "daily_prices.csv", index=False)
    pd.DataFrame(
        [{"ticker": "000001", "name": "테스트", "market": "KOSPI"}]
    ).to_csv(tmp_path / "korean_stocks_list.csv", index=False)

    collector = _DummyCollector(str(tmp_path))
    calls = {"count": 0}
    original_get_ticker_series = krx_local_data_mixin._get_ticker_padded_series

    def _counted_get_ticker_series(df):
        calls["count"] += 1
        return original_get_ticker_series(df)

    monkeypatch.setattr(
        krx_local_data_mixin,
        "_get_ticker_padded_series",
        _counted_get_ticker_series,
    )

    _ = collector._load_from_local_csv("KOSPI", top_n=5, target_date=None)
    _ = collector._load_from_local_csv("KOSPI", top_n=5, target_date=None)

    assert calls["count"] == 3


def test_load_from_local_csv_invalidates_stock_lookup_map_when_file_changes(tmp_path):
    pd.DataFrame(
        [
            {
                "ticker": "000001",
                "date": "2026-02-21",
                "open": 1000,
                "close": 1100,
                "volume": 2_000_000,
            }
        ]
    ).to_csv(tmp_path / "daily_prices.csv", index=False)

    stocks_path = tmp_path / "korean_stocks_list.csv"
    pd.DataFrame(
        [{"ticker": "000001", "name": "테스트1", "market": "KOSPI"}]
    ).to_csv(stocks_path, index=False)

    collector = _DummyCollector(str(tmp_path))
    first = collector._load_from_local_csv("KOSPI", top_n=5, target_date="20260221")
    assert len(first) == 1
    assert first[0].name == "테스트1"

    pd.DataFrame(
        [{"ticker": "000001", "name": "테스트2", "market": "KOSPI"}]
    ).to_csv(stocks_path, index=False)
    stat = stocks_path.stat()
    os.utime(stocks_path, ns=(stat.st_mtime_ns + 10_000_000, stat.st_mtime_ns + 10_000_000))

    second = collector._load_from_local_csv("KOSPI", top_n=5, target_date="20260221")
    assert len(second) == 1
    assert second[0].name == "테스트2"


def test_get_chart_data_fallback_reads_minimum_columns(monkeypatch, tmp_path):
    fake_pykrx = types.ModuleType("pykrx")
    fake_pykrx.stock = types.SimpleNamespace(get_market_ohlcv_by_date=lambda *_a, **_k: pd.DataFrame())
    monkeypatch.setitem(sys.modules, "pykrx", fake_pykrx)

    collector = _DummyCollector(str(tmp_path))
    captured: dict[str, object] = {}

    def _fake_read_local_csv(filename: str, *, cache_key: str, **kwargs):
        captured["filename"] = filename
        captured["cache_key"] = cache_key
        captured["usecols"] = kwargs.get("usecols")
        return pd.DataFrame(
            [
                {
                    "ticker": "005930",
                    "date": "2026-02-20",
                    "open": 100,
                    "high": 110,
                    "low": 90,
                    "close": 105,
                    "volume": 1000,
                }
            ]
        )

    monkeypatch.setattr(collector, "_read_local_csv", _fake_read_local_csv)

    chart = asyncio.run(collector.get_chart_data("005930", 30))

    assert chart is not None
    assert captured["filename"] == "daily_prices.csv"
    assert captured["cache_key"] == "daily_prices_chart"
    assert captured["usecols"] == ["ticker", "date", "open", "high", "low", "close", "volume"]


def test_get_supply_data_fallback_reads_minimum_columns(monkeypatch, tmp_path):
    fake_pykrx = types.ModuleType("pykrx")
    fake_pykrx.stock = types.SimpleNamespace(get_market_trading_value_by_date=lambda *_a, **_k: pd.DataFrame())
    monkeypatch.setitem(sys.modules, "pykrx", fake_pykrx)

    collector = _DummyCollector(str(tmp_path))
    captured: dict[str, object] = {}

    def _fake_read_local_csv(filename: str, *, cache_key: str, **kwargs):
        captured["filename"] = filename
        captured["cache_key"] = cache_key
        captured["usecols"] = kwargs.get("usecols")
        return pd.DataFrame(
            [
                {"ticker": "005930", "date": "2026-02-20", "foreign_buy": 10, "inst_buy": 20},
                {"ticker": "005930", "date": "2026-02-21", "foreign_buy": 11, "inst_buy": 21},
                {"ticker": "005930", "date": "2026-02-22", "foreign_buy": 12, "inst_buy": 22},
                {"ticker": "005930", "date": "2026-02-23", "foreign_buy": 13, "inst_buy": 23},
                {"ticker": "005930", "date": "2026-02-24", "foreign_buy": 14, "inst_buy": 24},
            ]
        )

    monkeypatch.setattr(collector, "_read_local_csv", _fake_read_local_csv)

    supply = asyncio.run(collector.get_supply_data("005930"))

    assert supply is not None
    assert supply.foreign_buy_5d == 60
    assert supply.inst_buy_5d == 110
    assert captured["filename"] == "all_institutional_trend_data.csv"
    assert captured["cache_key"] == "institutional_trend_supply"
    assert captured["usecols"] == ["ticker", "date", "foreign_buy", "inst_buy"]
