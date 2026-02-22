#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Engine - Pandas Utilities (Safe Values)

NaN/Inf-safe value conversion and JSON sanitization helpers.
"""

import logging
from typing import Any, Dict, List

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


def safe_str(value: Any, default: str = "") -> str:
    """안전한 문자열 변환."""
    if pd.isna(value):
        return default
    return str(value)


def sanitize_for_json(data: Any) -> Any:
    """JSON 직렬화를 위해 NaN, Infinity 등을 안전한 값으로 변환 (재귀)."""
    if isinstance(data, dict):
        return {k: sanitize_for_json(v) for k, v in data.items()}
    if isinstance(data, list):
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
