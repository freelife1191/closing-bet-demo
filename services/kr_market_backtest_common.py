#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KR Market Backtest - Common Helpers
"""

from __future__ import annotations

import logging
import math
from datetime import datetime
from typing import Any

from engine.constants_market import JONGGA_STOP_PCT, JONGGA_TARGET_PCT


logger = logging.getLogger(__name__)


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


def determine_backtest_status(win_rate: float, closed_trades: int) -> str:
    """승률과 종료 거래 수로 백테스트 상태를 판정한다.

    승률 0 은 서로 다른 두 상황에서 나온다. 승 0건에 패 N건인 전패와, 종료된
    거래가 한 건도 없어 승률을 계산할 수조차 없는 미집계다. 앞의 것은 성적이
    가장 나쁜 구간이고 뒤의 것은 아직 판정할 수 없는 구간이므로 갈라 놓는다.
    """
    if closed_trades <= 0:
        return "PENDING"
    if win_rate >= 60:
        return "EXCELLENT"
    if win_rate >= 40:
        return "GOOD"
    return "BAD"


def resolve_jongga_exit_prices(
    entry_price: Any,
    target_price: Any = None,
    stop_price: Any = None,
) -> tuple[float, float]:
    """저장 가격을 우선하고 유효하지 않은 한쪽만 종가 기본값으로 보충한다."""
    entry = safe_float(entry_price, default=0.0)
    if not math.isfinite(entry) or entry <= 0:
        logger.warning("Invalid jongga entry price while resolving exits: %r", entry_price)
        return 0.0, 0.0

    default_target = entry * (1 + JONGGA_TARGET_PCT)
    default_stop = entry * (1 - JONGGA_STOP_PCT)
    candidate_target = safe_float(target_price, default=0.0)
    candidate_stop = safe_float(stop_price, default=0.0)
    valid_target = math.isfinite(candidate_target) and candidate_target > entry
    valid_stop = math.isfinite(candidate_stop) and 0 < candidate_stop < entry

    if target_price is None:
        logger.info("Missing jongga target price; using default")
    if stop_price is None:
        logger.info("Missing jongga stop price; using default")
    if target_price is not None and not valid_target:
        logger.warning("Invalid jongga target price; using default: %r", target_price)
    if stop_price is not None and not valid_stop:
        logger.warning("Invalid jongga stop price; using default: %r", stop_price)

    return (
        candidate_target if valid_target else default_target,
        candidate_stop if valid_stop else default_stop,
    )


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
