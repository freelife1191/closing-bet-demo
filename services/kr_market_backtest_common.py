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


# 종가베팅 전략의 익절·손절 폭. 승패를 세는 두 경로가 이 값을 함께 쓴다.
JONGGA_TARGET_PCT = 0.09
JONGGA_STOP_PCT = 0.05


def pct_to_percent(pct: float) -> float:
    """비율을 백분율로 바꾼다.

    수익률을 돌려주는 쪽과 그 값을 임계값과 견주는 쪽이 이 함수를 함께 쓴다.
    한쪽만 반올림하면 0.07 처럼 꼬리가 붙는 폭에서 7.0 >= 7.000000000000001
    이 거짓이 되어, 익절한 거래를 승으로 세지 못한다.
    """
    return round(pct * 100, 1)


def resolve_hit_outcome(*, first_target: Any, first_stop: Any) -> tuple[str, Any]:
    """익절과 손절이 처음 충족된 위치를 받아 승패와 청산 위치를 판정한다.

    두 위치는 서로 비교할 수만 있으면 되므로 정수 인덱스든 날짜든 받는다.
    같은 시점에 둘 다 충족하면 손절을 우선한다. 일봉은 그날 고가와 저가 중
    무엇이 먼저 왔는지 알려주지 않으므로, 알 수 없는 것을 유리한 쪽으로
    가정하지 않는다.
    """
    if first_stop is not None and (first_target is None or first_stop <= first_target):
        return "LOSS", first_stop
    if first_target is not None:
        return "WIN", first_target
    return "OPEN", None
