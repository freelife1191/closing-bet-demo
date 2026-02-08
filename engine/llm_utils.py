#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Engine - LLM Utilities

Retry logic and common utilities for LLM API calls.
Eliminates duplicate retry code in llm_analyzer.py.
"""
import asyncio
import random
import logging
import time
from typing import Callable, TypeVar, List, Optional, Any, Dict
from functools import wraps

logger = logging.getLogger(__name__)

T = TypeVar('T')


# =============================================================================
# Retry Configuration
# =============================================================================
class RetryConfig:
    """
    재시도 설정

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

    # Common error keywords that indicate transient failures
    RETRY_ON: List[str] = [
        "429",
        "RESOURCE_EXHAUSTED",
        "503",
        "UNAVAILABLE",
        "UNIMPLEMENTED",
        "INTERNAL",
        "OVERLOADED",
        "RATE_LIMIT",
        "TIMEOUT"
    ]


# =============================================================================
# Retry Decorators
# =============================================================================
def async_retry_with_backoff(
    max_retries: int = None,
    base_delay: float = None,
    retry_on: List[str] = None
) -> Callable:
    """
    비동기 함수를 위한 지수 백오프 재시도 데코레이터

    Args:
        max_retries: 최대 재시도 횟수 (None이면 기본값 사용)
        base_delay: 기본 지연 시간 (None이면 기본값 사용)
        retry_on: 재시도할 에러 키워드 목록

    Returns:
        데코레이터 함수

    Example:
        >>> @async_retry_with_backoff(max_retries=3)
        ... async def fetch_data():
        ...     # API call
        ...     pass
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
                except Exception as e:
                    last_exception = e
                    error_msg = str(e).upper()

                    # Check if error is retryable
                    is_retryable = any(keyword in error_msg for keyword in retry_on)

                    if is_retryable and attempt < max_retries - 1:
                        # Calculate delay with exponential backoff
                        delay = min(
                            base_delay * (RetryConfig.BACKOFF_MULTIPLIER ** attempt),
                            RetryConfig.MAX_DELAY
                        )
                        # Add jitter (±20%)
                        jitter = delay * 0.2 * (random.random() * 2 - 1)
                        final_delay = delay + jitter

                        logger.warning(
                            f"[Retry] {func.__name__} failed (attempt {attempt + 1}/{max_retries}): "
                            f"{str(e)[:50]}... Retrying in {final_delay:.1f}s"
                        )
                        await asyncio.sleep(final_delay)
                        continue
                    else:
                        # Non-retryable error or max retries exceeded
                        if not is_retryable:
                            logger.debug(f"[No Retry] {func.__name__} failed with non-retryable error: {e}")
                        raise e

            # Should not reach here, but just in case
            raise last_exception if last_exception else Exception("Max retries exceeded")

        return wrapper
    return decorator


def sync_retry_with_backoff(
    max_retries: int = None,
    base_delay: float = None,
    retry_on: List[str] = None
) -> Callable:
    """
    동기 함수를 위한 지수 백오프 재시도 데코레이터

    Args:
        max_retries: 최대 재시도 횟수
        base_delay: 기본 지연 시간
        retry_on: 재시도할 에러 키워드 목록

    Returns:
        데코레이터 함수

    Example:
        >>> @sync_retry_with_backoff(max_retries=3)
        ... def fetch_data():
        ...     # API call
        ...     pass
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
                except Exception as e:
                    last_exception = e
                    error_msg = str(e).upper()

                    is_retryable = any(keyword in error_msg for keyword in retry_on)

                    if is_retryable and attempt < max_retries - 1:
                        delay = min(
                            base_delay * (RetryConfig.BACKOFF_MULTIPLIER ** attempt),
                            RetryConfig.MAX_DELAY
                        )
                        jitter = delay * 0.2 * (random.random() * 2 - 1)
                        final_delay = delay + jitter

                        logger.warning(
                            f"[Retry] {func.__name__} failed (attempt {attempt + 1}/{max_retries}): "
                            f"{str(e)[:50]}... Retrying in {final_delay:.1f}s"
                        )
                        time.sleep(final_delay)
                        continue
                    else:
                        raise e

            raise last_exception if last_exception else Exception("Max retries exceeded")

        return wrapper
    return decorator


