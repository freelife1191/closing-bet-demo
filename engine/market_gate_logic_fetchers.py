#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Engine - Market Gate Logic Fetchers (Facade)
"""

from __future__ import annotations

from engine.market_gate_fetchers_external import (
    fetch_benchmark_data,
    get_global_data,
    get_sector_data,
    get_usd_krw,
)
from engine.market_gate_fetchers_local import (
    load_price_data,
    load_supply_data,
)

__all__ = [
    "fetch_benchmark_data",
    "get_global_data",
    "get_sector_data",
    "load_price_data",
    "get_usd_krw",
    "load_supply_data",
]

