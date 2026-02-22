#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Engine - Pandas Utilities

Backwards-compatible facade that re-exports pandas helper APIs.
"""

from engine.pandas_utils_dataframe import (
    calculate_return_pct,
    calculate_volume_ratio,
    create_lookup_map,
    filter_by_date,
    filter_by_min_score,
    filter_by_ticker,
    filter_open_signals,
    format_ticker,
    get_latest_date_in_df,
    get_latest_values,
    parse_date_string,
)
from engine.pandas_utils_io import load_csv_file, load_json_file, save_json_file
from engine.pandas_utils_safe import (
    safe_float,
    safe_int,
    safe_str,
    safe_value,
    sanitize_dataframe,
    sanitize_for_json,
)
from engine.pandas_utils_signal_ops import (
    merge_realtime_prices,
    sort_signals_by_grade_and_score,
)

__all__ = [
    'safe_value',
    'safe_int',
    'safe_float',
    'safe_str',
    'load_csv_file',
    'load_json_file',
    'save_json_file',
    'filter_by_date',
    'filter_by_ticker',
    'get_latest_values',
    'create_lookup_map',
    'sanitize_for_json',
    'sanitize_dataframe',
    'calculate_return_pct',
    'calculate_volume_ratio',
    'get_latest_date_in_df',
    'parse_date_string',
    'format_ticker',
    'filter_open_signals',
    'filter_by_min_score',
    'merge_realtime_prices',
    'sort_signals_by_grade_and_score',
]
