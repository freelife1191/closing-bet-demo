#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Legacy engine.collectors 모듈의 CSV fallback 리팩토링 테스트.
"""

from __future__ import annotations

import asyncio
import sys
import types

import pandas as pd

import engine.collectors as collectors_module


def test_load_from_local_csv_uses_shared_sqlite_backed_loader(monkeypatch, tmp_path):
    collector = collectors_module.KRXCollector(config=types.SimpleNamespace(min_change_pct=0.0))
    with collectors_module.KRXCollector._top_gainers_cache_lock:
        collectors_module.KRXCollector._top_gainers_cache.clear()
    collectors_module.KRXCollector.clear_stock_lookup_cache()
    calls: list[tuple[str, tuple[str, ...] | None]] = []

    daily_df = pd.DataFrame(
        [
            {
                "ticker": "000001",
                "date": "2026-02-21",
                "open": 1000,
                "close": 1100,
                "volume": 2_000_000,
            }
        ]
    )
    stocks_df = pd.DataFrame(
        [
            {"ticker": "000001", "name": "테스트", "market": "KOSPI"},
        ]
    )

    def _fake_signature(path: str):
        if path.endswith("daily_prices.csv"):
            return (1, 1)
        if path.endswith("korean_stocks_list.csv"):
            return (2, 2)
        return None

    def _fake_load_shared_csv_file(
        data_dir: str,
        filename: str,
        *,
        deep_copy: bool = True,
        usecols: list[str] | None = None,
        signature: tuple[int, int] | None = None,
    ) -> pd.DataFrame:
        del data_dir, deep_copy, signature
        calls.append((filename, tuple(usecols) if usecols is not None else None))
        if filename == "daily_prices.csv":
            return daily_df.copy()
        if filename == "korean_stocks_list.csv":
            return stocks_df.copy()
        return pd.DataFrame()

    monkeypatch.setattr(collectors_module, "_shared_file_signature", _fake_signature)
    monkeypatch.setattr(collectors_module, "_load_shared_csv_file", _fake_load_shared_csv_file)
    monkeypatch.setattr(
        collectors_module.KRXCollector,
        "_top_gainers_sqlite_context",
        classmethod(lambda cls, **_kwargs: (str(tmp_path / ".krx_collector_cache" / "case1.snapshot"), (11, 11))),
    )
    monkeypatch.setattr(
        collectors_module.KRXCollector,
        "_stock_lookup_sqlite_context",
        classmethod(
            lambda cls, **_kwargs: (
                str(tmp_path / ".krx_collector_cache" / "stock_lookup_case1.snapshot"),
                (13, 17),
            )
        ),
    )
    monkeypatch.setattr(
        pd,
        "read_csv",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("pd.read_csv should not run")
        ),
    )

    results = collector._load_from_local_csv("KOSPI", top_n=5, target_date="20260221")

    assert len(results) == 1
    assert results[0].code == "000001"
    assert results[0].name == "테스트"
    assert any(name == "daily_prices.csv" for name, _ in calls)
    assert any(name == "korean_stocks_list.csv" for name, _ in calls)


def test_load_from_local_csv_falls_back_when_usecols_mismatch(monkeypatch, tmp_path):
    collector = collectors_module.KRXCollector(config=types.SimpleNamespace(min_change_pct=0.0))
    with collectors_module.KRXCollector._top_gainers_cache_lock:
        collectors_module.KRXCollector._top_gainers_cache.clear()
    collectors_module.KRXCollector.clear_stock_lookup_cache()
    calls: list[tuple[str, tuple[str, ...] | None]] = []

    daily_df = pd.DataFrame(
        [
            {
                "ticker": "000001",
                "date": "2026-02-21",
                "open": 1000,
                "close": 1100,
                "volume": 2_000_000,
            }
        ]
    )
    stocks_df = pd.DataFrame(
        [
            {"ticker": "000001", "name": "테스트", "market": "KOSPI"},
        ]
    )

    def _fake_signature(path: str):
        if path.endswith("daily_prices.csv"):
            return (1, 1)
        if path.endswith("korean_stocks_list.csv"):
            return (2, 2)
        return None

    def _fake_load_shared_csv_file(
        data_dir: str,
        filename: str,
        *,
        deep_copy: bool = True,
        usecols: list[str] | None = None,
        signature: tuple[int, int] | None = None,
    ) -> pd.DataFrame:
        del data_dir, deep_copy, signature
        calls.append((filename, tuple(usecols) if usecols is not None else None))
        if usecols is not None:
            raise ValueError("Missing columns")
        if filename == "daily_prices.csv":
            return daily_df.copy()
        if filename == "korean_stocks_list.csv":
            return stocks_df.copy()
        return pd.DataFrame()

    monkeypatch.setattr(collectors_module, "_shared_file_signature", _fake_signature)
    monkeypatch.setattr(collectors_module, "_load_shared_csv_file", _fake_load_shared_csv_file)
    monkeypatch.setattr(
        collectors_module.KRXCollector,
        "_top_gainers_sqlite_context",
        classmethod(lambda cls, **_kwargs: (str(tmp_path / ".krx_collector_cache" / "case2.snapshot"), (22, 22))),
    )
    monkeypatch.setattr(
        collectors_module.KRXCollector,
        "_stock_lookup_sqlite_context",
        classmethod(
            lambda cls, **_kwargs: (
                str(tmp_path / ".krx_collector_cache" / "stock_lookup_case2.snapshot"),
                (23, 29),
            )
        ),
    )

    results = collector._load_from_local_csv("KOSPI", top_n=5, target_date="20260221")

    assert len(results) == 1
    daily_calls = [entry for entry in calls if entry[0] == "daily_prices.csv"]
    stocks_calls = [entry for entry in calls if entry[0] == "korean_stocks_list.csv"]
    assert daily_calls[0][1] is not None
    assert daily_calls[1][1] is None
    assert stocks_calls[0][1] is not None
    assert stocks_calls[1][1] is None


def test_get_latest_market_date_uses_memory_cache_before_pykrx(monkeypatch, tmp_path):
    collector = collectors_module.KRXCollector(config=types.SimpleNamespace(min_change_pct=0.0))
    collectors_module.KRXCollector.clear_latest_market_date_cache()

    monkeypatch.setattr(
        collectors_module.KRXCollector,
        "_latest_market_date_cache_token",
        classmethod(lambda cls, _now: "20260224:postclose"),
    )
    monkeypatch.setattr(
        collectors_module.KRXCollector,
        "_latest_market_date_sqlite_context",
        classmethod(
            lambda cls, cache_token: (
                str(tmp_path / ".krx_collector_cache" / f"{cache_token}.snapshot"),
                (1, 1),
            )
        ),
    )

    calls = {"count": 0}

    def _fake_get_index_ohlcv_by_date(*_args, **_kwargs):
        calls["count"] += 1
        index = pd.to_datetime(["2026-02-24"])
        return pd.DataFrame({"종가": [2600]}, index=index)

    fake_pykrx = types.ModuleType("pykrx")
    fake_pykrx.stock = types.SimpleNamespace(get_index_ohlcv_by_date=_fake_get_index_ohlcv_by_date)
    monkeypatch.setitem(sys.modules, "pykrx", fake_pykrx)

    first = collector._get_latest_market_date()
    second = collector._get_latest_market_date()

    assert first == "20260224"
    assert second == "20260224"
    assert calls["count"] == 1


def test_get_latest_market_date_reuses_sqlite_snapshot_after_memory_clear(monkeypatch, tmp_path):
    collector = collectors_module.KRXCollector(config=types.SimpleNamespace(min_change_pct=0.0))
    collectors_module.KRXCollector.clear_latest_market_date_cache()

    monkeypatch.setattr(
        collectors_module.KRXCollector,
        "_latest_market_date_cache_token",
        classmethod(lambda cls, _now: "20260224:postclose"),
    )
    monkeypatch.setattr(
        collectors_module.KRXCollector,
        "_latest_market_date_sqlite_context",
        classmethod(
            lambda cls, cache_token: (
                str(tmp_path / ".krx_collector_cache" / f"{cache_token}.snapshot"),
                (9, 9),
            )
        ),
    )

    calls = {"count": 0}

    def _fake_get_index_ohlcv_by_date(*_args, **_kwargs):
        calls["count"] += 1
        index = pd.to_datetime(["2026-02-24"])
        return pd.DataFrame({"종가": [2600]}, index=index)

    fake_pykrx = types.ModuleType("pykrx")
    fake_pykrx.stock = types.SimpleNamespace(get_index_ohlcv_by_date=_fake_get_index_ohlcv_by_date)
    monkeypatch.setitem(sys.modules, "pykrx", fake_pykrx)

    first = collector._get_latest_market_date()
    assert first == "20260224"
    assert calls["count"] == 1

    collectors_module.KRXCollector.clear_latest_market_date_cache()
    fake_pykrx.stock = types.SimpleNamespace(
        get_index_ohlcv_by_date=lambda *_a, **_k: (_ for _ in ()).throw(
            AssertionError("pykrx call should be skipped by sqlite snapshot")
        )
    )

    second = collector._get_latest_market_date()
    assert second == "20260224"
    assert calls["count"] == 1


def test_get_stock_name_reuses_sqlite_snapshot_after_memory_clear(monkeypatch, tmp_path):
    collector = collectors_module.KRXCollector(config=types.SimpleNamespace(min_change_pct=0.0))
    collector._stock_name_cache.clear()

    monkeypatch.setattr(
        collectors_module.KRXCollector,
        "_stock_name_sqlite_context",
        classmethod(
            lambda cls, ticker: (
                str(tmp_path / ".krx_collector_cache" / f"{str(ticker).zfill(6)}.snapshot"),
                (71, 72),
            )
        ),
    )

    calls = {"count": 0}

    def _fake_get_market_ticker_name(_ticker: str):
        calls["count"] += 1
        return "삼성전자"

    fake_stock_ns = types.SimpleNamespace(get_market_ticker_name=_fake_get_market_ticker_name)
    fake_pykrx = types.ModuleType("pykrx")
    fake_pykrx.stock = fake_stock_ns
    monkeypatch.setitem(sys.modules, "pykrx", fake_pykrx)

    first = collector._get_stock_name("5930")
    assert first == "삼성전자"
    assert calls["count"] == 1

    collector._stock_name_cache.clear()
    fake_stock_ns.get_market_ticker_name = lambda *_a, **_k: (_ for _ in ()).throw(
        AssertionError("pykrx call should be skipped by sqlite snapshot")
    )

    second = collector._get_stock_name("005930")
    assert second == "삼성전자"
    assert calls["count"] == 1


def test_latest_market_date_sqlite_context_uses_project_data_dir():
    cache_key, signature = collectors_module.KRXCollector._latest_market_date_sqlite_context(
        "20260225:postclose"
    )
    assert "data/.krx_collector_cache/latest_market_date__20260225:postclose.snapshot" in cache_key
    assert isinstance(signature, tuple)
    assert len(signature) == 2


def test_load_from_local_csv_reuses_top_gainers_sqlite_snapshot_after_memory_clear(monkeypatch, tmp_path):
    collector = collectors_module.KRXCollector(config=types.SimpleNamespace(min_change_pct=0.0))
    with collectors_module.KRXCollector._top_gainers_cache_lock:
        collectors_module.KRXCollector._top_gainers_cache.clear()
    collectors_module.KRXCollector.clear_stock_lookup_cache()

    daily_df = pd.DataFrame(
        [
            {
                "ticker": "000001",
                "date": "2026-02-21",
                "open": 1000,
                "close": 1100,
                "volume": 2_000_000,
                "change_pct": 5.0,
                "trading_value": 2_200_000_000,
            }
        ]
    )
    stocks_df = pd.DataFrame([{"ticker": "000001", "name": "테스트", "market": "KOSPI"}])

    def _fake_signature(path: str):
        if path.endswith("daily_prices.csv"):
            return (100, 200)
        if path.endswith("korean_stocks_list.csv"):
            return (300, 400)
        return None

    def _fake_top_sqlite_context(
        cls,
        *,
        source: str = "csv",
        market: str,
        top_n: int,
        target_date: str | None,
        min_change_pct: float,
        csv_signature: tuple[int, int] | None,
        stocks_signature: tuple[int, int] | None,
    ):
        del cls, source, market, top_n, target_date, min_change_pct, csv_signature, stocks_signature
        return (str(tmp_path / ".krx_collector_cache" / "top_gainers.snapshot"), (77, 88))

    calls = {"count": 0}

    def _fake_load_shared_csv_file(
        data_dir: str,
        filename: str,
        *,
        deep_copy: bool = True,
        usecols: list[str] | None = None,
        signature: tuple[int, int] | None = None,
    ) -> pd.DataFrame:
        del data_dir, deep_copy, usecols, signature
        calls["count"] += 1
        if filename == "daily_prices.csv":
            return daily_df.copy()
        if filename == "korean_stocks_list.csv":
            return stocks_df.copy()
        return pd.DataFrame()

    monkeypatch.setattr(collectors_module, "_shared_file_signature", _fake_signature)
    monkeypatch.setattr(
        collectors_module.KRXCollector,
        "_top_gainers_sqlite_context",
        classmethod(_fake_top_sqlite_context),
    )
    monkeypatch.setattr(
        collectors_module.KRXCollector,
        "_stock_lookup_sqlite_context",
        classmethod(
            lambda cls, **_kwargs: (
                str(tmp_path / ".krx_collector_cache" / "stock_lookup_case3.snapshot"),
                (33, 44),
            )
        ),
    )
    monkeypatch.setattr(collectors_module, "_load_shared_csv_file", _fake_load_shared_csv_file)

    first = collector._load_from_local_csv("KOSPI", top_n=5, target_date="20260221")
    assert len(first) == 1
    assert first[0].code == "000001"
    assert calls["count"] >= 2

    with collectors_module.KRXCollector._top_gainers_cache_lock:
        collectors_module.KRXCollector._top_gainers_cache.clear()

    monkeypatch.setattr(
        collectors_module,
        "_load_shared_csv_file",
        lambda *_a, **_k: (_ for _ in ()).throw(
            AssertionError("sqlite snapshot hit 시 CSV 로더를 호출하면 안 됩니다.")
        ),
    )

    second = collector._load_from_local_csv("KOSPI", top_n=5, target_date="20260221")
    assert len(second) == 1
    assert second[0].code == "000001"


def test_load_from_local_csv_reuses_stock_lookup_sqlite_snapshot(monkeypatch, tmp_path):
    collector = collectors_module.KRXCollector(config=types.SimpleNamespace(min_change_pct=0.0))
    with collectors_module.KRXCollector._top_gainers_cache_lock:
        collectors_module.KRXCollector._top_gainers_cache.clear()
    collectors_module.KRXCollector.clear_stock_lookup_cache()

    daily_df = pd.DataFrame(
        [
            {
                "ticker": "000001",
                "date": "2026-02-21",
                "open": 1000,
                "close": 1100,
                "volume": 2_000_000,
                "change_pct": 5.0,
                "trading_value": 2_200_000_000,
            }
        ]
    )
    stocks_df = pd.DataFrame([{"ticker": "000001", "name": "테스트", "market": "KOSPI"}])

    def _fake_signature(path: str):
        if path.endswith("daily_prices.csv"):
            return (1000, 2000)
        if path.endswith("korean_stocks_list.csv"):
            return (3000, 4000)
        return None

    def _fake_top_sqlite_context(
        cls,
        *,
        source: str = "csv",
        market: str,
        top_n: int,
        target_date: str | None,
        min_change_pct: float,
        csv_signature: tuple[int, int] | None,
        stocks_signature: tuple[int, int] | None,
    ):
        del cls, source, market, target_date, min_change_pct, csv_signature, stocks_signature
        return (
            str(tmp_path / ".krx_collector_cache" / f"top_gainers__{top_n}.snapshot"),
            (55 + int(top_n), 66 + int(top_n)),
        )

    call_counter = {"daily_prices.csv": 0, "korean_stocks_list.csv": 0}

    def _first_loader(
        data_dir: str,
        filename: str,
        *,
        deep_copy: bool = True,
        usecols: list[str] | None = None,
        signature: tuple[int, int] | None = None,
    ) -> pd.DataFrame:
        del data_dir, deep_copy, usecols, signature
        if filename in call_counter:
            call_counter[filename] += 1
        if filename == "daily_prices.csv":
            return daily_df.copy()
        if filename == "korean_stocks_list.csv":
            return stocks_df.copy()
        return pd.DataFrame()

    monkeypatch.setattr(collectors_module, "_shared_file_signature", _fake_signature)
    monkeypatch.setattr(
        collectors_module.KRXCollector,
        "_top_gainers_sqlite_context",
        classmethod(_fake_top_sqlite_context),
    )
    monkeypatch.setattr(
        collectors_module.KRXCollector,
        "_stock_lookup_sqlite_context",
        classmethod(
            lambda cls, **_kwargs: (
                str(tmp_path / ".krx_collector_cache" / "stock_lookup_case4.snapshot"),
                (77, 88),
            )
        ),
    )
    monkeypatch.setattr(collectors_module, "_load_shared_csv_file", _first_loader)

    first = collector._load_from_local_csv("KOSPI", top_n=1, target_date="20260221")
    assert len(first) == 1
    assert call_counter["daily_prices.csv"] == 1
    assert call_counter["korean_stocks_list.csv"] == 1

    collectors_module.KRXCollector.clear_stock_lookup_cache()
    with collectors_module.KRXCollector._top_gainers_cache_lock:
        collectors_module.KRXCollector._top_gainers_cache.clear()

    def _second_loader(
        data_dir: str,
        filename: str,
        *,
        deep_copy: bool = True,
        usecols: list[str] | None = None,
        signature: tuple[int, int] | None = None,
    ) -> pd.DataFrame:
        del data_dir, deep_copy, usecols, signature
        if filename in call_counter:
            call_counter[filename] += 1
        if filename == "korean_stocks_list.csv":
            raise AssertionError("stock lookup sqlite snapshot hit 시 stocks CSV를 다시 읽으면 안 됩니다.")
        if filename == "daily_prices.csv":
            return daily_df.copy()
        return pd.DataFrame()

    monkeypatch.setattr(collectors_module, "_load_shared_csv_file", _second_loader)

    second = collector._load_from_local_csv("KOSPI", top_n=2, target_date="20260221")
    assert len(second) == 1
    assert second[0].code == "000001"
    assert call_counter["daily_prices.csv"] == 2
    assert call_counter["korean_stocks_list.csv"] == 1


def test_get_top_gainers_reuses_pykrx_sqlite_snapshot_after_memory_clear(monkeypatch, tmp_path):
    collector = collectors_module.KRXCollector(config=types.SimpleNamespace(min_change_pct=0.0))
    collector._stock_name_cache.clear()
    with collectors_module.KRXCollector._top_gainers_cache_lock:
        collectors_module.KRXCollector._top_gainers_cache.clear()

    monkeypatch.setattr(
        collectors_module.KRXCollector,
        "_top_gainers_sqlite_context",
        classmethod(
            lambda cls, **_kwargs: (
                str(tmp_path / ".krx_collector_cache" / "pykrx_top_gainers.snapshot"),
                (123, 456),
            )
        ),
    )
    monkeypatch.setattr(
        collectors_module.KRXCollector,
        "_stock_name_sqlite_context",
        classmethod(
            lambda cls, ticker: (
                str(tmp_path / ".krx_collector_cache" / "stock_name" / f"{str(ticker).zfill(6)}.snapshot"),
                (312, 421),
            )
        ),
    )

    calls = {"ohlcv": 0, "name": 0}

    def _fake_get_market_ohlcv_by_ticker(*_args, **_kwargs):
        calls["ohlcv"] += 1
        return pd.DataFrame(
            {
                "종가": [11_000],
                "거래대금": [2_500_000_000],
                "등락률": [5.5],
                "거래량": [2_000_000],
            },
            index=["000001"],
        )

    def _fake_get_market_ticker_name(_code: str):
        calls["name"] += 1
        return "테스트종목"

    fake_stock_ns = types.SimpleNamespace(
        get_market_ohlcv_by_ticker=_fake_get_market_ohlcv_by_ticker,
        get_market_ticker_name=_fake_get_market_ticker_name,
    )
    fake_pykrx = types.ModuleType("pykrx")
    fake_pykrx.stock = fake_stock_ns
    monkeypatch.setitem(sys.modules, "pykrx", fake_pykrx)

    first = asyncio.run(collector.get_top_gainers("KOSPI", top_n=5, target_date="20260221"))
    assert len(first) == 1
    assert first[0].code == "000001"
    assert calls["ohlcv"] == 1
    assert calls["name"] == 1

    with collectors_module.KRXCollector._top_gainers_cache_lock:
        collectors_module.KRXCollector._top_gainers_cache.clear()

    fake_stock_ns.get_market_ohlcv_by_ticker = lambda *_a, **_k: (_ for _ in ()).throw(
        AssertionError("pykrx ohlcv should be skipped by sqlite snapshot")
    )
    fake_stock_ns.get_market_ticker_name = lambda *_a, **_k: (_ for _ in ()).throw(
        AssertionError("pykrx ticker name should be skipped by sqlite snapshot")
    )

    second = asyncio.run(collector.get_top_gainers("KOSPI", top_n=5, target_date="20260221"))
    assert len(second) == 1
    assert second[0].code == "000001"
    assert calls["ohlcv"] == 1
    assert calls["name"] == 1


def test_get_supply_data_reuses_pykrx_sqlite_snapshot_after_memory_clear(monkeypatch, tmp_path):
    collector = collectors_module.KRXCollector(config=types.SimpleNamespace(min_change_pct=0.0))
    with collectors_module.KRXCollector._pykrx_supply_cache_lock:
        collectors_module.KRXCollector._pykrx_supply_cache.clear()

    monkeypatch.setattr(
        collectors_module.KRXCollector,
        "_pykrx_supply_sqlite_context",
        classmethod(
            lambda cls, **_kwargs: (
                str(tmp_path / ".krx_collector_cache" / "pykrx_supply_5d.snapshot"),
                (987, 654),
            )
        ),
    )
    monkeypatch.setattr(
        collectors_module.KRXCollector,
        "_get_latest_market_date",
        lambda self: "20260221",
    )
    monkeypatch.setattr(
        collectors_module,
        "get_investor_trend_5day_for_ticker",
        lambda **_kwargs: None,
    )

    calls = {"count": 0}

    def _fake_get_market_trading_value_by_date(*_args, **_kwargs):
        calls["count"] += 1
        return pd.DataFrame(
            {
                "외국인합계": [1_000_000_000, 500_000_000, -200_000_000, 100_000_000, 300_000_000],
                "기관합계": [300_000_000, -100_000_000, 200_000_000, 100_000_000, 50_000_000],
                "개인": [-1_300_000_000, -400_000_000, 0, -200_000_000, -350_000_000],
            }
        )

    fake_stock_ns = types.SimpleNamespace(
        get_market_trading_value_by_date=_fake_get_market_trading_value_by_date,
    )
    fake_pykrx = types.ModuleType("pykrx")
    fake_pykrx.stock = fake_stock_ns
    monkeypatch.setitem(sys.modules, "pykrx", fake_pykrx)

    first = asyncio.run(collector.get_supply_data("000001"))
    assert first is not None
    assert first.foreign_buy_5d == 1_700_000_000
    assert first.inst_buy_5d == 550_000_000
    assert first.retail_buy_5d == -2_250_000_000
    assert calls["count"] == 1

    with collectors_module.KRXCollector._pykrx_supply_cache_lock:
        collectors_module.KRXCollector._pykrx_supply_cache.clear()

    fake_stock_ns.get_market_trading_value_by_date = lambda *_a, **_k: (_ for _ in ()).throw(
        AssertionError("pykrx supply query should be skipped by sqlite snapshot")
    )

    second = asyncio.run(collector.get_supply_data("000001"))
    assert second is not None
    assert second.foreign_buy_5d == 1_700_000_000
    assert second.inst_buy_5d == 550_000_000
    assert second.retail_buy_5d == -2_250_000_000
    assert calls["count"] == 1


def test_get_chart_data_reuses_pykrx_sqlite_snapshot_after_memory_clear(monkeypatch, tmp_path):
    collector = collectors_module.KRXCollector(config=types.SimpleNamespace(min_change_pct=0.0))
    with collectors_module.KRXCollector._pykrx_chart_cache_lock:
        collectors_module.KRXCollector._pykrx_chart_cache.clear()

    monkeypatch.setattr(
        collectors_module.KRXCollector,
        "_pykrx_chart_sqlite_context",
        classmethod(
            lambda cls, **_kwargs: (
                str(tmp_path / ".krx_collector_cache" / "pykrx_chart.snapshot"),
                (321, 654),
            )
        ),
    )
    monkeypatch.setattr(
        collectors_module.KRXCollector,
        "_get_latest_market_date",
        lambda self: "20260221",
    )

    calls = {"count": 0}

    def _fake_get_market_ohlcv_by_date(*_args, **_kwargs):
        calls["count"] += 1
        index = pd.to_datetime(
            ["2026-02-19", "2026-02-20", "2026-02-21", "2026-02-24", "2026-02-25"]
        )
        return pd.DataFrame(
            {
                "시가": [100, 101, 102, 103, 104],
                "고가": [110, 111, 112, 113, 114],
                "저가": [90, 91, 92, 93, 94],
                "종가": [105, 106, 107, 108, 109],
                "거래량": [1000, 1100, 1200, 1300, 1400],
            },
            index=index,
        )

    fake_stock_ns = types.SimpleNamespace(
        get_market_ohlcv_by_date=_fake_get_market_ohlcv_by_date,
    )
    fake_pykrx = types.ModuleType("pykrx")
    fake_pykrx.stock = fake_stock_ns
    monkeypatch.setitem(sys.modules, "pykrx", fake_pykrx)

    first = asyncio.run(collector.get_chart_data("005930", 3))
    assert first is not None
    assert len(first.closes) == 3
    assert calls["count"] == 1

    with collectors_module.KRXCollector._pykrx_chart_cache_lock:
        collectors_module.KRXCollector._pykrx_chart_cache.clear()

    fake_stock_ns.get_market_ohlcv_by_date = lambda *_a, **_k: (_ for _ in ()).throw(
        AssertionError("pykrx chart query should be skipped by sqlite snapshot")
    )

    second = asyncio.run(collector.get_chart_data("005930", 3))
    assert second is not None
    assert second.closes == first.closes
    assert calls["count"] == 1


def test_naver_finance_investor_trend_prefers_unified_service(monkeypatch):
    collector = collectors_module.NaverFinanceCollector(
        config=types.SimpleNamespace(DATA_DIR="data")
    )
    captured: dict[str, object] = {}
    import engine.collectors.naver_pykrx_mixin as naver_pykrx_mixin_module

    def _fake_get_investor_trend_5day_for_ticker(**kwargs):
        captured.update(kwargs)
        return {
            "foreign": 321_000_000,
            "institution": -123_000_000,
        }

    monkeypatch.setattr(
        collectors_module,
        "get_investor_trend_5day_for_ticker",
        _fake_get_investor_trend_5day_for_ticker,
    )
    monkeypatch.setattr(
        naver_pykrx_mixin_module,
        "get_investor_trend_5day_for_ticker",
        _fake_get_investor_trend_5day_for_ticker,
    )
    monkeypatch.setitem(sys.modules, "pykrx", None)

    result = {"investorTrend": {"foreign": 0, "institution": 0, "individual": 0}}
    asyncio.run(collector._get_investor_trend("1234", result))

    assert captured["ticker"] == "001234"
    assert captured["verify_with_references"] is False
    assert result["investorTrend"]["foreign"] == 321_000_000
    assert result["investorTrend"]["institution"] == -123_000_000
    assert result["investorTrend"]["individual"] == 0


def test_naver_finance_investor_trend_uses_pykrx_sqlite_summary_cache(monkeypatch):
    collector = collectors_module.NaverFinanceCollector(
        config=types.SimpleNamespace(DATA_DIR="data")
    )
    import engine.collectors.krx as krx_module
    import engine.collectors.naver_pykrx_mixin as naver_pykrx_mixin_module

    monkeypatch.setattr(
        collectors_module,
        "get_investor_trend_5day_for_ticker",
        lambda **_kwargs: {
            "foreign": 101,
            "institution": 202,
            "quality": {"csv_anomaly_flags": ["stale_csv"]},
        },
    )
    monkeypatch.setattr(
        naver_pykrx_mixin_module,
        "get_investor_trend_5day_for_ticker",
        lambda **_kwargs: {
            "foreign": 101,
            "institution": 202,
            "quality": {"csv_anomaly_flags": ["stale_csv"]},
        },
    )
    monkeypatch.setattr(
        collectors_module.KRXCollector,
        "_get_latest_market_date",
        lambda self: "20260221",
    )
    monkeypatch.setattr(
        krx_module.KRXCollector,
        "_get_latest_market_date",
        lambda self: "20260221",
    )
    monkeypatch.setattr(
        collectors_module.KRXCollector,
        "_load_cached_pykrx_supply_summary",
        classmethod(
            lambda cls, *, ticker, end_date: {
                "foreign_buy_5d": 700_000_000,
                "inst_buy_5d": -200_000_000,
                "retail_buy_5d": -500_000_000,
            }
        ),
    )
    monkeypatch.setattr(
        krx_module.KRXCollector,
        "_load_pykrx_supply_summary_snapshot",
        lambda self, *, ticker, end_date: {
            "foreign_buy_5d": 700_000_000,
            "inst_buy_5d": -200_000_000,
            "retail_buy_5d": -500_000_000,
        },
    )
    fake_pykrx = types.ModuleType("pykrx")
    fake_pykrx.stock = types.SimpleNamespace(
        get_market_trading_value_by_date=lambda *_a, **_k: (_ for _ in ()).throw(
            AssertionError("pykrx 조회는 sqlite summary cache hit에서 호출되면 안 됩니다.")
        )
    )
    monkeypatch.setitem(sys.modules, "pykrx", fake_pykrx)

    result = {"investorTrend": {"foreign": 0, "institution": 0, "individual": 0}}
    asyncio.run(collector._get_investor_trend("5930", result))

    assert result["investorTrend"]["foreign"] == 700_000_000
    assert result["investorTrend"]["institution"] == -200_000_000
    assert result["investorTrend"]["individual"] == -500_000_000


def test_naver_finance_fundamental_reuses_sqlite_snapshot_after_memory_clear(monkeypatch, tmp_path):
    collector = collectors_module.NaverFinanceCollector(
        config=types.SimpleNamespace(DATA_DIR="data")
    )
    import engine.collectors.naver_pykrx_mixin as naver_pykrx_mixin_module
    with collectors_module.KRXCollector._pykrx_fundamental_cache_lock:
        collectors_module.KRXCollector._pykrx_fundamental_cache.clear()
    with naver_pykrx_mixin_module.NaverPykrxMixin._pykrx_fundamental_cache_lock:
        naver_pykrx_mixin_module.NaverPykrxMixin._pykrx_fundamental_cache.clear()
    with naver_pykrx_mixin_module.NaverPykrxMixin._pykrx_market_fundamental_cache_lock:
        naver_pykrx_mixin_module.NaverPykrxMixin._pykrx_market_fundamental_cache.clear()

    monkeypatch.setattr(
        collectors_module.KRXCollector,
        "_pykrx_fundamental_sqlite_context",
        classmethod(
            lambda cls, *, ticker, target_date: (
                str(tmp_path / f"{ticker}__{target_date}.snapshot"),
                (41, 41),
            )
        ),
    )
    monkeypatch.setattr(
        naver_pykrx_mixin_module.NaverPykrxMixin,
        "_pykrx_fundamental_sqlite_context",
        classmethod(
            lambda cls, *, ticker, target_date: (
                str(tmp_path / f"{ticker}__{target_date}.snapshot"),
                (41, 41),
            )
        ),
    )
    monkeypatch.setattr(
        naver_pykrx_mixin_module.NaverPykrxMixin,
        "_pykrx_market_fundamental_sqlite_context",
        classmethod(
            lambda cls, *, target_date: (
                str(tmp_path / f"market__{target_date}.snapshot"),
                (42, 42),
            )
        ),
    )

    calls = {"count": 0}

    def _fake_get_market_fundamental_by_ticker(target_date: str):
        calls["count"] += 1
        _ = target_date
        return pd.DataFrame(
            {
                "PER": [11.2],
                "PBR": [1.4],
                "EPS": [4500],
                "BPS": [35000],
                "DIV": [2.3],
            },
            index=["005930"],
        )

    fake_pykrx = types.ModuleType("pykrx")
    fake_pykrx.stock = types.SimpleNamespace(
        get_market_fundamental_by_ticker=_fake_get_market_fundamental_by_ticker,
    )
    monkeypatch.setitem(sys.modules, "pykrx", fake_pykrx)

    first_result = {
        "indicators": {
            "per": 0,
            "pbr": 0,
            "eps": 0,
            "bps": 0,
            "dividendYield": 0,
        }
    }
    asyncio.run(collector._get_fundamental_data("005930", first_result))

    assert calls["count"] == 1
    assert first_result["indicators"]["per"] == 11.2
    assert first_result["indicators"]["pbr"] == 1.4
    assert first_result["indicators"]["eps"] == 4500.0

    with collectors_module.KRXCollector._pykrx_fundamental_cache_lock:
        collectors_module.KRXCollector._pykrx_fundamental_cache.clear()
    with naver_pykrx_mixin_module.NaverPykrxMixin._pykrx_fundamental_cache_lock:
        naver_pykrx_mixin_module.NaverPykrxMixin._pykrx_fundamental_cache.clear()
    with naver_pykrx_mixin_module.NaverPykrxMixin._pykrx_market_fundamental_cache_lock:
        naver_pykrx_mixin_module.NaverPykrxMixin._pykrx_market_fundamental_cache.clear()

    fake_pykrx.stock.get_market_fundamental_by_ticker = lambda *_a, **_k: (_ for _ in ()).throw(
        AssertionError("pykrx 펀더멘탈 조회는 sqlite snapshot hit에서 호출되면 안 됩니다.")
    )

    second_result = {
        "indicators": {
            "per": 0,
            "pbr": 0,
            "eps": 0,
            "bps": 0,
            "dividendYield": 0,
        }
    }
    asyncio.run(collector._get_fundamental_data("005930", second_result))

    assert calls["count"] == 1
    assert second_result["indicators"]["per"] == 11.2
    assert second_result["indicators"]["pbr"] == 1.4
    assert second_result["indicators"]["eps"] == 4500.0


def test_naver_finance_fundamental_reuses_market_snapshot_sqlite_for_second_ticker(monkeypatch, tmp_path):
    collector = collectors_module.NaverFinanceCollector(
        config=types.SimpleNamespace(DATA_DIR="data")
    )
    import engine.collectors.naver_pykrx_mixin as naver_pykrx_mixin_module

    with naver_pykrx_mixin_module.NaverPykrxMixin._pykrx_fundamental_cache_lock:
        naver_pykrx_mixin_module.NaverPykrxMixin._pykrx_fundamental_cache.clear()
    with naver_pykrx_mixin_module.NaverPykrxMixin._pykrx_market_fundamental_cache_lock:
        naver_pykrx_mixin_module.NaverPykrxMixin._pykrx_market_fundamental_cache.clear()

    monkeypatch.setattr(
        naver_pykrx_mixin_module.NaverPykrxMixin,
        "_pykrx_fundamental_sqlite_context",
        classmethod(
            lambda cls, *, ticker, target_date: (
                str(tmp_path / ".krx_collector_cache" / "ticker" / f"{ticker}__{target_date}.snapshot"),
                (51, 51),
            )
        ),
    )
    monkeypatch.setattr(
        naver_pykrx_mixin_module.NaverPykrxMixin,
        "_pykrx_market_fundamental_sqlite_context",
        classmethod(
            lambda cls, *, target_date: (
                str(tmp_path / ".krx_collector_cache" / "market" / f"{target_date}.snapshot"),
                (52, 52),
            )
        ),
    )

    calls = {"count": 0}

    def _fake_get_market_fundamental_by_ticker(target_date: str):
        calls["count"] += 1
        _ = target_date
        return pd.DataFrame(
            {
                "PER": [11.2, 8.7],
                "PBR": [1.4, 1.1],
                "EPS": [4500, 3800],
                "BPS": [35000, 29000],
                "DIV": [2.3, 1.8],
            },
            index=["005930", "000660"],
        )

    fake_pykrx = types.ModuleType("pykrx")
    fake_pykrx.stock = types.SimpleNamespace(
        get_market_fundamental_by_ticker=_fake_get_market_fundamental_by_ticker,
    )
    monkeypatch.setitem(sys.modules, "pykrx", fake_pykrx)

    first_result = {
        "indicators": {
            "per": 0,
            "pbr": 0,
            "eps": 0,
            "bps": 0,
            "dividendYield": 0,
        }
    }
    asyncio.run(collector._get_fundamental_data("005930", first_result))
    assert calls["count"] == 1
    assert first_result["indicators"]["per"] == 11.2

    with naver_pykrx_mixin_module.NaverPykrxMixin._pykrx_fundamental_cache_lock:
        naver_pykrx_mixin_module.NaverPykrxMixin._pykrx_fundamental_cache.clear()
    with naver_pykrx_mixin_module.NaverPykrxMixin._pykrx_market_fundamental_cache_lock:
        naver_pykrx_mixin_module.NaverPykrxMixin._pykrx_market_fundamental_cache.clear()

    fake_pykrx.stock.get_market_fundamental_by_ticker = lambda *_a, **_k: (_ for _ in ()).throw(
        AssertionError("시장 펀더멘탈 sqlite snapshot hit에서는 pykrx 재호출이 없어야 합니다.")
    )

    second_result = {
        "indicators": {
            "per": 0,
            "pbr": 0,
            "eps": 0,
            "bps": 0,
            "dividendYield": 0,
        }
    }
    asyncio.run(collector._get_fundamental_data("000660", second_result))
    assert calls["count"] == 1
    assert second_result["indicators"]["per"] == 8.7
    assert second_result["indicators"]["pbr"] == 1.1
    assert second_result["indicators"]["eps"] == 3800.0
