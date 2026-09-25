#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Engine - Toss Collector Numeric Helpers
"""

from __future__ import annotations

import math
from typing import Any


def normalize_result_payload(data: Any) -> Any:
    if isinstance(data, dict):
        return data.get("result", data)
    return data


def to_float(value: Any) -> float:
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    if not isinstance(value, str):
        return 0.0

    cleaned = value.strip()
    if not cleaned:
        return 0.0
    cleaned = cleaned.replace(",", "")
    cleaned = cleaned.replace("배", "")
    cleaned = cleaned.replace("%", "")
    try:
        return float(cleaned)
    except ValueError:
        return 0.0


def optional_volume(value: Any) -> float | None:
    """[INFRA-109] 순매수 수량을 읽는다. 비었거나 숫자가 아니면 0 이 아니라 None 이다."""
    if value is None or isinstance(value, bool):
        return None
    try:
        volume = float(str(value).replace(",", "").strip())
    except ValueError:
        return None
    return volume if math.isfinite(volume) else None


def to_int(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        try:
            return int(float(value.replace(",", "").strip()))
        except ValueError:
            return 0
    return 0


def compute_change(close: Any, base: Any) -> int:
    close_val = to_int(close)
    base_val = to_int(base)
    return close_val - base_val


def compute_change_pct(close: Any, base: Any) -> float:
    close_val = to_float(close)
    base_val = to_float(base)
    if base_val == 0:
        return 0.0
    return (close_val - base_val) / base_val * 100.0


def normalize_ticker_code(raw_code: Any) -> str:
    code = str(raw_code or "")
    if code.startswith("A"):
        return code[1:]
    return code

