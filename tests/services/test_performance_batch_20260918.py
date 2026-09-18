#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""2026-09-18 성과 묶음 회귀 테스트."""

from __future__ import annotations

import logging
from datetime import datetime

import pandas as pd
import pytest

from services import kr_market_cumulative_cache as cumulative_cache
from services import kr_market_data_cache_core as data_cache_core
from services import kr_market_data_cache_prices as data_cache_prices
from services.kr_market_backtest_kpi_helpers import aggregate_cumulative_kpis
from services.kr_market_backtest_stats_helpers import calculate_jongga_backtest_stats
from services.kr_market_backtest_trade_helpers import calculate_cumulative_trade_metrics


def test_aggregate_cumulative_kpis_includes_d_grade_and_recent_metrics():
    kpi = aggregate_cumulative_kpis(
        [
            {
                "grade": "D",
                "outcome": "LOSS",
                "roi": -3,
                "days": 1,
                "date": "2026-09-17",
                "code": "000002",
            },
            {
                "grade": "S",
                "outcome": "WIN",
                "roi": 5,
                "days": 1,
                "date": "2026-09-16",
                "code": "000001",
            },
        ],
        pd.DataFrame(),
        datetime(2026, 9, 18),
    )

    assert (kpi["totalSignals"], kpi["totalRoi"]) == (2, 2.0)
    assert kpi["roiByGrade"]["D"] == {
        "count": 1,
        "avgRoi": -3.0,
        "totalRoi": -3.0,
        "wins": 0,
        "losses": 1,
        "winRate": 0.0,
    }
    assert (kpi["recentWinRate"], kpi["recentClosedCount"], kpi["consecutiveLosses"]) == (50.0, 2, 1)


def test_aggregate_cumulative_kpis_sorts_closed_trades_before_recent_calculation():
    trades = [
        {"id": "old-win", "date": "2026-09-11", "code": "000001", "outcome": "WIN"},
        {"id": "a-tie-win", "date": "2026-09-20", "code": "000002", "outcome": "WIN"},
        {"id": "mid-loss", "date": "2026-09-18", "code": "000001", "outcome": "LOSS"},
        {"id": "code-loss", "date": "2026-09-20", "code": "000001", "outcome": "LOSS"},
        {"id": "recent-win-1", "date": "2026-09-15", "code": "000001", "outcome": "WIN"},
        {"id": "recent-loss", "date": "2026-09-13", "code": "000001", "outcome": "LOSS"},
        {"id": "z-tie-loss", "date": "2026-09-20", "code": "000002", "outcome": "LOSS"},
        {"id": "recent-win-2", "date": "2026-09-17", "code": "000001", "outcome": "WIN"},
        {"id": "open-future", "date": "2026-09-30", "code": "000001", "outcome": "OPEN"},
        {"id": "recent-win-3", "date": "2026-09-19", "code": "000001", "outcome": "WIN"},
        {"id": "older-win", "date": "2026-09-12", "code": "000001", "outcome": "WIN"},
        {"id": "recent-loss-2", "date": "2026-09-16", "code": "000001", "outcome": "LOSS"},
        {"id": "recent-win-4", "date": "2026-09-14", "code": "000001", "outcome": "WIN"},
    ]

    kpi = aggregate_cumulative_kpis(trades, pd.DataFrame(), datetime(2026, 9, 21))

    assert (kpi["recentWinRate"], kpi["recentClosedCount"]) == (50.0, 10)
    assert kpi["consecutiveLosses"] == 1


def test_aggregate_cumulative_kpis_uses_null_recent_win_rate_without_closed_trades():
    kpi = aggregate_cumulative_kpis(
        [{"id": "open", "date": "2026-09-18", "code": "000001", "outcome": "OPEN"}],
        pd.DataFrame(),
        datetime(2026, 9, 18),
    )

    assert (kpi["recentWinRate"], kpi["recentClosedCount"], kpi["consecutiveLosses"]) == (None, 0, 0)


@pytest.mark.parametrize(
    "stock_prices",
    [
        pd.DataFrame(
            [{"date": "2026-09-21", "high": 106, "low": 99, "close": 104}]
        ),
        pd.DataFrame(
            [{"date": 20260921, "ticker": "000001", "high": 106, "low": 99, "close": 104}]
        ),
        pd.DataFrame(
            [{"high": "106", "low": "99", "close": "104"}],
            index=pd.to_datetime(["2026-09-21"]),
        ),
        pd.DataFrame(
            [{"date": "2026-09-21", "ticker": "000001", "low": 99, "close": 104}]
        ),
        pd.DataFrame(
            [{"date": "2026-02-30", "ticker": "000001", "high": 106, "low": 99, "close": 104}]
        ),
        pd.DataFrame(
            [{"high": 106, "low": 99, "close": 104}],
            index=pd.to_datetime(["2026-09-21"], utc=True),
        ),
        pd.DataFrame(
            [{"high": 106, "low": 99, "close": 104}, {"high": 104, "low": 99, "close": 103}],
            index=pd.to_datetime(["2026-09-21", "2026-09-20"]),
        ),
        pd.DataFrame(
            [{"high": 106 + 0j, "low": 99 + 0j, "close": 104 + 0j}],
            index=pd.to_datetime(["2026-09-21"]),
        ),
        pd.DataFrame(
            [{"date": pd.Timestamp("2026-09-21", tz="UTC"), "ticker": "000001", "high": 106, "low": 99, "close": 104}]
        ),
        pd.DataFrame(
            [{"date": pd.NaT, "ticker": "000001", "high": 106, "low": 99, "close": 104}]
        ),
        pd.DataFrame(
            [{"date": pd.Timestamp("2026-09-21 12:00"), "ticker": "000001", "high": 106, "low": 99, "close": 104}]
        ),
    ],
    ids=[
        "date_frame_without_ticker",
        "numeric_yyyymmdd_date",
        "string_ohlc_datetime_index",
        "missing_required_high",
        "invalid_iso_date",
        "timezone_aware_datetime_index",
        "unordered_datetime_index",
        "complex_ohlc",
        "timezone_aware_datetime_date_column",
        "nat_datetime_date_column",
        "nonmidnight_datetime_date_column",
    ],
)
def test_calculate_cumulative_trade_metrics_rejects_invalid_nonempty_price_frames(stock_prices):
    with pytest.raises(ValueError):
        calculate_cumulative_trade_metrics(100, "2026-09-20", stock_prices)


