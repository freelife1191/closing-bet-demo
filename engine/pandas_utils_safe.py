#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Engine - Pandas Utilities (Safe Values)

NaN/Inf-safe value conversion and JSON sanitization helpers.
"""

import logging
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def safe_value(value: Any, default: Any = None) -> Any:
    """NaN 값을 안전하게 처리하여 반환."""
    if pd.isna(value):
        return default
    return value


def safe_int(value: Any, default: int = 0) -> int:
    """안전한 정수 변환."""
    if pd.isna(value):
        return default
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def safe_float(value: Any, default: float = 0.0) -> float:
    """안전한 실수 변환."""
    if pd.isna(value):
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def safe_confidence(value: Any) -> Optional[int]:
    """AI 확신도를 0~100 정수로 정규화하고, 값이 없으면 None 을 반환한다.

    `safe_int` 와 달리 「값이 없음」과 「확신도 0」을 구분한다. 없는 값을 0 으로 채우면
    화면은 그 자리에 "AI 가 0% 확신한다" 는 막대를 그리고, 사용자는 AI 가 실제로 0 을
    낸 경우와 구분하지 못한다.

    LLM 이 확신도를 "80" 이나 "80%" 처럼 문자열로 내는 경로가 있어 그 형태도 받는다.
    """
    # pd.isna 는 None 도 결측으로 보지만, 리스트나 배열을 받으면 배열을 돌려주므로
    # if 문에서 예외가 난다.
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass

    if isinstance(value, str):
        value = value.replace("%", "").replace(",", "").strip()
        if not value:
            return None

    try:
        numeric = int(float(value))
    except (TypeError, ValueError, OverflowError):
        # inf 는 OverflowError 를 내는데 그것은 ValueError 가 아니라 ArithmeticError 의
        # 하위다. json.loads 가 `Infinity` 를 예외 없이 통과시키므로 LLM 응답으로 실제
        # 들어올 수 있고, 여기서 새면 배치 전체가 AI 분석을 잃는다.
        return None
    return max(0, min(100, numeric))


def safe_str(value: Any, default: str = "") -> str:
    """안전한 문자열 변환."""
    if pd.isna(value):
        return default
    return str(value)


_TRUE_STRINGS = {"1", "true", "yes", "y", "on"}


def safe_bool(value: Any, default: bool = False) -> bool:
    """CSV/DataFrame에서 읽은 불리언 값을 일관되게 해석한다."""
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    if value is None:
        return default
    try:
        if pd.isna(value):
            return default
    except (TypeError, ValueError):
        pass
    if isinstance(value, (int, float, np.integer, np.floating)):
        return bool(value)
    return str(value).strip().lower() in _TRUE_STRINGS


def sanitize_for_json(data: Any) -> Any:
    """JSON 직렬화를 위해 NaN, Infinity 등을 안전한 값으로 변환 (재귀)."""
    if isinstance(data, dict):
        return {k: sanitize_for_json(v) for k, v in data.items()}
    # tuple 도 함께 받는다. json 은 tuple 을 배열로 직렬화하므로, 여기서 걸러 두지
    # 않으면 그 안의 NaN 이 그대로 응답에 실린다.
    if isinstance(data, (list, tuple)):
        return [sanitize_for_json(v) for v in data]
    if isinstance(data, float):
        if np.isnan(data) or np.isinf(data):
            return None
        return data
    return data


def sanitize_dataframe(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """DataFrame을 JSON 직렬화 가능한 리스트로 변환."""
    if df.empty:
        return []

    # NaN을 None으로 변환
    df_clean = df.replace({float('nan'): None})
    return df_clean.to_dict('records')
