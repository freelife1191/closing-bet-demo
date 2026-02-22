#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KR Market Backtest - Common Helpers
"""

from __future__ import annotations

from datetime import datetime
from typing import Any


def safe_float(value: Any, default: float = 0.0) -> float:
    """문자열/None 포함 숫자 입력을 안전하게 float로 변환한다."""
    try:
        if value is None:
            return default
        if isinstance(value, str):
            cleaned = value.replace(",", "").strip()
            if cleaned == "":
                return default
            return float(cleaned)
        return float(value)
    except Exception:
        return default


def format_signal_date(value: Any) -> str:
    """다양한 형식의 날짜 입력을 YYYY-MM-DD 문자열로 정규화한다."""
    if value is None:
        return ""

    value_str = str(value).strip()
    if not value_str:
        return ""

    try:
        return datetime.fromisoformat(value_str).strftime("%Y-%m-%d")
    except Exception:
        pass

    if len(value_str) >= 10 and value_str[4] == "-" and value_str[7] == "-":
        return value_str[:10]

    if len(value_str) == 8 and value_str.isdigit():
        return f"{value_str[:4]}-{value_str[4:6]}-{value_str[6:8]}"

    return value_str[:10]


def determine_backtest_status(win_rate: float) -> str:
    """승률 기반 백테스트 상태를 계산한다."""
    if win_rate == 0:
        return "PENDING"
    if win_rate >= 60:
        return "EXCELLENT"
    if win_rate >= 40:
        return "GOOD"
    return "BAD"
