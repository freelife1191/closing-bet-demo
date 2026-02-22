#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Engine - Error Handler Response Builders
"""

from __future__ import annotations

from typing import Any

from engine.exceptions import EngineError, get_error_category, is_critical_error, is_retryable_error


def build_error_response(
    error: Exception,
    status_code: int = 500,
    include_details: bool = False,
) -> dict:
    """API 에러 응답 빌더."""
    _ = status_code
    response = {
        "error": True,
        "message": str(error),
        "type": type(error).__name__,
        "category": get_error_category(error),
    }

    if include_details:
        response["details"] = {
            "retryable": is_retryable_error(error),
            "critical": is_critical_error(error),
        }

        if isinstance(error, EngineError) and error.context:
            response["context"] = error.context

    return response


def build_success_response(data: Any, message: str = None) -> dict:
    """API 성공 응답 빌더."""
    response = {"error": False, "data": data}
    if message:
        response["message"] = message
    return response


__all__ = ["build_error_response", "build_success_response"]