def test_calculate_cumulative_trade_metrics_preserves_normalized_and_production_price_inputs():
    production_prices = pd.DataFrame(
        [{"date": "2026-09-21", "ticker": "000001", "high": 106.0, "low": 99.0, "close": 104.0}]
    )
    normalized_prices = pd.DataFrame(
        [{"high": 106.0, "low": 99.0, "close": 104.0}],
        index=pd.to_datetime(["2026-09-21"]),
    )

    expected = {
        "outcome": "WIN",
        "roi": 5.0,
        "max_high": 6.0,
        "days": 1,
        "price_trail": [100, 105.0],
    }
    assert calculate_cumulative_trade_metrics(100, "2026-09-20", production_prices) == expected
    assert calculate_cumulative_trade_metrics(100, "2026-09-20", normalized_prices) == expected


def test_warm_sqlite_price_snapshot_preserves_jongga_backtest_decision(tmp_path):
    daily_prices = tmp_path / "daily_prices.csv"
    pd.DataFrame(
        [{"date": "2026-09-21", "ticker": "005930", "high": 106, "low": 99, "close": 104}]
    ).to_csv(daily_prices, index=False)

    with data_cache_core.FILE_CACHE_LOCK:
        data_cache_core.CSV_FILE_CACHE.clear()
        data_cache_core.BACKTEST_PRICE_SNAPSHOT_CACHE.update(
            {"signature": None, "df": pd.DataFrame(), "price_map": {}}
        )
        data_cache_core.LATEST_VCP_PRICE_MAP_CACHE.update({"signature": None, "value": {}})
    data_cache_core._CSV_PAYLOAD_SQLITE_READY.clear()

    build_latest_price_map = lambda frame: {"005930": float(frame["close"].iloc[-1])}
    data_cache_prices.load_backtest_price_snapshot(str(tmp_path), build_latest_price_map)

    with data_cache_core.FILE_CACHE_LOCK:
        data_cache_core.CSV_FILE_CACHE.clear()
        data_cache_core.BACKTEST_PRICE_SNAPSHOT_CACHE.update(
            {"signature": None, "df": pd.DataFrame(), "price_map": {}}
        )
        data_cache_core.LATEST_VCP_PRICE_MAP_CACHE.update({"signature": None, "value": {}})

    warm_prices, latest_prices = data_cache_prices.load_backtest_price_snapshot(
        str(tmp_path),
        build_latest_price_map,
    )
    assert pd.api.types.is_datetime64_any_dtype(warm_prices["date"])

    stats = calculate_jongga_backtest_stats(
        candidates=[],
        history_payloads=[
            {
                "date": "2026-09-20",
                "signals": [{"ticker": "005930", "entry_price": 100, "grade": "S"}],
            }
        ],
        price_map=latest_prices,
        price_df=warm_prices,
    )

    assert (stats["count"], stats["win_rate"], stats["avg_return"]) == (1, 100.0, 5.0)


def test_cumulative_cache_schema_version_does_not_reuse_version_five_payload(tmp_path, monkeypatch):
    monkeypatch.setattr(cumulative_cache, "_CUMULATIVE_CACHE_DB_PATH", str(tmp_path / "runtime_cache.db"))
    (tmp_path / "daily_prices.csv").write_text("date,ticker,close\n", encoding="utf-8")
    monkeypatch.setattr(cumulative_cache, "_CUMULATIVE_CACHE_SCHEMA_VERSION", 5)
    version_five_signature = cumulative_cache.build_cumulative_cache_signature(
        data_dir_getter=lambda: str(tmp_path),
    )
    assert version_five_signature is not None

    cumulative_cache.save_cached_cumulative_payload(
        signature=version_five_signature,
        payload={"kpi": {"recentWinRate": 100.0}, "trades": []},
        logger=logging.getLogger("test-cumulative-version-six"),
    )
    monkeypatch.setattr(cumulative_cache, "_CUMULATIVE_CACHE_SCHEMA_VERSION", 6)
    version_six_signature = cumulative_cache.build_cumulative_cache_signature(
        data_dir_getter=lambda: str(tmp_path),
    )

    assert version_six_signature != version_five_signature
    assert cumulative_cache.get_cached_cumulative_payload(
        signature=version_six_signature,
        logger=logging.getLogger("test-cumulative-version-six"),
    ) is None
