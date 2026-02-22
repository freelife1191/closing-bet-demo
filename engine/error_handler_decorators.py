#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Engine - Error Handler Decorators
"""

from __future__ import annotations

import asyncio
import logging
from functools import wraps
from typing import Any, Callable, TypeVar

from engine.exceptions import LLMAnalysisError, MarketDataError, ScoringError, is_critical_error


logger = logging.getLogger(__name__)
T = TypeVar("T")


def handle_data_error(
    default_return: Any = None,
    log_level: str = "error",
    raise_on_critical: bool = True,
) -> Callable:
    """데이터 관련 에러 핸들링 데코레이터."""

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            try:
                return func(*args, **kwargs)
            except MarketDataError as error:
                log_func = getattr(logger, log_level, logger.error)
                log_func(f"Data error in {func.__name__}: {error}")
                if is_critical_error(error) and raise_on_critical:
                    raise
                return default_return
            except Exception as error:
                logger.error(f"Unexpected error in {func.__name__}: {error}")
                if raise_on_critical:
                    raise
                return default_return

        return wrapper

    return decorator


def handle_llm_error(
    default_return: Any = None,
    log_level: str = "warning",
) -> Callable:
    """LLM 관련 에러 핸들링 데코레이터."""

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def async_wrapper(*args, **kwargs) -> T:
            try:
                return await func(*args, **kwargs)
            except LLMAnalysisError as error:
                log_func = getattr(logger, log_level, logger.warning)
                log_func(f"LLM error in {func.__name__}: {error}")
                return default_return
            except Exception as error:
                logger.warning(f"Unexpected LLM error in {func.__name__}: {error}")
                return default_return

        @wraps(func)
        def sync_wrapper(*args, **kwargs) -> T:
            try:
                return func(*args, **kwargs)
            except LLMAnalysisError as error:
                log_func = getattr(logger, log_level, logger.warning)
                log_func(f"LLM error in {func.__name__}: {error}")
                return default_return
            except Exception as error:
                logger.warning(f"Unexpected LLM error in {func.__name__}: {error}")
                return default_return

        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper

    return decorator


def handle_scoring_error(
    default_return: Any = None,
    context: str = "",
) -> Callable:
    """스코어링 관련 에러 핸들링 데코레이터."""

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            try:
                return func(*args, **kwargs)
            except ScoringError as error:
                ctx = f" ({context})" if context else ""
                logger.warning(f"Scoring error{ctx} in {func.__name__}: {error}")
                return default_return
            except Exception as error:
                logger.debug(f"Unexpected error in {func.__name__}: {error}")
                return default_return

        return wrapper

    return decorator


__all__ = [
    "handle_data_error",
    "handle_llm_error",
    "handle_scoring_error",
]
