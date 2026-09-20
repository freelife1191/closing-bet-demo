#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""백테스트와 누적 성과의 공개 진입점. 실제 계산은 각 헬퍼가 담당한다."""

from services.kr_market_backtest_kpi_helpers import (
    aggregate_cumulative_kpis,
    paginate_items,
)
from services.kr_market_backtest_trade_helpers import (
    build_cumulative_trade_record,
    build_ticker_price_index,
    calculate_cumulative_trade_metrics,
    extract_stats_date_from_results_filename,
    prepare_cumulative_price_dataframe,
)
from services.kr_market_backtest_scenario_helpers import (
    build_latest_price_map,
    calculate_scenario_return,
    inject_latest_prices_to_candidates,
)
from services.kr_market_backtest_stats_helpers import (
    calculate_jongga_backtest_stats,
    calculate_vcp_backtest_stats,
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
