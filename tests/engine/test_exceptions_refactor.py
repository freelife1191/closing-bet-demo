#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
exceptions 퍼사드/유틸 리팩토링 회귀 테스트
"""

from __future__ import annotations

from engine.exceptions import (
    APIAuthenticationError,
    APIConnectionError,
    DataValidationError,
    EngineError,
    LLMRateLimitError,
    MarketDataError,
    UserActionError,
    get_error_category,
    is_critical_error,
    is_retryable_error,
)


def test_get_error_category_maps_known_errors():
    assert get_error_category(MarketDataError("market down")) == "DATA"
    assert get_error_category(UserActionError("stop")) == "USER"
    assert get_error_category(RuntimeError("x")) == "UNKNOWN"


def test_retryable_and_critical_flags_work():
    assert is_retryable_error(LLMRateLimitError("gemini", retry_after=1)) is True
    assert is_retryable_error(EngineError("generic")) is False

    assert is_critical_error(DataValidationError("invalid schema")) is True
    assert is_critical_error(APIAuthenticationError("service")) is True
    assert is_critical_error(APIConnectionError("endpoint")) is False

