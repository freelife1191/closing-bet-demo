#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Paper Trading 공통 상수.
"""

from __future__ import annotations

INITIAL_CASH_KRW = 100_000_000
MAX_DEPOSIT_PER_REQUEST_KRW = 10_000_000_000
MAX_TOTAL_DEPOSIT_KRW = 1_000_000_000_000
DEFAULT_TRADE_HISTORY_LIMIT = 50
DEFAULT_ASSET_HISTORY_LIMIT = 30
# 거래 내역 등 일반 히스토리 상한 (요청당 행 수)
MAX_HISTORY_LIMIT = 500
# 자산 히스토리는 하루 1건 스냅샷이므로 "전체(ALL=10년)" 조회를 위해 별도 상한을 둔다.
MAX_ASSET_HISTORY_LIMIT = 4000

__all__ = [
    "DEFAULT_ASSET_HISTORY_LIMIT",
    "DEFAULT_TRADE_HISTORY_LIMIT",
    "INITIAL_CASH_KRW",
    "MAX_DEPOSIT_PER_REQUEST_KRW",
    "MAX_TOTAL_DEPOSIT_KRW",
    "MAX_HISTORY_LIMIT",
    "MAX_ASSET_HISTORY_LIMIT",
]
