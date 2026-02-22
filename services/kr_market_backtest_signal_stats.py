#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KR Market Backtest - Scenario/Stats Calculators (Facade)
"""

from __future__ import annotations

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
    "build_latest_price_map",
    "inject_latest_prices_to_candidates",
    "calculate_scenario_return",
    "calculate_jongga_backtest_stats",
    "calculate_vcp_backtest_stats",
]