# =============================================================================
# Retry Helper Functions
# =============================================================================
async def retry_async_call(
    func: Callable,
    max_retries: int = None,
    base_delay: float = None,
    retry_on: List[str] = None
) -> Any:
    """
    비동기 함수 호출에 재시도 로직 적용

    Args:
        func: 호출할 비동기 함수
        max_retries: 최대 재시도 횟수
        base_delay: 기본 지연 시간
        retry_on: 재시도할 에러 키워드 목록

    Returns:
        함수 반환 값

    Example:
        >>> result = await retry_async_call(
        ...     lambda: api_client.call(),
        ...     max_retries=3
        ... )
    """
    max_retries = max_retries or RetryConfig.MAX_RETRIES
    base_delay = base_delay or RetryConfig.BASE_DELAY
    retry_on = retry_on or RetryConfig.RETRY_ON

    for attempt in range(max_retries):
        try:
            return await func()
        except Exception as e:
            error_msg = str(e).upper()
            is_retryable = any(keyword in error_msg for keyword in retry_on)

            if is_retryable and attempt < max_retries - 1:
                delay = min(
                    base_delay * (RetryConfig.BACKOFF_MULTIPLIER ** attempt),
                    RetryConfig.MAX_DELAY
                )
                jitter = delay * 0.2 * (random.random() * 2 - 1)
                final_delay = delay + jitter

                logger.warning(
                    f"[Retry] API call failed (attempt {attempt + 1}/{max_retries}): "
                    f"{str(e)[:50]}... Retrying in {final_delay:.1f}s"
                )
                await asyncio.sleep(final_delay)
            else:
                raise e

    raise Exception("Max retries exceeded")


async def retry_blocking_call(
    func: Callable,
    max_retries: int = None,
    base_delay: float = None,
    retry_on: List[str] = None
) -> Any:
    """
    Blocking 호출을 Thread로 분리하여 재시도 로직 적용

    Args:
        func: 호출할 동기 함수
        max_retries: 최대 재시도 횟수
        base_delay: 기본 지연 시간
        retry_on: 재시도할 에러 키워드 목록

    Returns:
        함수 반환 값

    Example:
        >>> result = await retry_blocking_call(
        ...     lambda: client.chat.completions.create(...),
        ...     max_retries=3
        ... )
    """
    max_retries = max_retries or RetryConfig.MAX_RETRIES
    base_delay = base_delay or RetryConfig.BASE_DELAY
    retry_on = retry_on or RetryConfig.RETRY_ON

    for attempt in range(max_retries):
        try:
            return await asyncio.to_thread(func)
        except Exception as e:
            error_msg = str(e).upper()
            is_retryable = any(keyword in error_msg for keyword in retry_on)

            if is_retryable and attempt < max_retries - 1:
                delay = min(
                    base_delay * (RetryConfig.BACKOFF_MULTIPLIER ** attempt),
                    RetryConfig.MAX_DELAY
                )
                jitter = delay * 0.2 * (random.random() * 2 - 1)
                final_delay = delay + jitter

                logger.warning(
                    f"[Retry] Blocking call failed (attempt {attempt + 1}/{max_retries}): "
                    f"{str(e)[:50]}... Retrying in {final_delay:.1f}s"
                )
                await asyncio.sleep(final_delay)
            else:
                raise e

    raise Exception("Max retries exceeded")


# =============================================================================
# Batch Processing Utilities
# =============================================================================
async def process_batch_with_concurrency(
    items: List[Any],
    processor: Callable,
    concurrency: int = 3,
    delay_between_chunks: float = 0.0
) -> List[Any]:
    """
    동시성 제어를 적용한 배치 처리

    Args:
        items: 처리할 항목 리스트
        processor: 비동기 처리 함수 (item을 인자로 받음)
        concurrency: 최대 동시 처리 수
        delay_between_chunks: 청크 간 지연 시간

    Returns:
        처리 결과 리스트

    Example:
        >>> results = await process_batch_with_concurrency(
        ...     stocks,
        ...     lambda stock: analyze_stock(stock),
        ...     concurrency=2
        ... )
    """
    semaphore = asyncio.Semaphore(concurrency)
    results = []

    async def process_with_semaphore(item, index):
        async with semaphore:
            try:
                result = await processor(item)
                return (index, result)
            except Exception as e:
                logger.warning(f"Item {index} processing failed: {e}")
                return (index, None)

    # Create tasks
    tasks = [process_with_semaphore(item, i) for i, item in enumerate(items)]

    # Process in batches
    chunk_size = concurrency
    for i in range(0, len(tasks), chunk_size):
        chunk = tasks[i:i + chunk_size]
        chunk_results = await asyncio.gather(*chunk)
        results.extend(chunk_results)

        # Add delay between chunks (except last chunk)
        if delay_between_chunks > 0 and i + chunk_size < len(tasks):
            await asyncio.sleep(delay_between_chunks)

    # Sort by original index and extract results
    results.sort(key=lambda x: x[0])
    return [r[1] for r in results]


# =============================================================================
# LLM Response Parsing Utilities
# =============================================================================
import re
import json


