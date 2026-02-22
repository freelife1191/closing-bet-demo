#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Engine - Pandas Utilities (DataFrame)

Common DataFrame filters, aggregations, and calculation helpers.
"""

import logging
import statistics
from datetime import datetime
from typing import Any, Dict, List, Optional

import pandas as pd

logger = logging.getLogger(__name__)


def filter_by_date(
    df: pd.DataFrame,
    date_column: str,
    target_date: Optional[str] = None,
    date_format: str = '%Y-%m-%d',
) -> pd.DataFrame:
    """날짜로 DataFrame 필터링."""
    if df.empty or date_column not in df.columns:
        return df

    try:
        parsed_dates = pd.to_datetime(df[date_column], format=date_format, errors='coerce')

        if target_date:
            target_dt = pd.to_datetime(target_date, format=date_format)
            return df[parsed_dates <= target_dt]

        latest_date = parsed_dates.max()
        if pd.notna(latest_date):
            return df[parsed_dates == latest_date]
    except Exception as e:
        logger.warning(f"Date filtering failed: {e}")

    return df


def filter_by_ticker(
    df: pd.DataFrame,
    ticker: str,
    ticker_column: str = 'ticker',
    zfill_width: int = 6,
) -> pd.DataFrame:
    """티커로 DataFrame 필터링."""
    if df.empty:
        return pd.DataFrame()

    try:
        tickers = df[ticker_column].astype(str).str.zfill(zfill_width)
        target_ticker = str(ticker).zfill(zfill_width)
        return df[tickers == target_ticker].copy()
    except Exception as e:
        logger.warning(f"Ticker filtering failed: {e}")
        return pd.DataFrame()


def get_latest_values(
    df: pd.DataFrame,
    group_column: str,
    value_columns: List[str],
) -> Dict[str, Any]:
    """그룹별 최신 값 조회 (고속 조회)."""
    if df.empty:
        return {}

    try:
        df_latest = df.drop_duplicates(subset=[group_column], keep='last')
        available_columns = [col for col in value_columns if col in df_latest.columns]
        if available_columns:
            return (
                df_latest[[group_column] + available_columns]
                .set_index(group_column)[available_columns]
                .to_dict(orient='index')
            )

        return {key: {} for key in df_latest[group_column].tolist()}
    except Exception as e:
        logger.error(f"Failed to get latest values: {e}")
        return {}


def create_lookup_map(df: pd.DataFrame, key_column: str, value_column: str) -> Dict[Any, Any]:
    """고속 조회용 맵 생성."""
    if df.empty:
        return {}

    try:
        return (
            df.drop_duplicates(subset=[key_column], keep='last')
            .set_index(key_column)[value_column]
            .to_dict()
        )
    except Exception as e:
        logger.error(f"Failed to create lookup map: {e}")
        return {}


def calculate_return_pct(
    current_price: float,
    entry_price: float,
    round_digits: int = 2,
) -> Optional[float]:
    """수익률 계산."""
    if entry_price and entry_price > 0 and current_price:
        return round(((current_price - entry_price) / entry_price) * 100, round_digits)
    return None


def calculate_volume_ratio(
    current_volume: float,
    historical_volumes: List[float],
    lookback: int = 20,
) -> float:
    """거래량 배수 계산."""
    if not historical_volumes or current_volume <= 0:
        return 1.0

    lookback = min(lookback, len(historical_volumes))
    if lookback == 0:
        return 1.0

    reference_window = historical_volumes[-lookback:]
    baseline_volume = statistics.median(reference_window)

    if baseline_volume > 0:
        return round(current_volume / baseline_volume, 2)
    return 1.0


def get_latest_date_in_df(df: pd.DataFrame, date_column: str = 'date') -> Optional[str]:
    """DataFrame에서 최신 날짜 조회."""
    if df.empty or date_column not in df.columns:
        return None

    try:
        latest = df[date_column].max()
        if pd.notna(latest):
            if isinstance(latest, (datetime, pd.Timestamp)):
                return latest.strftime('%Y-%m-%d')
            return str(latest)[:10]
    except Exception as e:
        logger.warning(f"Failed to get latest date: {e}")

    return None


def parse_date_string(
    date_str: str,
    input_format: str = '%Y-%m-%d',
    output_format: str = '%Y%m%d',
) -> Optional[str]:
    """날짜 문자열 파싱 및 포맷 변환."""
    try:
        dt = datetime.strptime(date_str, input_format)
        return dt.strftime(output_format)
    except ValueError:
        return None


def format_ticker(ticker: Any, width: int = 6) -> str:
    """티커 코드 포맷팅 (0패딩)."""
    return str(ticker).zfill(width)


def filter_open_signals(df: pd.DataFrame, status_column: str = 'status') -> pd.DataFrame:
    """OPEN 상태인 시그널만 필터링."""
    if df.empty or status_column not in df.columns:
        return df

    return df[df[status_column] == 'OPEN'].copy()


def filter_by_min_score(
    df: pd.DataFrame,
    score_column: str = 'score',
    min_score: float = 60.0,
) -> pd.DataFrame:
    """최소 점수 이상인 항목만 필터링."""
    if df.empty or score_column not in df.columns:
        return df

    return df[df[score_column] >= min_score].copy()
