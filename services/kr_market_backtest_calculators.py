#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KR Market Backtest/Cumulative Service

누적 성과/백테스트 계산 로직의 호환 레이어.
"""

from services.kr_market_backtest_cumulative import (
    aggregate_cumulative_kpis,
    build_cumulative_trade_record,
    build_ticker_price_index,
    calculate_cumulative_trade_metrics,
    extract_stats_date_from_results_filename,
    paginate_items,
    prepare_cumulative_price_dataframe,
)
from services.kr_market_backtest_signal_stats import (
    build_latest_price_map,
    calculate_jongga_backtest_stats,
    calculate_scenario_return,
    calculate_vcp_backtest_stats,
    inject_latest_prices_to_candidates,
)

__all__ = [
    "aggregate_cumulative_kpis",
    "build_cumulative_trade_record",
    "build_latest_price_map",
    "build_ticker_price_index",
    "calculate_cumulative_trade_metrics",
    "calculate_jongga_backtest_stats",
    "calculate_scenario_return",
    "calculate_vcp_backtest_stats",
    "extract_stats_date_from_results_filename",
    "inject_latest_prices_to_candidates",
    "paginate_items",
    "prepare_cumulative_price_dataframe",
]
