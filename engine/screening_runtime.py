#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Engine - Screening Runtime Helpers

SCREENING 설정값을 런타임에서 안전하게 파싱한다.
"""

from __future__ import annotations

from typing import Any

from engine.constants import SCREENING


def _coerce_int(value: Any, *, default: int) -> int:
    if isinstance(value, str):
        normalized = value.replace(",", "").strip()
        if not normalized:
            return default
        value = normalized
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _coerce_float(value: Any, *, default: float) -> float:
    if isinstance(value, str):
        normalized = value.replace(",", "").strip()
        if not normalized:
            return default
        value = normalized
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def resolve_vcp_signals_to_show(*, default: int = 20, minimum: int = 1) -> int:
    """VCP 노출 개수 설정을 안전하게 정수로 해석한다."""
    normalized_minimum = max(0, int(minimum))
    normalized_default = max(
        normalized_minimum,
        _coerce_int(default, default=max(normalized_minimum, 20)),
    )
    raw_value = getattr(SCREENING, "VCP_SIGNALS_TO_SHOW", normalized_default)
    parsed = _coerce_int(raw_value, default=normalized_default)
    return max(normalized_minimum, parsed)


def resolve_vcp_min_score(*, default: float = 60.0) -> float:
    """VCP 최소 점수 설정을 안전하게 실수로 해석한다."""
    raw_value = getattr(SCREENING, "VCP_MIN_SCORE", default)
    return _coerce_float(raw_value, default=default)


__all__ = [
    "resolve_vcp_signals_to_show",
    "resolve_vcp_min_score",
]
