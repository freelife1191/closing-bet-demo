#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Engine - Custom Exceptions (Facade)
"""

from __future__ import annotations

from engine.exceptions_types import (
    APIAuthenticationError,
    APIConnectionError,
    AllCandidatesFilteredError,
    ConfigurationError,
    DataFileNotFoundError,
    DataValidationError,
    EngineError,
    EntryPriceCalculationError,
    GradeCalculationError,
    IndicatorCalculationError,
    InsufficientDataError,
    InvalidConfigError,
    InvalidStockDataError,
    LLMAPIError,
    LLMAnalysisError,
    LLMRateLimitError,
    LLMResponseParseError,
    LLMTimeoutError,
    MarketDataError,
    MarketGateError,
    MissingConfigError,
    NetworkError,
    NoCandidatesError,
    PositionSizingError,
    ScoringError,
    ScreeningError,
    ScreeningStoppedError,
    SignalGenerationError,
    UserActionError,
)
from engine.exceptions_utils import (
    get_error_category,
    is_critical_error,
    is_retryable_error,
)

__all__ = [
    "APIAuthenticationError",
    "APIConnectionError",
    "AllCandidatesFilteredError",
    "ConfigurationError",
    "DataFileNotFoundError",
    "DataValidationError",
    "EngineError",
    "EntryPriceCalculationError",
    "GradeCalculationError",
    "IndicatorCalculationError",
    "InsufficientDataError",
    "InvalidConfigError",
    "InvalidStockDataError",
    "LLMAPIError",
    "LLMAnalysisError",
    "LLMRateLimitError",
    "LLMResponseParseError",
    "LLMTimeoutError",
    "MarketDataError",
    "MarketGateError",
    "MissingConfigError",
    "NetworkError",
    "NoCandidatesError",
    "PositionSizingError",
    "ScoringError",
    "ScreeningError",
    "ScreeningStoppedError",
    "SignalGenerationError",
    "UserActionError",
    "get_error_category",
    "is_critical_error",
    "is_retryable_error",
]

