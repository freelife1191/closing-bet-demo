#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KR Market 시그널 헬퍼 공통 유틸리티
"""

from datetime import datetime
from typing import Any, Optional

import pandas as pd

_VALID_AI_ACTIONS = {"BUY", "SELL", "HOLD"}
_INVALID_AI_REASONS = {
    "",
    "-",
    "n/a",
    "na",
    "none",
    "null",
    "분석 실패",
    "분석 대기중",
    "분석 대기 중",
    "분석중",
    "분석 중",
    "no analysis available.",
    "no analysis available",
    "analysis failed",
    "failed",
}


def _normalize_text(value: Any) -> str:
    """문자열 정규화 (None-safe)."""
    if value is None:
        return ""
    return str(value).strip()


def _is_meaningful_ai_reason(reason: Any) -> bool:
    """AI 분석 사유 텍스트가 실질적인 내용인지 판별."""
    reason_text = _normalize_text(reason)
    if not reason_text:
        return False
    return reason_text.lower() not in _INVALID_AI_REASONS


def _safe_float(value: Any, default: float = 0.0) -> float:
    """숫자 변환 실패 시 기본값을 반환한다."""
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    """정수 변환 실패 시 기본값을 반환한다."""
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return default


def _none_if_nan(value: Any) -> Any:
    """NaN 계열 값을 None으로 치환한다."""
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    return value


def _format_signal_date(value: Any) -> str:
    """신호 날짜를 YYYY-MM-DD 형태로 정규화한다."""
    date_str = str(value or "").strip()
    if len(date_str) == 8 and "-" not in date_str and date_str.isdigit():
        return f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"
    return date_str


def _normalize_ai_payload_tickers(payload: Any) -> Any:
    """분석 payload 내 ticker를 6자리 문자열로 정규화한다."""
    if not isinstance(payload, dict):
        return payload

    signals = payload.get("signals")
    if not isinstance(signals, list):
        return payload

    for signal in signals:
        if isinstance(signal, dict) and "ticker" in signal:
            signal["ticker"] = str(signal.get("ticker", "")).zfill(6)

    return payload


def _parse_datetime_safe(value: Any) -> Optional[datetime]:
    """문자열 날짜를 datetime으로 안전하게 변환한다."""
    value_str = str(value or "").strip()
    if not value_str:
        return None

    try:
        return datetime.fromisoformat(value_str)
    except ValueError:
        pass

    for fmt in ("%Y-%m-%d", "%Y%m%d"):
        try:
            return datetime.strptime(value_str, fmt)
        except ValueError:
            continue

    return None
