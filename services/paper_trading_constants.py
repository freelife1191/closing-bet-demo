#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Paper Trading 공통 상수.
"""

from __future__ import annotations

INITIAL_CASH_KRW = 100_000_000
DEFAULT_TRADE_HISTORY_LIMIT = 50
DEFAULT_ASSET_HISTORY_LIMIT = 30
MAX_HISTORY_LIMIT = 500

__all__ = [
    "DEFAULT_ASSET_HISTORY_LIMIT",
    "DEFAULT_TRADE_HISTORY_LIMIT",
    "INITIAL_CASH_KRW",
    "MAX_HISTORY_LIMIT",
]
