#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KR Market Backtest Service 단위 테스트
"""

import pandas as pd

from services.kr_market_backtest_service import (
    build_latest_price_map,
    build_cumulative_trade_record,
    build_ticker_price_index,
    calculate_jongga_backtest_stats,
    calculate_scenario_return,
    prepare_cumulative_price_dataframe,
)


def test_build_ticker_price_index_groups_by_ticker():
    price_df = pd.DataFrame(
        [
            {"date": "2026-02-20", "ticker": "5930", "close": 100},
            {"date": "2026-02-21", "ticker": "005930", "close": 101},
            {"date": "2026-02-21", "ticker": "000660", "close": 200},
        ]
    )
    price_df["date"] = pd.to_datetime(price_df["date"])
    price_df = price_df.set_index("date")

    index_map = build_ticker_price_index(price_df)

    assert set(index_map.keys()) == {"005930", "000660"}
    assert len(index_map["005930"]) == 2


def test_build_ticker_price_index_sorts_date_within_ticker():
    price_df = pd.DataFrame(
        [
            {"date": "2026-02-22", "ticker": "005930", "close": 102},
            {"date": "2026-02-20", "ticker": "005930", "close": 100},
            {"date": "2026-02-21", "ticker": "005930", "close": 101},
        ]
    )
    price_df["date"] = pd.to_datetime(price_df["date"])

    index_map = build_ticker_price_index(price_df)
    ticker_df = index_map["005930"]

    assert ticker_df["close"].tolist() == [100, 101, 102]


def test_build_cumulative_trade_record_uses_prebuilt_price_index():
    stock_prices = pd.DataFrame(
        [{"high": 110, "low": 99, "close": 108}],
        index=pd.to_datetime(["2026-02-21"]),
    )
    signal = {
        "ticker": "005930",
        "entry_price": 100,
        "grade": "S",
        "name": "삼성전자",
        "score": {"total": 10},
    }

    trade = build_cumulative_trade_record(
        signal=signal,
        stats_date="2026-02-20",
        price_df=pd.DataFrame(),
        price_index={"005930": stock_prices},
    )

    assert trade is not None
    assert trade["outcome"] == "WIN"
    assert trade["roi"] == 9.0


def test_calculate_scenario_return_prefers_stop_when_same_day_hits_both():
    stock_prices = pd.DataFrame(
        [{"high": 120, "low": 94, "close": 110}],
        index=pd.to_datetime(["2026-02-21"]),
    )
    # 같은 날 고가/저가가 동시에 익절/손절 조건을 만족하면 손절 우선.
    scenario_return = calculate_scenario_return(
        ticker="005930",
        entry_price=100,
        signal_date="2026-02-20",
        current_price=110,
        price_df=stock_prices,
        stock_prices=stock_prices,
        target_pct=0.15,
        stop_pct=0.05,
    )

    assert scenario_return == -5.0


def test_calculate_scenario_return_handles_invalid_signal_date_gracefully():
    price_df = pd.DataFrame(
        [
            {"ticker": "005930", "date": "2026-02-21", "high": 120, "low": 95, "close": 110},
        ]
    )
    price_df["date"] = pd.to_datetime(price_df["date"])

    scenario_return = calculate_scenario_return(
        ticker="005930",
        entry_price=100,
        signal_date="invalid-date",
        current_price=110,
        price_df=price_df,
        target_pct=0.15,
        stop_pct=0.05,
    )

    assert isinstance(scenario_return, float)


def test_calculate_scenario_return_with_invalid_signal_date_and_indexed_prices():
    stock_prices = pd.DataFrame(
        [{"high": 120, "low": 99, "close": 110}],
        index=pd.to_datetime(["2026-02-21"]),
    )

    scenario_return = calculate_scenario_return(
        ticker="005930",
        entry_price=100,
        signal_date="invalid-date",
        current_price=110,
        price_df=stock_prices,
        stock_prices=stock_prices,
        target_pct=0.15,
        stop_pct=0.05,
    )

    assert scenario_return == 15.0


def test_calculate_scenario_return_sorts_unsorted_date_rows_before_hit_check():
    stock_prices = pd.DataFrame(
        [
            {"date": "2026-02-22", "high": 120, "low": 99, "close": 110},
            {"date": "2026-02-21", "high": 100, "low": 94, "close": 98},
        ]
    )
    stock_prices["date"] = pd.to_datetime(stock_prices["date"])

    scenario_return = calculate_scenario_return(
        ticker="005930",
        entry_price=100,
        signal_date="2026-02-20",
        current_price=110,
        price_df=stock_prices,
        stock_prices=stock_prices,
        target_pct=0.15,
        stop_pct=0.05,
    )

    assert scenario_return == -5.0


def test_build_latest_price_map_uses_latest_row_per_ticker():
    price_df = pd.DataFrame(
        [
            {"ticker": "5930", "date": "2026-02-20", "close": 100},
            {"ticker": "005930", "date": "2026-02-21", "close": 103},
            {"ticker": "000660", "date": "2026-02-21", "close": 201},
        ]
    )

    latest_map = build_latest_price_map(price_df)

    assert latest_map["005930"] == 103
    assert latest_map["000660"] == 201


def test_prepare_cumulative_price_dataframe_normalizes_ticker_and_date_index():
    raw_df = pd.DataFrame(
        [
            {"ticker": "5930", "date": "2026-02-20", "close": "100"},
            {"ticker": "005930", "date": "2026-02-21", "close": "101"},
        ]
    )

    normalized = prepare_cumulative_price_dataframe(raw_df)

    assert not normalized.empty
    assert normalized.index.name == "date"
    assert normalized["ticker"].tolist() == ["005930", "005930"]
    assert float(normalized["close"].iloc[-1]) == 101.0


def test_calculate_jongga_backtest_stats_marks_new_and_injects_candidate_price():
    candidates = [{"stock_code": "5930", "entry_price": 100}]
    stats = calculate_jongga_backtest_stats(
        candidates=candidates,
        history_payloads=[],
        price_map={"005930": 110.0},
        price_df=pd.DataFrame(),
    )

    assert stats["status"] == "OK (New)"
    assert stats["count"] == 0
    assert stats["candidates"][0]["current_price"] == 110.0
    assert stats["candidates"][0]["return_pct"] == 10.0
