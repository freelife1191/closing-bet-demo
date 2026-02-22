#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Engine - Error Handler (Facade)

표준화된 에러 핸들링 유틸리티 공개 API를 재노출한다.
"""

from engine.error_handler_context import ErrorHandler
from engine.error_handler_decorators import (
    handle_data_error,
    handle_llm_error,
    handle_scoring_error,
)
from engine.error_handler_execution import (
    execute_with_fallback,
    execute_with_fallback_async,
    safe_execute,
    safe_execute_async,
)
from engine.error_handler_logging import log_error, log_warning
from engine.error_handler_response import build_error_response, build_success_response
from engine.error_handler_validation import validate_positive, validate_range, validate_required

__all__ = [
    "handle_data_error",
    "handle_llm_error",
    "handle_scoring_error",
    "log_error",
    "log_warning",
    "safe_execute",
    "safe_execute_async",
    "execute_with_fallback",
    "execute_with_fallback_async",
    "validate_required",
    "validate_range",
    "validate_positive",
    "build_error_response",
    "build_success_response",
    "ErrorHandler",
]
