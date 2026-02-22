#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KR Market Data Cache Service 퍼사드
"""

from __future__ import annotations

from services.kr_market_data_cache_core import (
    BACKTEST_PRICE_SNAPSHOT_CACHE,
    CSV_FILE_CACHE,
    FILE_CACHE_LOCK,
    JONGGA_RESULT_PAYLOADS_CACHE,
    JSON_FILE_CACHE,
    LATEST_VCP_PRICE_MAP_CACHE,
    SCANNED_STOCK_COUNT_CACHE,
    atomic_write_text,
    count_total_scanned_stocks,
    file_signature,
    invalidate_file_cache,
    load_csv_file,
    load_json_file,
    load_json_payload_from_path,
)
from services.kr_market_data_cache_jongga import (
    load_jongga_result_payloads,
)
from services.kr_market_data_cache_prices import (
    load_backtest_price_snapshot,
    load_latest_vcp_price_map,
)

__all__ = [
    "FILE_CACHE_LOCK",
    "JSON_FILE_CACHE",
    "CSV_FILE_CACHE",
    "LATEST_VCP_PRICE_MAP_CACHE",
    "SCANNED_STOCK_COUNT_CACHE",
    "BACKTEST_PRICE_SNAPSHOT_CACHE",
    "JONGGA_RESULT_PAYLOADS_CACHE",
    "file_signature",
    "invalidate_file_cache",
    "atomic_write_text",
    "load_json_file",
    "load_json_payload_from_path",
    "load_csv_file",
    "load_latest_vcp_price_map",
    "count_total_scanned_stocks",
    "load_backtest_price_snapshot",
    "load_jongga_result_payloads",
]
