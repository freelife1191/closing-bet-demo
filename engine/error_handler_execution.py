#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Engine - Error Handler Execution Utilities
"""

from __future__ import annotations

import logging
from typing import Any, Callable


logger = logging.getLogger(__name__)


def safe_execute(
    func: Callable,
    *args,
    default: Any = None,
    error_log: bool = True,
    **kwargs,
) -> Any:
    """안전한 함수 실행 (에러 발생 시 기본값 반환)."""
    try:
        return func(*args, **kwargs)
    except Exception as error:
        if error_log:
            logger.debug(f"Error in {func.__name__}: {error}")
        return default


async def safe_execute_async(
    func: Callable,
    *args,
    default: Any = None,
    error_log: bool = True,
    **kwargs,
) -> Any:
    """안전한 비동기 함수 실행."""
    try:
        return await func(*args, **kwargs)
    except Exception as error:
        if error_log:
            logger.debug(f"Error in {func.__name__}: {error}")
        return default


def execute_with_fallback(
    primary_func: Callable,
    fallback_func: Callable,
    *args,
    default: Any = None,
    **kwargs,
) -> Any:
    """기본 함수 실패 시 대체 함수 실행."""
    try:
        return primary_func(*args, **kwargs)
    except Exception as primary_error:
        logger.debug(f"Primary function failed: {primary_error}")
        try:
            return fallback_func(*args, **kwargs)
        except Exception as fallback_error:
            logger.warning(f"Fallback function also failed: {fallback_error}")
            return default


async def execute_with_fallback_async(
    primary_func: Callable,
    fallback_func: Callable,
    *args,
    default: Any = None,
    **kwargs,
) -> Any:
    """비동기 함수의 폴백 실행."""
    try:
        return await primary_func(*args, **kwargs)
    except Exception as primary_error:
        logger.debug(f"Primary async function failed: {primary_error}")
        try:
            return await fallback_func(*args, **kwargs)
        except Exception as fallback_error:
            logger.warning(f"Fallback async function also failed: {fallback_error}")
            return default


__all__ = [
    "safe_execute",
    "safe_execute_async",
    "execute_with_fallback",
    "execute_with_fallback_async",
]
