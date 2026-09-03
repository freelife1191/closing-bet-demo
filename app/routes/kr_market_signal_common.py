#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KR Market 시그널 헬퍼 공통 유틸리티
"""

from datetime import datetime
from typing import Any, Optional

import pandas as pd

# 이 두 상수는 프론트엔드에도 같은 내용이 있다. 화면은 병합된 응답이 비면 원시
# 캐시를 다시 보므로, 그쪽에서도 같은 기준으로 실패 기록을 걸러야 한다.
# 여기를 고치면 frontend/src/app/dashboard/kr/vcp/aiHelpers.ts 도 함께 고친다.
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
    """AI 분석 사유 텍스트가 실질적인 내용인지 판별.

    NaN 을 먼저 None 으로 바꾼다. DataFrame 에서 온 빈 칸을 그대로 문자열로
    만들면 "nan" 이 되어, 사유가 없는 행이 사유가 있는 행으로 통과한다.
    """
    reason_text = _normalize_text(_none_if_nan(reason))
    if not reason_text:
        return False
    return reason_text.lower() not in _INVALID_AI_REASONS


# 숫자 문자열에서 떼어 낼 기호. 종가·VCP·수급 경로가 모두 이 목록을 공유한다.
# 경로마다 목록이 다르면 같은 "5%" 가 어디를 지나왔느냐에 따라 5.0 이 되기도 하고
# 0.0 이 되기도 한다.
_NUMERIC_NOISE = str.maketrans("", "", ",₩$%원")


def _normalize_numeric_text(value: Any) -> str:
    """숫자 문자열에서 통화 기호와 단위를 떼어 낸다."""
    return str(value).translate(_NUMERIC_NOISE).strip()


def _safe_float(value: Any, default: float = 0.0) -> float:
    """숫자 변환 실패 시 기본값을 반환한다."""
    if isinstance(value, str):
        value = _normalize_numeric_text(value)
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    """정수 변환 실패 시 기본값을 반환한다."""
    if isinstance(value, str):
        value = _normalize_numeric_text(value)
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return default


def _safe_optional_float(value: Any) -> Optional[float]:
    """변환할 수 없으면 None 을 반환한다.

    `_safe_float` 와 달리 「값이 없음」과 「값이 0」을 구분해야 하는 자리에서 쓴다.
    수급 값을 여러 키에서 차례로 찾을 때, 0 을 못 찾은 것으로 오인하면 다음 키로
    넘어가 엉뚱한 값을 집는다.
    """
    if value is None:
        return None
    if isinstance(value, str):
        normalized = _normalize_numeric_text(value)
        if not normalized:
            return None
        value = normalized
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _normalize_ticker(value: Any) -> str:
    """티커를 6자리 숫자 문자열로 정규화한다. 유효하지 않으면 빈 문자열이다.

    숫자가 하나도 없는 값과 전부 0 인 값을 모두 빈 문자열로 돌린다. 전부 0 인
    코드는 국내 시장에 존재하지 않으며, 결측을 채워 넣은 자리채움이다. 그것을
    `"000000"` 이라는 여섯 자리로 통과시키면 실제 종목코드와 형태가 같아져서,
    가격 맵처럼 티커를 키로 쓰는 자리에서 엉뚱한 값이 매칭된다. 받는 쪽마다
    그 값을 다시 거르는 방어 코드가 생기는 것도 같은 이유다.
    """
    digits = "".join(ch for ch in str(value or "") if ch.isdigit())
    if not digits.strip("0"):
        return ""
    return digits.zfill(6)


def _resolve_ticker(signal: dict, *keys: str) -> str:
    """후보 키를 차례로 보며 처음으로 쓸 수 있는 티커를 돌려준다.

    `or` 로 값을 먼저 고른 뒤 정규화하면 순서가 뒤집힌다. `"0"` 은 빈 값이
    아니라서 `or` 를 통과하고, 그 뒤에 있는 쓸 수 있는 코드를 가린다. 값마다
    정규화를 먼저 해야 자리채움을 건너뛸 수 있다.
    """
    for key in keys:
        ticker = _normalize_ticker(signal.get(key))
        if ticker:
            return ticker
    return ""


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
    if not date_str:
        return ""

    parsed = _parse_datetime_safe(date_str)
    if parsed is not None:
        return parsed.strftime("%Y-%m-%d")

    if len(date_str) == 8 and "-" not in date_str and date_str.isdigit():
        return f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"

    if "T" in date_str:
        return date_str.split("T", 1)[0]
    if " " in date_str:
        return date_str.split(" ", 1)[0]

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

    iso_candidate = value_str
    if iso_candidate.endswith("Z"):
        iso_candidate = iso_candidate[:-1] + "+00:00"

    try:
        return datetime.fromisoformat(iso_candidate)
    except ValueError:
        pass

    for fmt in ("%Y-%m-%d", "%Y%m%d", "%Y/%m/%d"):
        try:
            return datetime.strptime(value_str, fmt)
        except ValueError:
            continue

    return None
