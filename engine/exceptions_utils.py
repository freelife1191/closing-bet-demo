#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Engine - Exception Utilities
"""

from __future__ import annotations

from engine.exceptions_types import (
    APIAuthenticationError,
    APIConnectionError,
    ConfigurationError,
    DataFileNotFoundError,
    DataValidationError,
    InvalidStockDataError,
    LLMAPIError,
    LLMAnalysisError,
    LLMRateLimitError,
    LLMResponseParseError,
    LLMTimeoutError,
    MarketDataError,
    NetworkError,
    NoCandidatesError,
    ScoringError,
    ScreeningError,
    UserActionError,
)

_DATA_ERRORS = (MarketDataError, DataFileNotFoundError, DataValidationError)
_LLM_ERRORS = (LLMAnalysisError, LLMAPIError, LLMResponseParseError)
_SCORING_ERRORS = (ScoringError, InvalidStockDataError)
_SCREENING_ERRORS = (ScreeningError, NoCandidatesError)
_NETWORK_ERRORS = (NetworkError, APIConnectionError)
_RETRYABLE_ERRORS = (LLMRateLimitError, LLMTimeoutError, NetworkError, APIConnectionError)
_CRITICAL_ERRORS = (
    ConfigurationError,
    APIAuthenticationError,
    DataValidationError,
    DataFileNotFoundError,
)


def get_error_category(error: Exception) -> str:
    """예외 카테고리 반환."""
    if isinstance(error, _DATA_ERRORS):
        return "DATA"
    if isinstance(error, _LLM_ERRORS):
        return "LLM"
    if isinstance(error, _SCORING_ERRORS):
        return "SCORING"
    if isinstance(error, _SCREENING_ERRORS):
        return "SCREENING"
    if isinstance(error, _NETWORK_ERRORS):
        return "NETWORK"
    if isinstance(error, UserActionError):
        return "USER"
    return "UNKNOWN"


def is_retryable_error(error: Exception) -> bool:
    """재시도 가능한 에러인지 확인."""
    return isinstance(error, _RETRYABLE_ERRORS)


def is_critical_error(error: Exception) -> bool:
    """치명적 에러인지 확인 (즉시 중단 필요)."""
    return isinstance(error, _CRITICAL_ERRORS)