def extract_json_from_response(response_text: str) -> Optional[dict]:
    """
    LLM 응답에서 JSON 추출 (마크다운 코드 블록 처리)

    Args:
        response_text: LLM 응답 텍스트

    Returns:
        파싱된 dict, 실패 시 None
    """
    if not response_text or not response_text.strip():
        return None

    try:
        # Remove markdown code blocks
        text = response_text.strip()

        # Try to find JSON array
        json_match = re.search(r'\[.*\]', text, re.DOTALL)
        if json_match:
            return json.loads(json_match.group(0))

        # Try to find JSON object
        json_match = re.search(r'\{.*\}', text, re.DOTALL)
        if json_match:
            return json.loads(json_match.group(0))

        # Try to parse entire response as JSON
        return json.loads(text)
    except json.JSONDecodeError as e:
        logger.error(f"JSON parsing failed: {e}")
        return None


def extract_code_block(text: str, language: str = None) -> Optional[str]:
    """
    마크다운 코드 블록 추출

    Args:
        text: 마크다운 텍스트
        language: 언어 지정 (예: "json", "python")

    Returns:
        코드 블록 내용, 없으면 None
    """
    if language:
        pattern = rf'```{language}\s*\n(.*?)\n```'
    else:
        pattern = r'```\s*\n(.*?)\n```'

    match = re.search(pattern, text, re.DOTALL)
    if match:
        return match.group(1).strip()

    return None


# =============================================================================
# Logging Utilities
# =============================================================================
class LLMCallLogger:
    """
    LLM API 호출 로깅 헬퍼

    Usage:
        >>> with LLMCallLogger("Gemini", "sentiment-analysis"):
        ...     result = await api_call()
    """

    def __init__(self, provider: str, operation: str):
        self.provider = provider.upper()
        self.operation = operation
        self.start_time = None

    def __enter__(self):
        self.start_time = time.time()
        logger.info(f"[{self.provider}] Starting {self.operation}...")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        elapsed = time.time() - self.start_time
        if exc_type is None:
            logger.info(f"[{self.provider}] {self.operation} completed in {elapsed:.2f}s")
        else:
            logger.error(f"[{self.provider}] {self.operation} failed after {elapsed:.2f}s: {exc_val}")

    async def __aenter__(self):
        self.start_time = time.time()
        logger.info(f"[{self.provider}] Starting {self.operation}...")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        elapsed = time.time() - self.start_time
        if exc_type is None:
            logger.info(f"[{self.provider}] {self.operation} completed in {elapsed:.2f}s")
        else:
            logger.error(f"[{self.provider}] {self.operation} failed after {elapsed:.2f}s: {exc_val}")


def log_llm_response(provider: str, response_length: int, model: str = None):
    """
    LLM 응답 로깅

    Args:
        provider: 제공자 이름
        response_length: 응답 길이
        model: 모델 이름 (선택)
    """
    model_info = f" (Model: {model})" if model else ""
    logger.info(
        f"[{provider.upper()}] Response received{model_info} "
        f"(Length: {response_length} chars)"
    )


# =============================================================================
# Model Fallback Utilities
# =============================================================================
class ModelFallbackHandler:
    """
    모델 폴백 핸들러

    Usage:
        >>> handler = ModelFallbackHandler({
        ...     'primary': 'gemini-3-flash-preview',
        ...     'fallback': 'gemini-flash-latest'
        ... })
        >>> # Use handler.get_model() to get current model
    """

    def __init__(
        self,
        models: Dict[str, str],
        fallback_errors: List[str] = None
    ):
        """
        Args:
            models: {'primary': 'model-1', 'fallback': 'model-2'}
            fallback_errors: 폴백을 트리거할 에러 키워드
        """
        self.models = models
        self.fallback_errors = fallback_errors or [
            'RESOURCE_EXHAUSTED',
            'OVERLOADED',
            'UNAVAILABLE'
        ]
        self.current_model = models.get('primary')
        self._used_fallback = False

    def should_fallback(self, error: Exception) -> bool:
        """
        폴백이 필요한지 확인

        Args:
            error: 발생한 에러

        Returns:
            폴백 필요 시 True
        """
        if self._used_fallback:
            return False  # Already used fallback

        error_msg = str(error).upper()
        return any(keyword in error_msg for keyword in self.fallback_errors)

    def get_fallback_model(self) -> Optional[str]:
        """
        폴백 모델 반환

        Returns:
            폴백 모델명, 없으면 None
        """
        self._used_fallback = True
        return self.models.get('fallback')

    def get_model(self) -> str:
        """
        현재 모델 반환

        Returns:
            현재 사용할 모델명
        """
        return self.current_model

    def set_model(self, model: str):
        """현재 모델 설정"""
        self.current_model = model

    def reset(self):
        """상태 리셋"""
        self.current_model = self.models.get('primary')
        self._used_fallback = False
