#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KR Market Signal Common 유틸 리팩토링 테스트
"""

from __future__ import annotations

from app.routes.kr_market_signal_common import (
    _format_signal_date,
    _is_meaningful_ai_reason,
    _none_if_nan,
    _normalize_ai_payload_tickers,
    _normalize_text,
    _parse_datetime_safe,
    _safe_float,
    _safe_int,
)


def test_safe_number_converters_return_default_on_invalid_values():
    assert _safe_float("12.5") == 12.5
    assert _safe_float("₩1,234.5%") == 1234.5
    assert _safe_float("bad", default=1.5) == 1.5

    assert _safe_int("12") == 12
    assert _safe_int("$1,234%") == 1234
    assert _safe_int("bad", default=3) == 3


def test_none_if_nan_returns_none_only_for_nan_values():
    assert _none_if_nan(float("nan")) is None
    assert _none_if_nan(0) == 0
    assert _none_if_nan("text") == "text"


def test_normalize_and_reason_helpers():
    assert _normalize_text(None) == ""
    assert _normalize_text("  abc  ") == "abc"

    assert _is_meaningful_ai_reason("분석 실패") is False
    assert _is_meaningful_ai_reason("수급 개선") is True


def test_format_signal_date_supports_compact_and_iso():
    assert _format_signal_date("20260221") == "2026-02-21"
    assert _format_signal_date("2026-02-21") == "2026-02-21"
    assert _format_signal_date("2026-02-21 00:00:00") == "2026-02-21"
    assert _format_signal_date("2026-02-21T15:30:00Z") == "2026-02-21"


def test_normalize_ai_payload_tickers_updates_signal_items():
    payload = {"signals": [{"ticker": "5930"}, {"ticker": "000660"}]}

    normalized = _normalize_ai_payload_tickers(payload)

    assert normalized["signals"][0]["ticker"] == "005930"
    assert normalized["signals"][1]["ticker"] == "000660"


def test_parse_datetime_safe_handles_supported_formats_and_invalid_input():
    assert _parse_datetime_safe("2026-02-21") is not None
    assert _parse_datetime_safe("20260221") is not None
    assert _parse_datetime_safe("2026-02-21T10:30:00") is not None
    assert _parse_datetime_safe("2026-02-21T10:30:00Z") is not None
    assert _parse_datetime_safe("invalid") is None
