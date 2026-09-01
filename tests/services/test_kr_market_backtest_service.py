#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KR Market Backtest Service 단위 테스트
"""

import pandas as pd

from services import kr_market_backtest_stats_helpers as stats_helpers
from services.kr_market_backtest_kpi_helpers import aggregate_cumulative_kpis
from services.kr_market_backtest_service import (
    build_latest_price_map,
    build_cumulative_trade_record,
    build_ticker_price_index,
    calculate_cumulative_trade_metrics,
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


def _one_day_prices(high: float, low: float, close: float):
    return pd.DataFrame(
        [{"high": high, "low": low, "close": close}],
        index=pd.to_datetime(["2026-02-21"]),
    )


def test_cumulative_and_scenario_agree_when_same_day_hits_both():
    """같은 날 익절과 손절을 함께 충족하면 두 판정 경로가 같은 결론을 내야 한다."""
    stock_prices = _one_day_prices(high=120, low=94, close=110)

    metrics = calculate_cumulative_trade_metrics(
        entry_price=100,
        stats_date="2026-02-20",
        stock_prices=stock_prices,
    )
    scenario_return = calculate_scenario_return(
        ticker="005930",
        entry_price=100,
        signal_date="2026-02-20",
        current_price=110,
        price_df=stock_prices,
        stock_prices=stock_prices,
        target_pct=0.09,
        stop_pct=0.05,
    )

    assert metrics["outcome"] == "LOSS"
    assert metrics["roi"] == -5.0
    assert scenario_return == -5.0


def test_cumulative_metrics_win_path_reports_roi_days_and_max_high():
    stock_prices = pd.DataFrame(
        [
            {"high": 104, "low": 99, "close": 103},
            {"high": 112, "low": 102, "close": 110},
            {"high": 130, "low": 120, "close": 128},
        ],
        index=pd.to_datetime(["2026-02-21", "2026-02-22", "2026-02-23"]),
    )

    metrics = calculate_cumulative_trade_metrics(
        entry_price=100,
        stats_date="2026-02-20",
        stock_prices=stock_prices,
    )

    assert metrics["outcome"] == "WIN"
    assert metrics["roi"] == 9.0
    # 익절일에서 거래가 끝나므로 셋째 날의 고가 130 은 어느 값에도 반영되지 않는다.
    assert metrics["days"] == 2
    assert metrics["max_high"] == 12.0
    assert metrics["price_trail"][:2] == [100, 103]
    assert round(metrics["price_trail"][-1], 2) == 109.0


def test_cumulative_metrics_loss_path_trims_trail_at_stop_price():
    stock_prices = pd.DataFrame(
        [
            {"high": 104, "low": 99, "close": 103},
            {"high": 102, "low": 90, "close": 92},
            {"high": 130, "low": 120, "close": 128},
        ],
        index=pd.to_datetime(["2026-02-21", "2026-02-22", "2026-02-23"]),
    )

    metrics = calculate_cumulative_trade_metrics(
        entry_price=100,
        stats_date="2026-02-20",
        stock_prices=stock_prices,
    )

    assert metrics["outcome"] == "LOSS"
    assert metrics["roi"] == -5.0
    assert metrics["days"] == 2
    assert metrics["max_high"] == 4.0
    assert metrics["price_trail"][:2] == [100, 103]
    assert round(metrics["price_trail"][-1], 2) == 95.0


def test_cumulative_metrics_open_path_uses_last_close_for_roi():
    stock_prices = pd.DataFrame(
        [
            {"high": 104, "low": 99, "close": 103},
            {"high": 106, "low": 101, "close": 105},
        ],
        index=pd.to_datetime(["2026-02-21", "2026-02-22"]),
    )

    metrics = calculate_cumulative_trade_metrics(
        entry_price=100,
        stats_date="2026-02-20",
        stock_prices=stock_prices,
    )

    assert metrics["outcome"] == "OPEN"
    assert metrics["roi"] == 5.0
    assert metrics["days"] == 2
    assert metrics["max_high"] == 6.0
    assert metrics["price_trail"] == [100, 103, 105]


def test_cumulative_metrics_follows_the_given_target_and_stop_widths():
    """폭이 본문에 다시 박히면 인자를 바꿔도 판정이 따라오지 않아 여기서 걸린다."""
    stock_prices = _one_day_prices(high=106, low=99, close=105)

    default_metrics = calculate_cumulative_trade_metrics(
        entry_price=100,
        stats_date="2026-02-20",
        stock_prices=stock_prices,
    )
    narrow_target = calculate_cumulative_trade_metrics(
        entry_price=100,
        stats_date="2026-02-20",
        stock_prices=stock_prices,
        target_pct=0.03,
        stop_pct=0.02,
    )
    narrow_stop = calculate_cumulative_trade_metrics(
        entry_price=100,
        stats_date="2026-02-20",
        stock_prices=stock_prices,
        target_pct=0.20,
        stop_pct=0.005,
    )
    # 0.07 은 그냥 곱하면 7.000000000000001 이 되어 화면에 꼬리가 그대로 나간다.
    # 목표가가 107 이므로 고가 106 짜리 위 픽스처로는 익절이 나지 않는다.
    float_tail = calculate_cumulative_trade_metrics(
        entry_price=100,
        stats_date="2026-02-20",
        stock_prices=_one_day_prices(high=112, low=99, close=105),
        target_pct=0.07,
        stop_pct=0.02,
    )

    assert default_metrics["outcome"] == "OPEN"
    assert default_metrics["roi"] == 5.0
    assert narrow_target["outcome"] == "WIN"
    assert narrow_target["roi"] == 3.0
    assert narrow_stop["outcome"] == "LOSS"
    assert narrow_stop["roi"] == -0.5
    assert float_tail["outcome"] == "WIN"
    assert repr(float_tail["roi"]) == "7.0"


def test_earlier_hit_decides_when_target_and_stop_land_on_different_days():
    """익절과 손절이 서로 다른 날 충족되면 먼저 온 쪽이 결론을 정한다."""
    target_first = pd.DataFrame(
        [
            {"high": 112, "low": 105, "close": 110},
            {"high": 100, "low": 90, "close": 92},
        ],
        index=pd.to_datetime(["2026-02-21", "2026-02-22"]),
    )
    stop_first = pd.DataFrame(
        [
            {"high": 104, "low": 90, "close": 92},
            {"high": 130, "low": 120, "close": 128},
        ],
        index=pd.to_datetime(["2026-02-21", "2026-02-22"]),
    )

    win = calculate_cumulative_trade_metrics(
        entry_price=100, stats_date="2026-02-20", stock_prices=target_first
    )
    loss = calculate_cumulative_trade_metrics(
        entry_price=100, stats_date="2026-02-20", stock_prices=stop_first
    )

    assert win["outcome"] == "WIN"
    assert win["days"] == 1
    assert loss["outcome"] == "LOSS"
    assert loss["days"] == 1

    # 시나리오 경로도 같은 데이터에서 같은 방향을 가리켜야 한다.
    for prices, expected in ((target_first, 9.0), (stop_first, -5.0)):
        assert (
            calculate_scenario_return(
                ticker="005930",
                entry_price=100,
                signal_date="2026-02-20",
                current_price=100,
                price_df=prices,
                stock_prices=prices,
                target_pct=0.09,
                stop_pct=0.05,
            )
            == expected
        )


def test_dashboard_and_cumulative_report_the_same_win_rate():
    """대시보드와 누적성과는 같은 시그널 집합에서 같은 승률을 내야 한다.

    두 화면은 서로 다른 함수로 승패를 세므로, 폭이나 우선순위가 한쪽만 바뀌면
    사용자는 같은 시그널을 놓고 어긋난 승률 두 개를 보게 된다.
    """
    from datetime import datetime

    stats_date = "2026-02-20"
    # 동시 충족 / 익절만 / 손절만.
    raw_prices = pd.DataFrame(
        [
            {"date": "2026-02-21", "ticker": "005930", "high": 120, "low": 94, "close": 110},
            {"date": "2026-02-21", "ticker": "000660", "high": 112, "low": 102, "close": 110},
            {"date": "2026-02-21", "ticker": "035420", "high": 102, "low": 90, "close": 92},
        ]
    )
    price_df = prepare_cumulative_price_dataframe(raw_prices)
    price_index = build_ticker_price_index(price_df)
    tickers = ("005930", "000660", "035420")
    signals = [
        {
            "ticker": ticker,
            "stock_code": ticker,
            "entry_price": 100,
            "grade": "S",
            "name": ticker,
            "score": {"total": 10},
        }
        for ticker in tickers
    ]

    dashboard = calculate_jongga_backtest_stats(
        candidates=[],
        history_payloads=[{"date": stats_date, "signals": signals}],
        price_map=dict.fromkeys(tickers, 100.0),
        price_df=price_df,
        price_index=price_index,
    )
    trades = [
        build_cumulative_trade_record(signal, stats_date, price_df, price_index=price_index)
        for signal in signals
    ]
    cumulative = aggregate_cumulative_kpis(trades, price_df, datetime.now())

    assert [trade["outcome"] for trade in trades] == ["LOSS", "WIN", "LOSS"]
    assert dashboard["win_rate"] == cumulative["winRate"] == 33.3


def test_jongga_stats_counts_a_win_when_the_width_carries_a_float_tail(monkeypatch):
    """익절 수익률을 만드는 쪽과 그 값을 재는 쪽이 같은 변환을 써야 승이 사라지지 않는다.

    폭 0.07 은 곱하기만 하면 7.000000000000001 이 되므로, 반환값 7.0 이 기준에
    미치지 못해 익절한 거래가 승으로도 패로도 세어지지 않는다.
    """
    monkeypatch.setattr(stats_helpers, "JONGGA_TARGET_PCT", 0.07)

    raw_prices = pd.DataFrame(
        [{"date": "2026-02-21", "ticker": "005930", "high": 112, "low": 102, "close": 110}]
    )
    price_df = prepare_cumulative_price_dataframe(raw_prices)

    stats = stats_helpers.calculate_jongga_backtest_stats(
        candidates=[],
        history_payloads=[
            {
                "date": "2026-02-20",
                "signals": [{"ticker": "005930", "stock_code": "005930", "entry_price": 100}],
            }
        ],
        price_map={"005930": 100.0},
        price_df=price_df,
        price_index=build_ticker_price_index(price_df),
    )

    assert stats["count"] == 1
    assert stats["win_rate"] == 100.0
