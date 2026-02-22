#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KR Market Realtime Price Service 리팩토링 테스트
"""

from __future__ import annotations

import logging
import sqlite3
import sys
from types import SimpleNamespace

import pandas as pd

import services.kr_market_realtime_latest_close_cache as latest_close_cache
import services.kr_market_realtime_market_map_cache as market_map_cache
from services.kr_market_realtime_price_service import (
    build_market_map,
    clear_market_map_cache,
    fetch_yfinance_missing_prices,
    fetch_naver_missing_prices,
    fetch_small_batch_prices,
    fill_missing_prices_from_csv,
    normalize_unique_tickers,
)


def test_normalize_unique_tickers_preserves_order_and_deduplicates():
    tickers = ["5930", "005930", "000660", 660, "035420"]

    normalized = normalize_unique_tickers(tickers)

    assert normalized == ["005930", "000660", "035420"]


def test_normalize_unique_tickers_fast_path_for_pre_normalized_input():
    tickers = ["005930", "000660", "035420"]

    normalized = normalize_unique_tickers(tickers)

    assert normalized == tickers


def test_fetch_small_batch_prices_deduplicates_network_calls(monkeypatch):
    calls: list[str] = []

    def fake_fetch_stock_price(ticker):
        calls.append(ticker)
        return {"price": 70000 if ticker == "005930" else 120000}

    monkeypatch.setattr("engine.data_sources.fetch_stock_price", fake_fetch_stock_price)

    prices = fetch_small_batch_prices(["5930", "005930", "660", "000660"], logging.getLogger(__name__))

    assert prices["005930"] == 70000.0
    assert prices["000660"] == 120000.0
    assert sorted(calls) == ["000660", "005930"]


def test_fetch_small_batch_prices_small_input_uses_sequential_path(monkeypatch):
    calls: list[str] = []

    def fake_fetch_stock_price(ticker):
        calls.append(ticker)
        return {"price": 50000}

    monkeypatch.setattr("engine.data_sources.fetch_stock_price", fake_fetch_stock_price)

    prices = fetch_small_batch_prices(["5930", "005930"], logging.getLogger(__name__))

    assert prices == {"005930": 50000.0}
    assert calls == ["005930"]


def test_fetch_small_batch_prices_can_skip_normalization_for_pre_normalized_input(monkeypatch):
    monkeypatch.setattr(
        "services.kr_market_realtime_price_service.normalize_unique_tickers",
        lambda _tickers: (_ for _ in ()).throw(AssertionError("normalize_unique_tickers should not be called")),
    )
    monkeypatch.setattr(
        "engine.data_sources.fetch_stock_price",
        lambda ticker: {"price": 1000 + int(ticker[-1])},
    )

    prices = fetch_small_batch_prices(
        ["005930", "000660"],
        logging.getLogger(__name__),
        normalize_input=False,
    )

    assert prices == {"005930": 1000.0, "000660": 1000.0}


def test_fill_missing_prices_from_csv_prefers_latest_date_when_unsorted():
    prices: dict[str, float] = {}

    def _load_csv_file(_name: str) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {"date": "2026-02-22", "ticker": "005930", "close": 120},
                {"date": "2026-02-20", "ticker": "000660", "close": 98},
                {"date": "2026-02-21", "ticker": "005930", "close": 110},
            ]
        )

    fill_missing_prices_from_csv(["005930", "5930"], prices, _load_csv_file)

    assert prices["005930"] == 120.0


def test_fill_missing_prices_from_cached_price_map_without_loading_csv():
    prices: dict[str, float] = {}

    fill_missing_prices_from_csv(
        ["005930", "5930", "000660"],
        prices,
        lambda _name: (_ for _ in ()).throw(AssertionError("load_csv_file should not be called")),
        latest_price_map={"5930": 120.0, "000660": 210.0},
    )

    assert prices["005930"] == 120.0
    assert prices["000660"] == 210.0


def test_fill_missing_prices_from_csv_handles_invalid_close_as_zero():
    prices: dict[str, float] = {}

    def _load_csv_file(_name: str) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {"date": "2026-02-22", "ticker": "005930", "close": "N/A"},
                {"date": "2026-02-22", "ticker": "000660", "close": 210},
            ]
        )

    fill_missing_prices_from_csv(["005930", "000660"], prices, _load_csv_file)

    assert prices["005930"] == 0.0
    assert prices["000660"] == 210.0


def test_fill_missing_prices_from_csv_skips_io_when_all_prices_already_resolved():
    prices: dict[str, float] = {"005930": 120.0, "000660": 210.0}

    fill_missing_prices_from_csv(
        ["005930", "000660"],
        prices,
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("load_csv_file should not run when prices are already complete")
        ),
        get_data_path=lambda filename: f"/tmp/{filename}",
    )

    assert prices == {"005930": 120.0, "000660": 210.0}


def test_fill_missing_prices_from_csv_uses_sqlite_latest_close_cache_after_memory_clear(tmp_path):
    clear_market_map_cache()
    daily_prices_path = tmp_path / "daily_prices.csv"
    pd.DataFrame(
        [
            {"date": "2026-02-22", "ticker": "005930", "close": 120.0},
            {"date": "2026-02-20", "ticker": "000660", "close": 98.0},
            {"date": "2026-02-21", "ticker": "005930", "close": 110.0},
        ]
    ).to_csv(daily_prices_path, index=False)

    get_data_path = lambda filename: str(tmp_path / filename)
    prices: dict[str, float] = {}
    fill_missing_prices_from_csv(
        ["005930", "5930", "000660"],
        prices,
        lambda name, **kwargs: pd.read_csv(tmp_path / name, usecols=kwargs.get("usecols")),
        get_data_path=get_data_path,
        logger=logging.getLogger(__name__),
    )
    assert prices["005930"] == 120.0
    assert prices["000660"] == 98.0

    clear_market_map_cache()
    prices_2: dict[str, float] = {}
    fill_missing_prices_from_csv(
        ["005930", "000660"],
        prices_2,
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("load_csv_file should not run when sqlite cache is warm")
        ),
        get_data_path=get_data_path,
        logger=logging.getLogger(__name__),
    )
    assert prices_2["005930"] == 120.0
    assert prices_2["000660"] == 98.0

    with sqlite3.connect(tmp_path / "runtime_cache.db") as conn:
        row_count = conn.execute(
            "SELECT COUNT(*) FROM realtime_latest_close_map_cache"
        ).fetchone()[0]
    assert int(row_count) == 1


def test_fill_missing_prices_from_csv_creates_latest_close_sqlite_parent_dir(monkeypatch, tmp_path):
    clear_market_map_cache()
    daily_prices_path = tmp_path / "daily_prices.csv"
    pd.DataFrame(
        [
            {"date": "2026-02-22", "ticker": "005930", "close": 120.0},
            {"date": "2026-02-21", "ticker": "000660", "close": 98.0},
        ]
    ).to_csv(daily_prices_path, index=False)

    db_path = tmp_path / "cache" / "latest_close" / "runtime_cache.db"
    monkeypatch.setattr(
        latest_close_cache,
        "_resolve_latest_close_map_cache_db_path",
        lambda _source_path: str(db_path),
    )
    get_data_path = lambda filename: str(tmp_path / filename)

    prices: dict[str, float] = {}
    fill_missing_prices_from_csv(
        ["005930", "000660"],
        prices,
        lambda name, **kwargs: pd.read_csv(tmp_path / name, usecols=kwargs.get("usecols")),
        get_data_path=get_data_path,
        logger=logging.getLogger(__name__),
    )

    assert prices["005930"] == 120.0
    assert db_path.exists()

    with sqlite3.connect(db_path) as conn:
        row_count = conn.execute("SELECT COUNT(*) FROM realtime_latest_close_map_cache").fetchone()[0]
    assert int(row_count) >= 1


def test_fill_missing_prices_from_csv_recovers_when_latest_close_table_missing(tmp_path):
    clear_market_map_cache()
    daily_prices_path = tmp_path / "daily_prices.csv"
    pd.DataFrame(
        [
            {"date": "2026-02-22", "ticker": "005930", "close": 120.0},
            {"date": "2026-02-21", "ticker": "000660", "close": 98.0},
        ]
    ).to_csv(daily_prices_path, index=False)

    get_data_path = lambda filename: str(tmp_path / filename)

    prices: dict[str, float] = {}
    fill_missing_prices_from_csv(
        ["005930", "000660"],
        prices,
        lambda name, **kwargs: pd.read_csv(tmp_path / name, usecols=kwargs.get("usecols")),
        get_data_path=get_data_path,
        logger=logging.getLogger(__name__),
    )
    assert prices["005930"] == 120.0

    db_path = tmp_path / "runtime_cache.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute("DROP TABLE realtime_latest_close_map_cache")
        conn.commit()

    latest_close_cache.clear_latest_close_map_cache()
    prices_after_drop: dict[str, float] = {}
    fill_missing_prices_from_csv(
        ["005930", "000660"],
        prices_after_drop,
        lambda name, **kwargs: pd.read_csv(tmp_path / name, usecols=kwargs.get("usecols")),
        get_data_path=get_data_path,
        logger=logging.getLogger(__name__),
    )
    assert prices_after_drop["005930"] == 120.0
    assert prices_after_drop["000660"] == 98.0

    with sqlite3.connect(db_path) as conn:
        row_count = int(conn.execute("SELECT COUNT(*) FROM realtime_latest_close_map_cache").fetchone()[0])
    assert row_count >= 1


def test_fill_missing_prices_from_csv_skips_latest_close_delete_when_rows_within_limit(monkeypatch, tmp_path):
    latest_close_cache.clear_latest_close_map_cache()
    pd.DataFrame(
        [
            {"date": "2026-02-22", "ticker": "005930", "close": 120.0},
            {"date": "2026-02-21", "ticker": "000660", "close": 98.0},
        ]
    ).to_csv(tmp_path / "daily_prices.csv", index=False)

    monkeypatch.setattr(latest_close_cache, "_LATEST_CLOSE_MAP_SQLITE_MAX_ROWS", 16)

    traced_sql: list[str] = []
    original_connect = latest_close_cache.connect_sqlite

    def _traced_connect(*args, **kwargs):
        conn = original_connect(*args, **kwargs)
        conn.set_trace_callback(traced_sql.append)
        return conn

    monkeypatch.setattr(latest_close_cache, "connect_sqlite", _traced_connect)

    prices: dict[str, float] = {}
    fill_missing_prices_from_csv(
        ["005930", "000660"],
        prices,
        lambda name, **kwargs: pd.read_csv(tmp_path / name, usecols=kwargs.get("usecols")),
        get_data_path=lambda filename: str(tmp_path / filename),
        logger=logging.getLogger(__name__),
    )

    assert prices["005930"] == 120.0
    assert not any("DELETE FROM realtime_latest_close_map_cache" in sql for sql in traced_sql)


def test_fill_missing_prices_from_csv_stores_compact_latest_close_payload_json(tmp_path):
    latest_close_cache.clear_latest_close_map_cache()
    pd.DataFrame(
        [
            {"date": "2026-02-22", "ticker": "005930", "close": 120.0},
            {"date": "2026-02-21", "ticker": "000660", "close": 98.0},
        ]
    ).to_csv(tmp_path / "daily_prices.csv", index=False)

    prices: dict[str, float] = {}
    fill_missing_prices_from_csv(
        ["005930", "000660"],
        prices,
        lambda name, **kwargs: pd.read_csv(tmp_path / name, usecols=kwargs.get("usecols")),
        get_data_path=lambda filename: str(tmp_path / filename),
        logger=logging.getLogger(__name__),
    )

    assert prices["005930"] == 120.0
    db_path = tmp_path / "runtime_cache.db"
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT payload_json FROM realtime_latest_close_map_cache LIMIT 1"
        ).fetchone()

    assert row is not None
    payload_json = str(row[0])
    assert ": " not in payload_json
    assert ", " not in payload_json


def test_build_market_map_normalizes_ticker_and_drops_invalid_rows():
    def _load_csv_file(_name: str) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {"ticker": "5930", "market": "KOSPI"},
                {"ticker": None, "market": "KOSDAQ"},
                {"ticker": "000660", "market": None},
            ]
        )

    market_map = build_market_map(_load_csv_file)

    assert market_map == {"005930": "KOSPI"}


def test_build_market_map_reuses_memory_cache_with_signature(tmp_path):
    clear_market_map_cache()
    stocks_path = tmp_path / "korean_stocks_list.csv"
    pd.DataFrame(
        [
            {"ticker": "5930", "market": "KOSPI"},
            {"ticker": "000660", "market": "KOSDAQ"},
        ]
    ).to_csv(stocks_path, index=False)

    calls = {"count": 0}

    def _load_csv_file(name: str, **kwargs):
        calls["count"] += 1
        usecols = kwargs.get("usecols")
        return pd.read_csv(tmp_path / name, dtype={"ticker": str}, usecols=usecols)

    get_data_path = lambda filename: str(tmp_path / filename)

    first = build_market_map(_load_csv_file, get_data_path=get_data_path)
    second = build_market_map(_load_csv_file, get_data_path=get_data_path)

    assert first == {"005930": "KOSPI", "000660": "KOSDAQ"}
    assert second == first
    assert calls["count"] == 1


def test_build_market_map_reuses_sqlite_cache_after_memory_clear(tmp_path):
    clear_market_map_cache()
    stocks_path = tmp_path / "korean_stocks_list.csv"
    pd.DataFrame(
        [
            {"ticker": "5930", "market": "KOSPI"},
            {"ticker": "000660", "market": "KOSDAQ"},
        ]
    ).to_csv(stocks_path, index=False)

    get_data_path = lambda filename: str(tmp_path / filename)

    first = build_market_map(
        lambda name, **kwargs: pd.read_csv(
            tmp_path / name,
            dtype={"ticker": str},
            usecols=kwargs.get("usecols"),
        ),
        get_data_path=get_data_path,
    )
    assert first == {"005930": "KOSPI", "000660": "KOSDAQ"}

    clear_market_map_cache()
    second = build_market_map(
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("should load market map from sqlite cache")
        ),
        get_data_path=get_data_path,
    )
    assert second == first

    db_path = tmp_path / "runtime_cache.db"
    with sqlite3.connect(db_path) as conn:
        row_count = conn.execute("SELECT COUNT(*) FROM realtime_market_map_cache").fetchone()[0]
    assert int(row_count) == 1


def test_build_market_map_creates_sqlite_parent_dir_when_missing(monkeypatch, tmp_path):
    clear_market_map_cache()
    pd.DataFrame(
        [
            {"ticker": "5930", "market": "KOSPI"},
            {"ticker": "000660", "market": "KOSDAQ"},
        ]
    ).to_csv(tmp_path / "korean_stocks_list.csv", index=False)

    db_path = tmp_path / "cache" / "market_map" / "runtime_cache.db"
    monkeypatch.setattr(
        market_map_cache,
        "_resolve_market_map_cache_db_path",
        lambda _source_path: str(db_path),
    )

    get_data_path = lambda filename: str(tmp_path / filename)
    market_map = build_market_map(
        lambda name, **kwargs: pd.read_csv(tmp_path / name, dtype={"ticker": str}, usecols=kwargs.get("usecols")),
        get_data_path=get_data_path,
    )

    assert market_map == {"005930": "KOSPI", "000660": "KOSDAQ"}
    assert db_path.exists()

    with sqlite3.connect(db_path) as conn:
        row_count = conn.execute("SELECT COUNT(*) FROM realtime_market_map_cache").fetchone()[0]
    assert int(row_count) >= 1


def test_build_market_map_recovers_when_sqlite_table_missing(tmp_path):
    clear_market_map_cache()
    pd.DataFrame(
        [
            {"ticker": "5930", "market": "KOSPI"},
            {"ticker": "000660", "market": "KOSDAQ"},
        ]
    ).to_csv(tmp_path / "korean_stocks_list.csv", index=False)

    get_data_path = lambda filename: str(tmp_path / filename)
    first = build_market_map(
        lambda name, **kwargs: pd.read_csv(tmp_path / name, dtype={"ticker": str}, usecols=kwargs.get("usecols")),
        get_data_path=get_data_path,
    )
    assert first == {"005930": "KOSPI", "000660": "KOSDAQ"}

    db_path = tmp_path / "runtime_cache.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute("DROP TABLE realtime_market_map_cache")
        conn.commit()

    clear_market_map_cache()
    second = build_market_map(
        lambda name, **kwargs: pd.read_csv(tmp_path / name, dtype={"ticker": str}, usecols=kwargs.get("usecols")),
        get_data_path=get_data_path,
    )
    assert second == first

    with sqlite3.connect(db_path) as conn:
        row_count = int(conn.execute("SELECT COUNT(*) FROM realtime_market_map_cache").fetchone()[0])
    assert row_count >= 1


def test_build_market_map_skips_delete_when_rows_within_limit(monkeypatch, tmp_path):
    clear_market_map_cache()
    pd.DataFrame(
        [
            {"ticker": "5930", "market": "KOSPI"},
            {"ticker": "000660", "market": "KOSDAQ"},
        ]
    ).to_csv(tmp_path / "korean_stocks_list.csv", index=False)

    monkeypatch.setattr(market_map_cache, "_MARKET_MAP_SQLITE_MAX_ROWS", 16)

    traced_sql: list[str] = []
    original_connect = market_map_cache.connect_sqlite

    def _traced_connect(*args, **kwargs):
        conn = original_connect(*args, **kwargs)
        conn.set_trace_callback(traced_sql.append)
        return conn

    monkeypatch.setattr(market_map_cache, "connect_sqlite", _traced_connect)

    market_map = build_market_map(
        lambda name, **kwargs: pd.read_csv(tmp_path / name, dtype={"ticker": str}, usecols=kwargs.get("usecols")),
        get_data_path=lambda filename: str(tmp_path / filename),
    )

    assert market_map == {"005930": "KOSPI", "000660": "KOSDAQ"}
    assert not any("DELETE FROM realtime_market_map_cache" in sql for sql in traced_sql)


def test_build_market_map_stores_compact_payload_json(tmp_path):
    clear_market_map_cache()
    pd.DataFrame(
        [
            {"ticker": "5930", "market": "KOSPI"},
            {"ticker": "000660", "market": "KOSDAQ"},
        ]
    ).to_csv(tmp_path / "korean_stocks_list.csv", index=False)

    market_map = build_market_map(
        lambda name, **kwargs: pd.read_csv(tmp_path / name, dtype={"ticker": str}, usecols=kwargs.get("usecols")),
        get_data_path=lambda filename: str(tmp_path / filename),
    )
    assert market_map == {"005930": "KOSPI", "000660": "KOSDAQ"}

    db_path = tmp_path / "runtime_cache.db"
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT payload_json FROM realtime_market_map_cache LIMIT 1"
        ).fetchone()

    assert row is not None
    payload_json = str(row[0])
    assert ": " not in payload_json
    assert ", " not in payload_json


def test_fetch_naver_missing_prices_reuses_session_per_worker(monkeypatch):
    import requests

    created_sessions = {"count": 0}
    called_urls: list[str] = []

    class _DummyResponse:
        def __init__(self, status_code: int, payload: dict[str, object]):
            self.status_code = status_code
            self._payload = payload

        def json(self):
            return dict(self._payload)

    class _DummySession:
        def __init__(self):
            created_sessions["count"] += 1

        def get(self, url, headers=None, timeout=0):
            del headers, timeout
            called_urls.append(url)
            return _DummyResponse(200, {"closePrice": "1,234"})

        def close(self):
            return None

    monkeypatch.setattr(requests, "Session", _DummySession)

    tickers = [str(idx).zfill(6) for idx in range(1, 13)]
    prices: dict[str, float] = {}

    fetch_naver_missing_prices(tickers, prices, logging.getLogger(__name__))

    assert len(prices) == 12
    assert all(value == 1234.0 for value in prices.values())
    assert len(called_urls) == 12
    assert created_sessions["count"] < len(called_urls)


def test_fetch_naver_missing_prices_small_input_uses_single_session(monkeypatch):
    import requests

    created_sessions = {"count": 0}

    class _DummyResponse:
        def __init__(self, status_code: int, payload: dict[str, object]):
            self.status_code = status_code
            self._payload = payload

        def json(self):
            return dict(self._payload)

    class _DummySession:
        def __init__(self):
            created_sessions["count"] += 1

        def get(self, _url, headers=None, timeout=0):
            del headers, timeout
            return _DummyResponse(200, {"closePrice": "9,999"})

        def close(self):
            return None

    monkeypatch.setattr(requests, "Session", _DummySession)

    prices: dict[str, float] = {}
    fetch_naver_missing_prices(["005930", "000660"], prices, logging.getLogger(__name__))

    assert prices == {"005930": 9999.0, "000660": 9999.0}
    assert created_sessions["count"] == 1


def test_fetch_yfinance_missing_prices_skips_recent_failed_tickers(monkeypatch):
    class _FakeNow:
        hour = 10

        @staticmethod
        def weekday() -> int:
            return 2

    class _FakeDatetime:
        @staticmethod
        def now() -> _FakeNow:
            return _FakeNow()

    download_calls = {"count": 0}

    def _fake_download(*_args, **_kwargs):
        download_calls["count"] += 1
        return pd.DataFrame()

    monkeypatch.setattr("services.kr_market_realtime_price_service.datetime", _FakeDatetime)
    monkeypatch.setattr(
        "services.kr_market_realtime_price_service._load_recent_yfinance_failed_tickers",
        lambda _tickers, **_kwargs: {"005930"},
    )
    monkeypatch.setitem(sys.modules, "yfinance", SimpleNamespace(download=_fake_download))

    prices: dict[str, float] = {}
    fetch_yfinance_missing_prices(
        ["005930"],
        prices,
        lambda _name: pd.DataFrame(),
        logging.getLogger(__name__),
        get_data_path=lambda filename: f"/tmp/{filename}",
    )

    assert prices == {}
    assert download_calls["count"] == 0


def test_fetch_yfinance_missing_prices_records_failed_tickers_on_empty_result(monkeypatch):
    class _FakeNow:
        hour = 10

        @staticmethod
        def weekday() -> int:
            return 2

    class _FakeDatetime:
        @staticmethod
        def now() -> _FakeNow:
            return _FakeNow()

    recorded: dict[str, list[str]] = {}

    monkeypatch.setattr("services.kr_market_realtime_price_service.datetime", _FakeDatetime)
    monkeypatch.setattr(
        "services.kr_market_realtime_price_service._load_recent_yfinance_failed_tickers",
        lambda _tickers, **_kwargs: set(),
    )
    monkeypatch.setattr(
        "services.kr_market_realtime_price_service._save_yfinance_failed_tickers",
        lambda tickers, **_kwargs: recorded.setdefault("tickers", list(tickers)),
    )
    monkeypatch.setattr(
        "services.kr_market_realtime_price_service.build_market_map",
        lambda *_args, **_kwargs: {"005930": "KOSPI", "000660": "KOSDAQ"},
    )
    monkeypatch.setitem(
        sys.modules,
        "yfinance",
        SimpleNamespace(download=lambda *_args, **_kwargs: pd.DataFrame()),
    )

    prices: dict[str, float] = {}
    fetch_yfinance_missing_prices(
        ["005930", "000660"],
        prices,
        lambda _name: pd.DataFrame(),
        logging.getLogger(__name__),
        get_data_path=lambda filename: f"/tmp/{filename}",
    )

    assert prices == {}
    assert recorded["tickers"] == ["005930", "000660"]


def test_fetch_yfinance_missing_prices_records_only_unresolved_tickers(monkeypatch):
    class _FakeNow:
        hour = 10

        @staticmethod
        def weekday() -> int:
            return 2

    class _FakeDatetime:
        @staticmethod
        def now() -> _FakeNow:
            return _FakeNow()

    recorded: dict[str, list[str]] = {}

    monkeypatch.setattr("services.kr_market_realtime_price_service.datetime", _FakeDatetime)
    monkeypatch.setattr(
        "services.kr_market_realtime_price_service._load_recent_yfinance_failed_tickers",
        lambda _tickers, **_kwargs: set(),
    )
    monkeypatch.setattr(
        "services.kr_market_realtime_price_service._save_yfinance_failed_tickers",
        lambda tickers, **_kwargs: recorded.setdefault("tickers", list(tickers)),
    )
    monkeypatch.setattr(
        "services.kr_market_realtime_price_service.build_market_map",
        lambda *_args, **_kwargs: {"005930": "KOSPI", "000660": "KOSDAQ"},
    )
    monkeypatch.setitem(
        sys.modules,
        "yfinance",
        SimpleNamespace(
            download=lambda *_args, **_kwargs: pd.DataFrame(
                [[70123.0, None]],
                columns=pd.MultiIndex.from_tuples(
                    [
                        ("Close", "005930.KS"),
                        ("Close", "000660.KQ"),
                    ]
                ),
            )
        ),
    )

    prices: dict[str, float] = {}
    fetch_yfinance_missing_prices(
        ["005930", "000660"],
        prices,
        lambda _name: pd.DataFrame(),
        logging.getLogger(__name__),
        get_data_path=lambda filename: f"/tmp/{filename}",
    )

    assert prices["005930"] == 70123.0
    assert "000660" not in prices
    assert recorded["tickers"] == ["000660"]


def test_fetch_yfinance_missing_prices_calls_download_with_threads_disabled(monkeypatch):
    class _FakeNow:
        hour = 10

        @staticmethod
        def weekday() -> int:
            return 2

    class _FakeDatetime:
        @staticmethod
        def now() -> _FakeNow:
            return _FakeNow()

    captured_kwargs: dict[str, object] = {}

    def _fake_download(*_args, **kwargs):
        captured_kwargs.update(kwargs)
        return pd.DataFrame(
            [[70123.0]],
            columns=pd.MultiIndex.from_tuples([("Close", "005930.KS")]),
        )

    monkeypatch.setattr("services.kr_market_realtime_price_service.datetime", _FakeDatetime)
    monkeypatch.setattr(
        "services.kr_market_realtime_price_service._load_recent_yfinance_failed_tickers",
        lambda _tickers, **_kwargs: set(),
    )
    monkeypatch.setattr(
        "services.kr_market_realtime_price_service._save_yfinance_failed_tickers",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        "services.kr_market_realtime_price_service.build_market_map",
        lambda *_args, **_kwargs: {"005930": "KOSPI"},
    )
    monkeypatch.setitem(sys.modules, "yfinance", SimpleNamespace(download=_fake_download))

    prices: dict[str, float] = {}
    fetch_yfinance_missing_prices(
        ["005930"],
        prices,
        lambda _name: pd.DataFrame(),
        logging.getLogger(__name__),
        get_data_path=lambda filename: f"/tmp/{filename}",
    )

    assert prices["005930"] == 70123.0
    assert captured_kwargs["threads"] is False
