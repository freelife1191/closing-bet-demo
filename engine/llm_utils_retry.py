#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Engine - LLM Utilities (Retry)
"""

from __future__ import annotations

import asyncio
import logging
import random
import time
from functools import wraps
from typing import Any, Callable, List, TypeVar


logger = logging.getLogger(__name__)
T = TypeVar("T")


class RetryConfig:
    """
    재시도 설정.

    Attributes:
        MAX_RETRIES: 최대 재시도 횟수
        BASE_DELAY: 기본 지연 시간 (초)
        MAX_DELAY: 최대 지연 시간 (초)
        RETRY_ON: 재시도할 에러 키워드 목록
        BACKOFF_MULTIPLIER: 지수 백오프 배수
    """

    MAX_RETRIES: int = 5
    BASE_DELAY: float = 2.0
    MAX_DELAY: float = 60.0
    BACKOFF_MULTIPLIER: float = 2.0
    RETRY_ON: List[str] = [
        "429",
        "RESOURCE_EXHAUSTED",
        "503",
        "UNAVAILABLE",
        "UNIMPLEMENTED",
        "INTERNAL",
        "OVERLOADED",
        "RATE_LIMIT",
        "TIMEOUT",
    ]


def _is_retryable_error(error: Exception, retry_on: List[str]) -> bool:
    error_msg = str(error).upper()
    return any(keyword in error_msg for keyword in retry_on)


def _calculate_backoff_delay(base_delay: float, attempt: int) -> float:
    delay = min(
        base_delay * (RetryConfig.BACKOFF_MULTIPLIER ** attempt),
        RetryConfig.MAX_DELAY,
    )
    jitter = delay * 0.2 * (random.random() * 2 - 1)
    return delay + jitter


def async_retry_with_backoff(
    max_retries: int = None,
    base_delay: float = None,
    retry_on: List[str] = None,
) -> Callable:
    """
    비동기 함수를 위한 지수 백오프 재시도 데코레이터.
    """

    max_retries = max_retries or RetryConfig.MAX_RETRIES
    base_delay = base_delay or RetryConfig.BASE_DELAY
    retry_on = retry_on or RetryConfig.RETRY_ON

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            last_exception = None

            for attempt in range(max_retries):
                try:
                    return await func(*args, **kwargs)
                except Exception as error:
                    last_exception = error
                    is_retryable = _is_retryable_error(error, retry_on)

                    if is_retryable and attempt < max_retries - 1:
                        final_delay = _calculate_backoff_delay(base_delay, attempt)
                        logger.warning(
                            f"[Retry] {func.__name__} failed (attempt {attempt + 1}/{max_retries}): "
                            f"{str(error)[:50]}... Retrying in {final_delay:.1f}s"
                        )
                        await asyncio.sleep(final_delay)
                        continue

                    if not is_retryable:
                        logger.debug(
                            f"[No Retry] {func.__name__} failed with non-retryable error: {error}"
                        )
                    raise error

            raise last_exception if last_exception else Exception("Max retries exceeded")

        return wrapper

    return decorator


def sync_retry_with_backoff(
    max_retries: int = None,
    base_delay: float = None,
    retry_on: List[str] = None,
) -> Callable:
    """
    동기 함수를 위한 지수 백오프 재시도 데코레이터.
    """

    max_retries = max_retries or RetryConfig.MAX_RETRIES
    base_delay = base_delay or RetryConfig.BASE_DELAY
    retry_on = retry_on or RetryConfig.RETRY_ON

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            last_exception = None

            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as error:
                    last_exception = error
                    is_retryable = _is_retryable_error(error, retry_on)

                    if is_retryable and attempt < max_retries - 1:
                        final_delay = _calculate_backoff_delay(base_delay, attempt)
                        logger.warning(
                            f"[Retry] {func.__name__} failed (attempt {attempt + 1}/{max_retries}): "
                            f"{str(error)[:50]}... Retrying in {final_delay:.1f}s"
                        )
                        time.sleep(final_delay)
                        continue

                    raise error

            raise last_exception if last_exception else Exception("Max retries exceeded")

        return wrapper

    return decorator


async def retry_async_call(
    func: Callable,
    max_retries: int = None,
    base_delay: float = None,
    retry_on: List[str] = None,
) -> Any:
    """
    비동기 함수 호출에 재시도 로직 적용.
    """

    max_retries = max_retries or RetryConfig.MAX_RETRIES
    base_delay = base_delay or RetryConfig.BASE_DELAY
    retry_on = retry_on or RetryConfig.RETRY_ON

    for attempt in range(max_retries):
        try:
            return await func()
        except Exception as error:
            is_retryable = _is_retryable_error(error, retry_on)
            if is_retryable and attempt < max_retries - 1:
                final_delay = _calculate_backoff_delay(base_delay, attempt)
                logger.warning(
                    f"[Retry] API call failed (attempt {attempt + 1}/{max_retries}): "
                    f"{str(error)[:50]}... Retrying in {final_delay:.1f}s"
                )
                await asyncio.sleep(final_delay)
                continue
            raise error

    raise Exception("Max retries exceeded")


async def retry_blocking_call(
    func: Callable,
    max_retries: int = None,
    base_delay: float = None,
    retry_on: List[str] = None,
) -> Any:
    """
    Blocking 호출을 Thread로 분리하여 재시도 로직 적용.
    """

    max_retries = max_retries or RetryConfig.MAX_RETRIES
    base_delay = base_delay or RetryConfig.BASE_DELAY
    retry_on = retry_on or RetryConfig.RETRY_ON

    for attempt in range(max_retries):
        try:
            return await asyncio.to_thread(func)
        except Exception as error:
            is_retryable = _is_retryable_error(error, retry_on)
            if is_retryable and attempt < max_retries - 1:
                final_delay = _calculate_backoff_delay(base_delay, attempt)
                logger.warning(
                    f"[Retry] Blocking call failed (attempt {attempt + 1}/{max_retries}): "
                    f"{str(error)[:50]}... Retrying in {final_delay:.1f}s"
                )
                await asyncio.sleep(final_delay)
                continue
            raise error

    raise Exception("Max retries exceeded")


__all__ = [
    "RetryConfig",
    "async_retry_with_backoff",
    "sync_retry_with_backoff",
    "retry_async_call",
    "retry_blocking_call",
]
