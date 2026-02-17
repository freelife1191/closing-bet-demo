#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Engine - Pandas Utilities

Common DataFrame operations and NaN handling utilities.
Eliminates code duplication in data processing.
"""
import pandas as pd
import numpy as np
import logging
from typing import Any, Optional, Dict, List, Union
from datetime import datetime

logger = logging.getLogger(__name__)


# =============================================================================
# Safe Value Extractors (NaN handling)
# =============================================================================
def safe_value(value: Any, default: Any = None) -> Any:
    """
    NaN 값을 안전하게 처리하여 반환

    Args:
        value: 검사할 값
        default: NaN일 경우 반환할 기본값

    Returns:
        값이 NaN이 아니면 원래 값, NaN이면 default

    Example:
        >>> safe_value(float('nan'), 0)
        0
        >>> safe_value(100, 0)
        100
    """
    if pd.isna(value):
        return default
    return value


def safe_int(value: Any, default: int = 0) -> int:
    """
    안전한 정수 변환

    Args:
        value: 변환할 값
        default: 변환 실패 시 기본값

    Returns:
        정수 값

    Example:
        >>> safe_int(123.45)
        123
        >>> safe_int(float('nan'), 0)
        0
    """
    if pd.isna(value):
        return default
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def safe_float(value: Any, default: float = 0.0) -> float:
    """
    안전한 실수 변환

    Args:
        value: 변환할 값
        default: 변환 실패 시 기본값

    Returns:
        실수 값

    Example:
        >>> safe_float("123.45")
        123.45
        >>> safe_float(None, 0.0)
        0.0
    """
    if pd.isna(value):
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def safe_str(value: Any, default: str = "") -> str:
    """
    안전한 문자열 변환

    Args:
        value: 변환할 값
        default: 변환 실패 시 기본값

    Returns:
        문자열 값
    """
    if pd.isna(value):
        return default
    return str(value)


# =============================================================================
# DataFrame Loaders
# =============================================================================
def load_csv_file(
    filepath: str,
    dtype: Optional[Dict[str, Any]] = None,
    usecols: Optional[List[str]] = None,
    low_memory: bool = False
) -> pd.DataFrame:
    """
    CSV 파일 안전하게 로드

    Args:
        filepath: 파일 경로
        dtype: 열 데이터 타입 지정
        usecols: 읽을 열 목록
        low_memory: 메모리 절약 모드

    Returns:
        DataFrame (파일이 없거나 오류 시 빈 DataFrame)
    """
    import os

    if not os.path.exists(filepath):
        logger.warning(f"File not found: {filepath}")
        return pd.DataFrame()

    try:
        return pd.read_csv(
            filepath,
            dtype=dtype,
            usecols=usecols,
            low_memory=low_memory
        )
    except Exception as e:
        logger.error(f"Failed to load CSV {filepath}: {e}")
        return pd.DataFrame()


def load_json_file(filepath: str) -> dict:
    """
    JSON 파일 안전하게 로드

    Args:
        filepath: 파일 경로

    Returns:
        dict (파일이 없거나 오류 시 빈 dict)
    """
    import os
    import json

    if not os.path.exists(filepath):
        logger.debug(f"JSON file not found: {filepath}")
        return {}

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in {filepath}: {e}")
        return {}
    except Exception as e:
        logger.error(f"Failed to load JSON {filepath}: {e}")
        return {}


def save_json_file(
    filepath: str,
    data: dict,
    indent: int = 2,
    ensure_ascii: bool = False
) -> bool:
    """
    JSON 파일 안전하게 저장

    Args:
        filepath: 파일 경로
        data: 저장할 데이터
        indent: 들여쓰기
        ensure_ascii: ASCII 변환 여부

    Returns:
        성공 시 True, 실패 시 False
    """
    import os

    os.makedirs(os.path.dirname(filepath) if os.path.dirname(filepath) else ".", exist_ok=True)

    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=indent, ensure_ascii=ensure_ascii)
        return True
    except Exception as e:
        logger.error(f"Failed to save JSON {filepath}: {e}")
        return False


# =============================================================================
# DataFrame Filters
# =============================================================================
def filter_by_date(
    df: pd.DataFrame,
    date_column: str,
    target_date: Optional[str] = None,
    date_format: str = '%Y-%m-%d'
) -> pd.DataFrame:
    """
    날짜로 DataFrame 필터링

    Args:
        df: 대상 DataFrame
        date_column: 날짜 열 이름
        target_date: 목표 날짜 (None이면 최신 날짜 사용)
        date_format: 날짜 형식

    Returns:
        필터링된 DataFrame
    """
    if df.empty or date_column not in df.columns:
        return df

    try:
        df[date_column] = pd.to_datetime(df[date_column], format=date_format, errors='coerce')

        if target_date:
            target_dt = pd.to_datetime(target_date, format=date_format)
            return df[df[date_column] <= target_dt]
        else:
            # 최신 날짜만 반환
            latest_date = df[date_column].max()
            if pd.notna(latest_date):
                return df[df[date_column] == latest_date]
    except Exception as e:
        logger.warning(f"Date filtering failed: {e}")

    return df


def filter_by_ticker(
    df: pd.DataFrame,
    ticker: str,
    ticker_column: str = 'ticker',
    zfill_width: int = 6
) -> pd.DataFrame:
    """
    티커로 DataFrame 필터링

    Args:
        df: 대상 DataFrame
        ticker: 티커 코드
        ticker_column: 티커 열 이름
        zfill_width: 티커 0패딩 너비

    Returns:
        필터링된 DataFrame
    """
    if df.empty:
        return pd.DataFrame()

    try:
        # 티커 형식 정규화
        df[ticker_column] = df[ticker_column].astype(str).str.zfill(zfill_width)
        return df[df[ticker_column] == ticker.zfill(zfill_width)].copy()
    except Exception as e:
        logger.warning(f"Ticker filtering failed: {e}")
        return pd.DataFrame()


# =============================================================================
# DataFrame Aggregations
# =============================================================================
def get_latest_values(
    df: pd.DataFrame,
    group_column: str,
    value_columns: List[str]
) -> Dict[str, Any]:
    """
    그룹별 최신 값 조회 (고속 조회)

    Args:
        df: 대상 DataFrame
        group_column: 그룹화 열 (예: 'ticker')
        value_columns: 조회할 값 열 목록

    Returns:
        {ticker: {column: value}} 형태의 dict

    Example:
        >>> get_latest_values(df, 'ticker', ['close', 'date'])
        {'005930': {'close': 75000, 'date': '2024-01-15'}, ...}
    """
    if df.empty:
        return {}

    try:
        # 중복 제거 (마지막 값 유지)
        df_latest = df.drop_duplicates(subset=[group_column], keep='last')

        result = {}
        for _, row in df_latest.iterrows():
            key = row[group_column]
            result[key] = {col: row[col] for col in value_columns if col in row}

        return result
    except Exception as e:
        logger.error(f"Failed to get latest values: {e}")
        return {}


def create_lookup_map(
    df: pd.DataFrame,
    key_column: str,
    value_column: str
) -> Dict[Any, Any]:
    """
    고속 조회용 맵 생성

    Args:
        df: 대상 DataFrame
        key_column: 키 열
        value_column: 값 열

    Returns:
        {key: value} dict
    """
    if df.empty:
        return {}

    try:
        return df.drop_duplicates(subset=[key_column], keep='last').set_index(key_column)[value_column].to_dict()
    except Exception as e:
        logger.error(f"Failed to create lookup map: {e}")
        return {}


# =============================================================================
# Data Sanitization (JSON serialization)
# =============================================================================
def sanitize_for_json(data: Any) -> Any:
    """
    JSON 직렬화를 위해 NaN, Infinity 등을 안전한 값으로 변환 (재귀)

    Args:
        data: 변환할 데이터

    Returns:
        JSON 직렬화 가능한 데이터
    """
    if isinstance(data, dict):
        return {k: sanitize_for_json(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [sanitize_for_json(v) for v in data]
    elif isinstance(data, float):
        if np.isnan(data) or np.isinf(data):
            return None
        return data
    return data


def sanitize_dataframe(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """
    DataFrame을 JSON 직렬화 가능한 리스트로 변환

    Args:
        df: 대상 DataFrame

    Returns:
        JSON 직렬화 가능한 dict 리스트
    """
    if df.empty:
        return []

    # NaN을 None으로 변환
    df_clean = df.replace({float('nan'): None})
    return df_clean.to_dict('records')


# =============================================================================
# Price/Return Calculators
# =============================================================================
def calculate_return_pct(
    current_price: float,
    entry_price: float,
    round_digits: int = 2
) -> Optional[float]:
    """
    수익률 계산

    Args:
        current_price: 현재가
        entry_price: 진입가
        round_digits: 반올림 자릿수

    Returns:
        수익률 (%), 계산 불가능 시 None
    """
    if entry_price and entry_price > 0 and current_price:
        return round(((current_price - entry_price) / entry_price) * 100, round_digits)
    return None


def calculate_volume_ratio(
    current_volume: float,
    historical_volumes: List[float],
    lookback: int = 20
) -> float:
    """
    거래량 배수 계산

    Args:
        current_volume: 현재 거래량
        historical_volumes: 과거 거래량 리스트
        lookback: 평균 계산 기간

    Returns:
        거래량 배수
    """
    if not historical_volumes or current_volume <= 0:
        return 1.0

    lookback = min(lookback, len(historical_volumes))
    if lookback == 0:
        return 1.0

    avg_volume = sum(historical_volumes[-lookback:-1]) / (lookback - 1) if lookback > 1 else current_volume

    if avg_volume > 0:
        return round(current_volume / avg_volume, 2)
    return 1.0


# =============================================================================
# Date Utilities
# =============================================================================
def get_latest_date_in_df(df: pd.DataFrame, date_column: str = 'date') -> Optional[str]:
    """
    DataFrame에서 최신 날짜 조회

    Args:
        df: 대상 DataFrame
        date_column: 날짜 열 이름

    Returns:
        최신 날짜 문자열 (YYYY-MM-DD), 없으면 None
    """
    if df.empty or date_column not in df.columns:
        return None

    try:
        latest = df[date_column].max()
        if pd.notna(latest):
            # datetime 형이면 문자열로 변환
            if isinstance(latest, datetime):
                return latest.strftime('%Y-%m-%d')
            return str(latest)[:10]
    except Exception as e:
        logger.warning(f"Failed to get latest date: {e}")

    return None


def parse_date_string(
    date_str: str,
    input_format: str = '%Y-%m-%d',
    output_format: str = '%Y%m%d'
) -> Optional[str]:
    """
    날짜 문자열 파싱 및 포맷 변환

    Args:
        date_str: 입력 날짜 문자열
        input_format: 입력 형식
        output_format: 출력 형식

    Returns:
        변환된 날짜 문자열, 실패 시 None
    """
    try:
        dt = datetime.strptime(date_str, input_format)
        return dt.strftime(output_format)
    except ValueError:
        return None


# =============================================================================
# Ticker Formatting
# =============================================================================
def format_ticker(ticker: Any, width: int = 6) -> str:
    """
    티커 코드 포맷팅 (0패딩)

    Args:
        ticker: 티커 코드
        width: 패딩 너비

    Returns:
        포맷팅된 티커 문자열
    """
    return str(ticker).zfill(width)


# =============================================================================
# Signal/Data Processing Helpers
# =============================================================================
def filter_open_signals(df: pd.DataFrame, status_column: str = 'status') -> pd.DataFrame:
    """
    OPEN 상태인 시그널만 필터링

    Args:
        df: 시그널 DataFrame
        status_column: 상태 열 이름

    Returns:
        OPEN 상태 시그널만 포함된 DataFrame
    """
    if df.empty or status_column not in df.columns:
        return df

    return df[df[status_column] == 'OPEN'].copy()


def filter_by_min_score(
    df: pd.DataFrame,
    score_column: str = 'score',
    min_score: float = 60.0
) -> pd.DataFrame:
    """
    최소 점수 이상인 항목만 필터링

    Args:
        df: 대상 DataFrame
        score_column: 점수 열 이름
        min_score: 최소 점수

    Returns:
        필터링된 DataFrame
    """
    if df.empty or score_column not in df.columns:
        return df

    return df[df[score_column] >= min_score].copy()


def merge_realtime_prices(
    signals: List[Dict[str, Any]],
    price_df: pd.DataFrame,
    price_column: str = 'close',
    date_column: str = 'date',
    ticker_column: str = 'ticker'
) -> List[Dict[str, Any]]:
    """
    시그널 리스트에 실시간 가격 주입

    Args:
        signals: 시그너 리스트
        price_df: 가격 DataFrame
        price_column: 가격 열 이름
        date_column: 날짜 열 이름
        ticker_column: 티커 열 이름

    Returns:
        가격이 업데이트된 시그널 리스트
    """
    if not signals or price_df.empty:
        return signals

    try:
        # 최신 가격 맵 생성
        latest_prices = get_latest_values(
            price_df.drop_duplicates(subset=[ticker_column], keep='last'),
            ticker_column,
            [price_column, date_column]
        )

        # 시그널 업데이트
        for signal in signals:
            ticker = format_ticker(signal.get('ticker', ''))
            if ticker in latest_prices:
                price_data = latest_prices[ticker]
                real_price = safe_float(price_data.get(price_column))

                if real_price > 0:
                    signal['current_price'] = real_price

                    # 수익률 재계산
                    entry_price = safe_float(signal.get('entry_price'))
                    if entry_price and entry_price > 0:
                        signal['return_pct'] = calculate_return_pct(real_price, entry_price)

    except Exception as e:
        logger.warning(f"Failed to merge real-time prices: {e}")

    return signals


# =============================================================================
# Sorting Utilities
# =============================================================================
def sort_signals_by_grade_and_score(
    signals: List[Dict[str, Any]],
    grade_order: Dict[str, int] = None,
    max_count: int = None
) -> List[Dict[str, Any]]:
    """
    등급 및 점수 기준 정렬

    Args:
        signals: 시그널 리스트
        grade_order: 등급 순서 매핑 (높을수록 우선)
        max_count: 최대 반환 개수

    Returns:
        정렬된 시그널 리스트
    """
    if not signals:
        return []

    if grade_order is None:
        grade_order = {"S": 5, "A": 4, "B": 3}

    def sort_key(signal: Dict[str, Any]) -> tuple:
        grade = str(signal.get('grade', '')).strip().upper()
        grade_score = grade_order.get(grade, 0)
        total_score = signal.get('score', {}).get('total', 0) if isinstance(signal.get('score'), dict) else signal.get('score', 0)
        return (grade_score, total_score)

    result = sorted(signals, key=sort_key, reverse=True)

    if max_count:
        result = result[:max_count]

    return result
