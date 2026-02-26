#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KRX 로컬 CSV 캐시 리팩토링 테스트
"""

from __future__ import annotations

import asyncio
import logging
import os
import sqlite3
import sys
import time
import types

import pandas as pd
import pytest

from engine.collectors.krx_data_mixin import KRXCollectorDataMixin
import engine.collectors.krx_local_cache_helpers as krx_local_cache_helpers
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


def test_read_csv_cached_prefers_shared_loader_when_supported(monkeypatch, tmp_path):
    csv_path = tmp_path / "sample.csv"
    pd.DataFrame([{"a": 1}, {"a": 2}]).to_csv(csv_path, index=False)

    cache: dict[str, CsvCacheEntry] = {}
    shared_calls = {"count": 0}

    def _fake_shared_loader(data_dir, filename, *, deep_copy, usecols=None, signature=None):
        shared_calls["count"] += 1
        assert data_dir == str(tmp_path)
        assert filename == "sample.csv"
        assert deep_copy is False
        assert signature is not None
        return pd.DataFrame([{"a": 1}, {"a": 2}])

    monkeypatch.setattr(krx_local_cache_helpers, "_load_shared_csv_file", _fake_shared_loader)
    monkeypatch.setattr(
        krx_local_cache_helpers.pd,
        "read_csv",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("pd.read_csv should not be used")),
    )

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

    assert len(first) == 2
    assert len(second) == 2
    assert shared_calls["count"] == 1


def test_read_csv_cached_falls_back_to_pd_read_csv_for_unsupported_kwargs(monkeypatch, tmp_path):
    csv_path = tmp_path / "sample.csv"
    pd.DataFrame([{"a": 1}, {"a": 2}]).to_csv(csv_path, index=False)

    cache: dict[str, CsvCacheEntry] = {}
    pd_calls = {"count": 0}
    original_read_csv = pd.read_csv

    monkeypatch.setattr(
        krx_local_cache_helpers,
        "_load_shared_csv_file",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("shared loader should not be used")),
    )

    def _counted_read_csv(*args, **kwargs):
        pd_calls["count"] += 1
        return original_read_csv(*args, **kwargs)

    monkeypatch.setattr(krx_local_cache_helpers.pd, "read_csv", _counted_read_csv)

    loaded = read_csv_cached(
        cache=cache,
        path=str(csv_path),
        cache_key="default",
        logger=logging.getLogger(__name__),
        encoding="utf-8",
    )

    assert len(loaded) == 2
    assert pd_calls["count"] == 1


def test_read_csv_cached_uses_shared_loader_with_dtype(monkeypatch, tmp_path):
    csv_path = tmp_path / "sample.csv"
    pd.DataFrame([{"a": 1}, {"a": 2}]).to_csv(csv_path, index=False)

    cache: dict[str, CsvCacheEntry] = {}
    shared_calls = {"count": 0}

    def _fake_shared_loader(_data_dir, _filename, *, deep_copy, usecols=None, signature=None):
        shared_calls["count"] += 1
        assert deep_copy is False
        assert signature is not None
        frame = pd.DataFrame([{"a": 1}, {"a": 2}])
        if usecols is None:
            return frame
        return frame.loc[:, list(usecols)]

    monkeypatch.setattr(krx_local_cache_helpers, "_load_shared_csv_file", _fake_shared_loader)
    monkeypatch.setattr(
        krx_local_cache_helpers.pd,
        "read_csv",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("pd.read_csv should not be used")),
    )

    loaded = read_csv_cached(
        cache=cache,
        path=str(csv_path),
        cache_key="default",
        logger=logging.getLogger(__name__),
        dtype={"a": str},
    )

    assert shared_calls["count"] == 1
    assert loaded["a"].tolist() == ["1", "2"]


def test_read_csv_cached_falls_back_to_pd_read_csv_when_dtype_cast_fails(monkeypatch, tmp_path):
    csv_path = tmp_path / "sample.csv"
    pd.DataFrame([{"a": "x"}, {"a": "y"}]).to_csv(csv_path, index=False)

    cache: dict[str, CsvCacheEntry] = {}
    shared_calls = {"count": 0}
    pd_calls = {"count": 0}
    original_read_csv = pd.read_csv

    def _fake_shared_loader(_data_dir, _filename, *, deep_copy, usecols=None, signature=None):
        shared_calls["count"] += 1
        assert deep_copy is False
        assert signature is not None
        frame = pd.DataFrame([{"a": "x"}, {"a": "y"}])
        if usecols is None:
            return frame
        return frame.loc[:, list(usecols)]

    def _counted_read_csv(*args, **kwargs):
        pd_calls["count"] += 1
        return original_read_csv(*args, **kwargs)

    monkeypatch.setattr(krx_local_cache_helpers, "_load_shared_csv_file", _fake_shared_loader)
    monkeypatch.setattr(krx_local_cache_helpers.pd, "read_csv", _counted_read_csv)

    with pytest.raises((ValueError, TypeError)):
        read_csv_cached(
            cache=cache,
            path=str(csv_path),
            cache_key="default",
            logger=logging.getLogger(__name__),
            dtype={"a": "int64"},
        )
    assert shared_calls["count"] == 1
    assert pd_calls["count"] == 1


def test_read_csv_cached_retries_shared_loader_without_usecols_on_schema_mismatch(monkeypatch, tmp_path):
    csv_path = tmp_path / "sample.csv"
    pd.DataFrame([{"a": 1, "b": 10}, {"a": 2, "b": 20}]).to_csv(csv_path, index=False)

    cache: dict[str, CsvCacheEntry] = {}
    shared_calls = {"count": 0}

    def _fake_shared_loader(_data_dir, _filename, *, deep_copy, usecols=None, signature=None):
        shared_calls["count"] += 1
        assert deep_copy is False
        assert signature is not None
        if usecols is not None:
            raise ValueError("Usecols do not match columns")
        return pd.DataFrame([{"a": 1, "b": 10}, {"a": 2, "b": 20}])

    monkeypatch.setattr(krx_local_cache_helpers, "_load_shared_csv_file", _fake_shared_loader)
    monkeypatch.setattr(
        krx_local_cache_helpers.pd,
        "read_csv",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("pd.read_csv should not be used")),
    )

    loaded = read_csv_cached(
        cache=cache,
        path=str(csv_path),
        cache_key="default",
        logger=logging.getLogger(__name__),
        usecols=["a", "missing_col"],
    )

    assert shared_calls["count"] == 2
    assert list(loaded.columns) == ["a"]


def test_read_csv_cached_projects_existing_columns_on_pd_fallback_after_usecols_mismatch(
    monkeypatch,
    tmp_path,
):
    csv_path = tmp_path / "sample.csv"
    pd.DataFrame([{"a": 1, "b": 10}, {"a": 2, "b": 20}]).to_csv(csv_path, index=False)

    cache: dict[str, CsvCacheEntry] = {}
    shared_calls = {"count": 0}

    def _fake_shared_loader(_data_dir, _filename, *, deep_copy, usecols=None, signature=None):
        shared_calls["count"] += 1
        assert deep_copy is False
        assert signature is not None
        if usecols is not None:
            raise ValueError("Usecols do not match columns")
        raise RuntimeError("force pd.read_csv fallback")

    monkeypatch.setattr(krx_local_cache_helpers, "_load_shared_csv_file", _fake_shared_loader)

    loaded = read_csv_cached(
        cache=cache,
        path=str(csv_path),
        cache_key="default",
        logger=logging.getLogger(__name__),
        usecols=["a", "missing_col"],
    )

    assert shared_calls["count"] == 2
    assert list(loaded.columns) == ["a"]


def test_read_csv_cached_separates_cache_by_usecols(monkeypatch, tmp_path):
    csv_path = tmp_path / "sample.csv"
    pd.DataFrame([{"a": 1, "b": 10}, {"a": 2, "b": 20}]).to_csv(csv_path, index=False)

    cache: dict[str, CsvCacheEntry] = {}
    shared_calls = {"count": 0}

    def _fake_shared_loader(_data_dir, _filename, *, deep_copy, usecols=None, signature=None):
        shared_calls["count"] += 1
        assert deep_copy is False
        assert signature is not None
        frame = pd.DataFrame([{"a": 1, "b": 10}, {"a": 2, "b": 20}])
        if usecols is None:
            return frame
        return frame.loc[:, list(usecols)]

    monkeypatch.setattr(krx_local_cache_helpers, "_load_shared_csv_file", _fake_shared_loader)
    monkeypatch.setattr(
        krx_local_cache_helpers.pd,
        "read_csv",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("pd.read_csv should not be used")),
    )

    first = read_csv_cached(
        cache=cache,
        path=str(csv_path),
        cache_key="default",
        logger=logging.getLogger(__name__),
        usecols=["a"],
    )
    second = read_csv_cached(
        cache=cache,
        path=str(csv_path),
        cache_key="default",
        logger=logging.getLogger(__name__),
        usecols=["b"],
    )

    assert list(first.columns) == ["a"]
    assert list(second.columns) == ["b"]
    assert shared_calls["count"] == 2


def test_read_local_csv_projects_existing_columns_on_usecols_mismatch(monkeypatch, tmp_path):
    csv_path = tmp_path / "sample.csv"
    pd.DataFrame(
        [
            {"ticker": "005930", "date": "2026-02-21", "close": 100.0, "extra_col": 1},
            {"ticker": "000660", "date": "2026-02-21", "close": 200.0, "extra_col": 2},
        ]
    ).to_csv(csv_path, index=False)

    collector = _DummyCollector(str(tmp_path))
    calls = {"count": 0, "usecols": []}

    def _fake_shared_loader(_data_dir, _filename, *, deep_copy, usecols=None, signature=None):
        calls["count"] += 1
        calls["usecols"].append(usecols)
        assert deep_copy is False
        assert signature is not None
        if usecols is not None:
            raise ValueError("Usecols do not match columns")
        return pd.DataFrame(
            [
                {"ticker": "005930", "date": "2026-02-21", "close": 100.0, "extra_col": 1},
                {"ticker": "000660", "date": "2026-02-21", "close": 200.0, "extra_col": 2},
            ]
        )

    monkeypatch.setattr(krx_local_data_mixin, "load_shared_csv_file", _fake_shared_loader)

    loaded = collector._read_local_csv(
        "sample.csv",
        cache_key="sample_projection",
        usecols=["ticker", "missing_col"],
    )

    assert calls["count"] == 2
    assert calls["usecols"][0] == ["ticker", "missing_col"]
    assert calls["usecols"][1] is None
    assert list(loaded.columns) == ["ticker"]


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

    # top gainers SQLite snapshot 재사용으로 2회차는 패딩 로직까지 생략된다.
    assert calls["count"] == 2


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


def test_get_chart_data_reuses_pykrx_sqlite_snapshot_after_memory_clear(monkeypatch, tmp_path):
    collector = _DummyCollector(str(tmp_path))
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

    collector._pykrx_chart_cache = {}
    fake_stock_ns.get_market_ohlcv_by_date = lambda *_a, **_k: (_ for _ in ()).throw(
        AssertionError("pykrx 조회는 sqlite snapshot hit 시 호출되면 안 됩니다.")
    )
    monkeypatch.setattr(
        collector,
        "_read_local_csv",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("csv fallback 없이 sqlite snapshot을 사용해야 합니다.")),
    )

    second = asyncio.run(collector.get_chart_data("005930", 3))
    assert second is not None
    assert second.closes == first.closes
    assert calls["count"] == 1


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


def test_get_supply_data_uses_pykrx_fallback_when_unified_trend_has_anomaly_flags(monkeypatch, tmp_path):
    collector = _DummyCollector(str(tmp_path))
    captured_calls: list[dict[str, object]] = []

    monkeypatch.setattr(
        krx_local_data_mixin,
        "get_investor_trend_5day_for_ticker",
        lambda **kwargs: captured_calls.append(dict(kwargs)) or {
            "foreign": 999_999_999,
            "institution": 888_888_888,
            "quality": {"csv_anomaly_flags": ["stale_csv"]},
        },
    )

    fake_pykrx = types.ModuleType("pykrx")
    fake_pykrx.stock = types.SimpleNamespace(
        get_market_trading_value_by_date=lambda *_a, **_k: pd.DataFrame(
            {
                "외국인합계": [10, 20, 30, 40, 50],
                "기관합계": [1, 2, 3, 4, 5],
                "개인": [-11, -22, -33, -44, -55],
            }
        )
    )
    monkeypatch.setitem(sys.modules, "pykrx", fake_pykrx)

    supply = asyncio.run(collector.get_supply_data("005930"))

    assert supply is not None
    assert supply.foreign_buy_5d == 150
    assert supply.inst_buy_5d == 15
    assert supply.retail_buy_5d == -165
    assert len(captured_calls) == 1
    assert captured_calls[0]["verify_with_references"] is False


def test_get_supply_data_fallback_reuses_precomputed_supply_summary_map(monkeypatch, tmp_path):
    fake_pykrx = types.ModuleType("pykrx")
    fake_pykrx.stock = types.SimpleNamespace(get_market_trading_value_by_date=lambda *_a, **_k: pd.DataFrame())
    monkeypatch.setitem(sys.modules, "pykrx", fake_pykrx)

    collector = _DummyCollector(str(tmp_path))
    calls = {"count": 0}

    def _fake_read_local_csv(filename: str, *, cache_key: str, **kwargs):
        calls["count"] += 1
        assert filename == "all_institutional_trend_data.csv"
        assert cache_key == "institutional_trend_supply"
        assert kwargs.get("usecols") == ["ticker", "date", "foreign_buy", "inst_buy"]
        return pd.DataFrame(
            [
                {"ticker": "005930", "date": "2026-02-20", "foreign_buy": 10, "inst_buy": 20},
                {"ticker": "005930", "date": "2026-02-21", "foreign_buy": 11, "inst_buy": 21},
                {"ticker": "005930", "date": "2026-02-22", "foreign_buy": 12, "inst_buy": 22},
                {"ticker": "005930", "date": "2026-02-23", "foreign_buy": 13, "inst_buy": 23},
                {"ticker": "005930", "date": "2026-02-24", "foreign_buy": 14, "inst_buy": 24},
                {"ticker": "000660", "date": "2026-02-20", "foreign_buy": 1, "inst_buy": 2},
                {"ticker": "000660", "date": "2026-02-21", "foreign_buy": 2, "inst_buy": 3},
                {"ticker": "000660", "date": "2026-02-22", "foreign_buy": 3, "inst_buy": 4},
                {"ticker": "000660", "date": "2026-02-23", "foreign_buy": 4, "inst_buy": 5},
                {"ticker": "000660", "date": "2026-02-24", "foreign_buy": 5, "inst_buy": 6},
            ]
        )

    monkeypatch.setattr(collector, "_read_local_csv", _fake_read_local_csv)

    first = asyncio.run(collector.get_supply_data("005930"))
    second = asyncio.run(collector.get_supply_data("000660"))

    assert first is not None
    assert second is not None
    assert first.foreign_buy_5d == 60
    assert first.inst_buy_5d == 110
    assert second.foreign_buy_5d == 15
    assert second.inst_buy_5d == 20
    # 수급 요약 맵을 캐시하므로 CSV 로드는 최초 1회만 수행된다.
    assert calls["count"] == 1


def test_get_top_gainers_reuses_pykrx_sqlite_snapshot_after_memory_clear(monkeypatch, tmp_path):
    collector = _DummyCollector(str(tmp_path))
    calls = {"ohlcv": 0}

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

    fake_stock_ns = types.SimpleNamespace(
        get_market_ohlcv_by_ticker=_fake_get_market_ohlcv_by_ticker,
    )
    fake_pykrx = types.ModuleType("pykrx")
    fake_pykrx.stock = fake_stock_ns
    monkeypatch.setitem(sys.modules, "pykrx", fake_pykrx)

    first = asyncio.run(collector.get_top_gainers("KOSPI", top_n=5, target_date="20260221"))
    assert len(first) == 1
    assert first[0].code == "000001"
    assert calls["ohlcv"] == 1

    collector._pykrx_top_gainers_cache = {}
    fake_stock_ns.get_market_ohlcv_by_ticker = lambda *_a, **_k: (_ for _ in ()).throw(
        AssertionError("pykrx 조회는 sqlite snapshot hit 시 호출되면 안 됩니다.")
    )

    second = asyncio.run(collector.get_top_gainers("KOSPI", top_n=5, target_date="20260221"))
    assert len(second) == 1
    assert second[0].code == "000001"
    assert calls["ohlcv"] == 1


def test_get_supply_data_reuses_pykrx_sqlite_snapshot_after_memory_clear(monkeypatch, tmp_path):
    collector = _DummyCollector(str(tmp_path))
    monkeypatch.setattr(
        krx_local_data_mixin,
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

    first = asyncio.run(collector.get_supply_data("005930"))
    assert first is not None
    assert first.foreign_buy_5d == 1_700_000_000
    assert first.inst_buy_5d == 550_000_000
    assert first.retail_buy_5d == -2_250_000_000
    assert calls["count"] == 1

    collector._pykrx_supply_summary_cache = {}
    fake_stock_ns.get_market_trading_value_by_date = lambda *_a, **_k: (_ for _ in ()).throw(
        AssertionError("pykrx 조회는 sqlite snapshot hit 시 호출되면 안 됩니다.")
    )
    monkeypatch.setattr(
        collector,
        "_load_supply_summary_map",
        lambda: (_ for _ in ()).throw(AssertionError("pykrx sqlite snapshot을 우선 사용해야 합니다.")),
    )

    second = asyncio.run(collector.get_supply_data("005930"))
    assert second is not None
    assert second.foreign_buy_5d == 1_700_000_000
    assert second.inst_buy_5d == 550_000_000
    assert second.retail_buy_5d == -2_250_000_000
    assert calls["count"] == 1


def test_load_supply_summary_map_reuses_sqlite_snapshot_after_memory_clear(monkeypatch, tmp_path):
    trend_path = tmp_path / "all_institutional_trend_data.csv"
    pd.DataFrame(
        [
            {"ticker": "005930", "date": "2026-02-20", "foreign_buy": 10, "inst_buy": 20},
            {"ticker": "005930", "date": "2026-02-21", "foreign_buy": 11, "inst_buy": 21},
            {"ticker": "005930", "date": "2026-02-22", "foreign_buy": 12, "inst_buy": 22},
            {"ticker": "005930", "date": "2026-02-23", "foreign_buy": 13, "inst_buy": 23},
            {"ticker": "005930", "date": "2026-02-24", "foreign_buy": 14, "inst_buy": 24},
            {"ticker": "000660", "date": "2026-02-20", "foreign_buy": 1, "inst_buy": 2},
            {"ticker": "000660", "date": "2026-02-21", "foreign_buy": 2, "inst_buy": 3},
            {"ticker": "000660", "date": "2026-02-22", "foreign_buy": 3, "inst_buy": 4},
            {"ticker": "000660", "date": "2026-02-23", "foreign_buy": 4, "inst_buy": 5},
            {"ticker": "000660", "date": "2026-02-24", "foreign_buy": 5, "inst_buy": 6},
        ]
    ).to_csv(trend_path, index=False)

    collector = _DummyCollector(str(tmp_path))
    calls = {"count": 0}

    def _fake_read_local_csv(filename: str, *, cache_key: str, **kwargs):
        calls["count"] += 1
        assert filename == "all_institutional_trend_data.csv"
        assert cache_key == "institutional_trend_supply"
        assert kwargs.get("usecols") == ["ticker", "date", "foreign_buy", "inst_buy"]
        return pd.read_csv(trend_path)

    monkeypatch.setattr(collector, "_read_local_csv", _fake_read_local_csv)

    first = collector._load_supply_summary_map()
    assert first["005930"] == (60, 110)
    assert first["000660"] == (15, 20)
    assert calls["count"] == 1

    collector._supply_summary_cache = {}
    monkeypatch.setattr(
        collector,
        "_read_local_csv",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("should use sqlite snapshot")),
    )

    second = collector._load_supply_summary_map()
    assert second["005930"] == (60, 110)
    assert second["000660"] == (15, 20)
    assert calls["count"] == 1

    sqlite_key = krx_local_data_mixin._supply_summary_sqlite_cache_key(str(trend_path))
    with sqlite3.connect(tmp_path / "runtime_cache.db") as conn:
        row_count = int(
            conn.execute(
                """
                SELECT COUNT(*)
                FROM json_file_payload_cache
                WHERE filepath = ?
                """,
                (sqlite_key,),
            ).fetchone()[0]
        )
    assert row_count >= 1


def test_load_stock_lookup_maps_reuses_sqlite_snapshot_after_memory_clear(monkeypatch, tmp_path):
    stocks_path = tmp_path / "korean_stocks_list.csv"
    pd.DataFrame(
        [
            {"ticker": "005930", "name": "삼성전자", "market": "KOSPI"},
            {"ticker": "000660", "name": "SK하이닉스", "market": "KOSPI"},
        ]
    ).to_csv(stocks_path, index=False)

    collector = _DummyCollector(str(tmp_path))
    calls = {"count": 0}

    def _fake_read_local_csv(filename: str, *, cache_key: str, **kwargs):
        calls["count"] += 1
        assert filename == "korean_stocks_list.csv"
        assert cache_key == "stocks_list"
        assert kwargs.get("usecols") == ["ticker", "name", "market"]
        return pd.read_csv(stocks_path)

    monkeypatch.setattr(collector, "_read_local_csv", _fake_read_local_csv)

    market_map, name_map = collector._load_stock_lookup_maps()
    assert market_map["005930"] == "KOSPI"
    assert name_map["005930"] == "삼성전자"
    assert name_map["000660"] == "SK하이닉스"
    assert calls["count"] == 1

    collector._stocks_lookup_cache = {}
    monkeypatch.setattr(
        collector,
        "_read_local_csv",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("should use sqlite snapshot")),
    )

    market_map_2, name_map_2 = collector._load_stock_lookup_maps()
    assert market_map_2["005930"] == "KOSPI"
    assert name_map_2["005930"] == "삼성전자"
    assert name_map_2["000660"] == "SK하이닉스"
    assert calls["count"] == 1

    sqlite_key = krx_local_data_mixin._stock_lookup_sqlite_cache_key(str(stocks_path))
    with sqlite3.connect(tmp_path / "runtime_cache.db") as conn:
        row_count = int(
            conn.execute(
                """
                SELECT COUNT(*)
                FROM json_file_payload_cache
                WHERE filepath = ?
                """,
                (sqlite_key,),
            ).fetchone()[0]
        )
    assert row_count >= 1


def test_load_from_local_csv_reuses_top_gainers_sqlite_snapshot_after_memory_clear(monkeypatch, tmp_path):
    prices_path = tmp_path / "daily_prices.csv"
    pd.DataFrame(
        [
            {
                "ticker": "005930",
                "date": "2026-02-21",
                "open": 1000,
                "close": 1110,
                "volume": 2_500_000,
            },
            {
                "ticker": "000660",
                "date": "2026-02-21",
                "open": 2000,
                "close": 2020,
                "volume": 2_000_000,
            },
        ]
    ).to_csv(prices_path, index=False)

    stocks_path = tmp_path / "korean_stocks_list.csv"
    pd.DataFrame(
        [
            {"ticker": "005930", "name": "삼성전자", "market": "KOSPI"},
            {"ticker": "000660", "name": "SK하이닉스", "market": "KOSPI"},
        ]
    ).to_csv(stocks_path, index=False)

    collector = _DummyCollector(str(tmp_path))
    first = collector._load_from_local_csv("KOSPI", top_n=5, target_date="20260221")
    assert len(first) >= 1
    assert first[0].market == "KOSPI"

    collector._local_processed_csv_cache = {}
    collector._stocks_lookup_cache = {}
    monkeypatch.setattr(
        collector,
        "_read_local_csv",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("should use sqlite top gainers snapshot")),
    )

    second = collector._load_from_local_csv("KOSPI", top_n=5, target_date="20260221")
    assert len(second) == len(first)
    assert second[0].market == "KOSPI"

    sqlite_key = krx_local_data_mixin._top_gainers_sqlite_cache_key(
        csv_path=str(prices_path),
        market="KOSPI",
        top_n=5,
        target_date="20260221",
        min_change_pct=0.0,
    )
    with sqlite3.connect(tmp_path / "runtime_cache.db") as conn:
        row_count = int(
            conn.execute(
                """
                SELECT COUNT(*)
                FROM json_file_payload_cache
                WHERE filepath = ?
                """,
                (sqlite_key,),
            ).fetchone()[0]
        )
    assert row_count >= 1
