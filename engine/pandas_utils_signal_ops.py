#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Engine - Pandas Utilities (Signal Ops)

Signal list update and sorting helpers.
"""

import logging
from typing import Any, Dict, List, Optional

import pandas as pd

from engine.pandas_utils_dataframe import (
    calculate_return_pct,
    format_ticker,
    get_latest_values,
)
from engine.pandas_utils_safe import safe_float

logger = logging.getLogger(__name__)


def merge_realtime_prices(
    signals: List[Dict[str, Any]],
    price_df: pd.DataFrame,
    price_column: str = 'close',
    date_column: str = 'date',
    ticker_column: str = 'ticker',
) -> List[Dict[str, Any]]:
    """시그널 리스트에 실시간 가격 주입."""
    if not signals or price_df.empty:
        return signals

    try:
        latest_prices = get_latest_values(price_df, ticker_column, [price_column, date_column])

        for signal in signals:
            ticker = format_ticker(signal.get('ticker', ''))
            if ticker not in latest_prices:
                continue

            price_data = latest_prices[ticker]
            real_price = safe_float(price_data.get(price_column))
            if real_price <= 0:
                continue

            signal['current_price'] = real_price
            entry_price = safe_float(signal.get('entry_price'))
            if entry_price and entry_price > 0:
                signal['return_pct'] = calculate_return_pct(real_price, entry_price)

    except Exception as e:
        logger.warning(f"Failed to merge real-time prices: {e}")

    return signals


def sort_signals_by_grade_and_score(
    signals: List[Dict[str, Any]],
    grade_order: Optional[Dict[str, int]] = None,
    max_count: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """등급 및 점수 기준 정렬."""
    if not signals:
        return []

    if grade_order is None:
        grade_order = {'S': 5, 'A': 4, 'B': 3}

    def sort_key(signal: Dict[str, Any]) -> tuple:
        grade = str(signal.get('grade', '')).strip().upper()
        grade_score = grade_order.get(grade, 0)
        raw_score = signal.get('score', 0)
        total_score = raw_score.get('total', 0) if isinstance(raw_score, dict) else raw_score
        return (grade_score, total_score)

    result = sorted(signals, key=sort_key, reverse=True)
    if max_count:
        result = result[:max_count]
    return result
