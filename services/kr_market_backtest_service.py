#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KR Market Backtest/Cumulative Service (Compatibility Layer)

실제 계산 로직은 `services.kr_market_backtest_calculators`로 분리되었다.
기존 import 경로 호환을 위해 동일 API를 재노출한다.
"""

from services.kr_market_backtest_calculators import (
    aggregate_cumulative_kpis,
    build_cumulative_trade_record,
    build_latest_price_map,
    build_ticker_price_index,
    calculate_cumulative_trade_metrics,
    calculate_jongga_backtest_stats,
    calculate_scenario_return,
    calculate_vcp_backtest_stats,
    extract_stats_date_from_results_filename,
    inject_latest_prices_to_candidates,
    paginate_items,
    prepare_cumulative_price_dataframe,
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
