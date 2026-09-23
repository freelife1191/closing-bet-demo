#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
보유 중 재추천을 누적성과가 어떻게 세는지 고정하는 회귀 테스트 ([FLOW-018])

누적성과는 추천 단위로 센다. 앞선 추천이 청산되기 전에 같은 종목이 다시 추천되어도 두 건을
따로 승패에 넣는다. 이 정의를 바꾸려면 화면 툴팁의 문구도 함께 바꿔야 한다.
"""

from __future__ import annotations

from datetime import datetime

import pandas as pd

from services.kr_market_backtest_kpi_helpers import aggregate_cumulative_kpis
from services.kr_market_backtest_trade_helpers import build_cumulative_trade_record


def test_overlapping_recommendations_of_one_ticker_count_as_two_trades():
    # 09-04 진입(100)분이 09-08 에 익절되기 전인 09-07 에 103 으로 다시 추천되고,
    # 같은 09-08 일봉에서 뒤 건은 손절가(-3%)에 닿는다. AUDIT-FLOW §2.1 의 005935 사례 구조다.
    stock_prices = pd.DataFrame(
        [
            {"high": 103, "low": 101, "close": 103},
            {"high": 106, "low": 99, "close": 100},
        ],
        index=pd.to_datetime(["2026-09-07", "2026-09-08"]),
    )
    price_index = {"005935": stock_prices}
    trades = [
        build_cumulative_trade_record(
            {"ticker": "005935", "entry_price": entry, "grade": "A"},
            stats_date,
            pd.DataFrame(),
            price_index=price_index,
        )
        for stats_date, entry in (("2026-09-04", 100), ("2026-09-07", 103))
    ]

    assert [t["id"] for t in trades] == ["005935-2026-09-04", "005935-2026-09-07"]
    assert [t["outcome"] for t in trades] == ["WIN", "LOSS"]

    kpi = aggregate_cumulative_kpis(trades, pd.DataFrame(), datetime(2026, 9, 23))
    assert (kpi["totalSignals"], kpi["wins"], kpi["losses"], kpi["winRate"]) == (2, 1, 1, 50.0)
