#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KR Market Backtest - Cumulative Calculators (Facade)
"""

from __future__ import annotations

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

__all__ = [
    "aggregate_cumulative_kpis",
    "build_cumulative_trade_record",
    "build_ticker_price_index",
    "calculate_cumulative_trade_metrics",
    "extract_stats_date_from_results_filename",
    "paginate_items",
    "prepare_cumulative_price_dataframe",
]

