#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Engine - Error Handler

표준화된 에러 핸들링 유틸리티
"""
import logging
import traceback
from typing import Any, Callable, Optional, TypeVar
from functools import wraps
from engine.exceptions import (
    EngineError,
    MarketDataError,
    LLMAnalysisError,
    ScoringError,
    is_retryable_error,
    is_critical_error,
    get_error_category
)

logger = logging.getLogger(__name__)

T = TypeVar('T')


# =============================================================================
# Error Handling Decorators
# =============================================================================
def handle_data_error(
    default_return: Any = None,
    log_level: str = "error",
    raise_on_critical: bool = True
) -> Callable:
    """
    데이터 관련 에러 핸들링 데코레이터

    Args:
        default_return: 에러 발생 시 반환할 기본값
        log_level: 로그 레벨 (debug, info, warning, error)
        raise_on_critical: 치명적 에러 시 재발생 여부

    Example:
        >>> @handle_data_error(default_return=pd.DataFrame())
        ... def load_stock_data(ticker):
        ...     # Data loading logic
        ...     pass
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            try:
                return func(*args, **kwargs)
            except MarketDataError as e:
                log_func = getattr(logger, log_level, logger.error)
                log_func(f"Data error in {func.__name__}: {e}")
                if is_critical_error(e) and raise_on_critical:
                    raise
                return default_return
            except Exception as e:
                logger.error(f"Unexpected error in {func.__name__}: {e}")
                if raise_on_critical:
                    raise
                return default_return
        return wrapper
    return decorator


def handle_llm_error(
    default_return: Any = None,
    log_level: str = "warning"
) -> Callable:
    """
    LLM 관련 에러 핸들링 데코레이터

    Args:
        default_return: 에러 발생 시 반환할 기본값
        log_level: 로그 레벨

    Example:
        >>> @handle_llm_error(default_return=None)
        ... async def analyze_sentiment(news):
        ...     # LLM analysis logic
        ...     pass
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def async_wrapper(*args, **kwargs) -> T:
            try:
                return await func(*args, **kwargs)
            except LLMAnalysisError as e:
                log_func = getattr(logger, log_level, logger.warning)
                log_func(f"LLM error in {func.__name__}: {e}")
                return default_return
            except Exception as e:
                logger.warning(f"Unexpected LLM error in {func.__name__}: {e}")
                return default_return

        @wraps(func)
        def sync_wrapper(*args, **kwargs) -> T:
            try:
                return func(*args, **kwargs)
            except LLMAnalysisError as e:
                log_func = getattr(logger, log_level, logger.warning)
                log_func(f"LLM error in {func.__name__}: {e}")
                return default_return
            except Exception as e:
                logger.warning(f"Unexpected LLM error in {func.__name__}: {e}")
                return default_return

        # Return appropriate wrapper based on whether function is async
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    return decorator


def handle_scoring_error(
    default_return: Any = None,
    context: str = ""
) -> Callable:
    """
    스코어링 관련 에러 핸들링 데코레이터

    Args:
        default_return: 에러 발생 시 반환할 기본값
        context: 추가 컨텍스트 정보

    Example:
        >>> @handle_scoring_error(default_return=ScoreDetail())
        ... def calculate_score(stock):
        ...     # Scoring logic
        ...     pass
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            try:
                return func(*args, **kwargs)
            except ScoringError as e:
                ctx = f" ({context})" if context else ""
                logger.warning(f"Scoring error{ctx} in {func.__name__}: {e}")
                return default_return
            except Exception as e:
                logger.debug(f"Unexpected error in {func.__name__}: {e}")
                return default_return
        return wrapper
    return decorator


# =============================================================================
# Error Logging Utilities
# =============================================================================
def log_error(
    error: Exception,
    context: str = "",
    include_traceback: bool = False
):
    """
    에러 로깅

    Args:
        error: 예외 객체
        context: 추가 컨텍스트
        include_traceback: 스택 트레이스 포함 여부
    """
    category = get_error_category(error)
    ctx = f" [{context}]" if context else ""

    if include_traceback:
        logger.error(
            f"[{category}]{ctx} {type(error).__name__}: {error}\n"
            f"{traceback.format_exc()}"
        )
    else:
        logger.error(f"[{category}]{ctx} {type(error).__name__}: {error}")


def log_warning(error: Exception, context: str = ""):
    """
    경고 로깅

    Args:
        error: 예외 객체
        context: 추가 컨텍스트
    """
    category = get_error_category(error)
    ctx = f" [{context}]" if context else ""
    logger.warning(f"[{category}]{ctx} {type(error).__name__}: {error}")


# =============================================================================
# Safe Execution Utilities
# =============================================================================
def safe_execute(
    func: Callable,
    *args,
    default: Any = None,
    error_log: bool = True,
    **kwargs
) -> Any:
    """
    안전한 함수 실행 (에러 발생 시 기본값 반환)

    Args:
        func: 실행할 함수
        *args: 위치 인자
        default: 에러 발생 시 기본값
        error_log: 에러 로깅 여부
        **kwargs: 키워드 인자

    Returns:
        함수 반환 값 또는 기본값

    Example:
        >>> result = safe_execute(
        ...     risky_function,
        ...     arg1, arg2,
        ...     default=0,
        ...     error_log=True
        ... )
    """
    try:
        return func(*args, **kwargs)
    except Exception as e:
        if error_log:
            logger.debug(f"Error in {func.__name__}: {e}")
        return default


async def safe_execute_async(
    func: Callable,
    *args,
    default: Any = None,
    error_log: bool = True,
    **kwargs
) -> Any:
    """
    안전한 비동기 함수 실행

    Args:
        func: 실행할 비동기 함수
        *args: 위치 인자
        default: 에러 발생 시 기본값
        error_log: 에러 로깅 여부
        **kwargs: 키워드 인자

    Returns:
        함수 반환 값 또는 기본값
    """
    try:
        return await func(*args, **kwargs)
    except Exception as e:
        if error_log:
            logger.debug(f"Error in {func.__name__}: {e}")
        return default


# =============================================================================
# Fallback Utilities
# =============================================================================
def execute_with_fallback(
    primary_func: Callable,
    fallback_func: Callable,
    *args,
    default: Any = None,
    **kwargs
) -> Any:
    """
    기본 함수 실패 시 대체 함수 실행

    Args:
        primary_func: 기본 함수
        fallback_func: 대체 함수
        *args: 위치 인자
        default: 모두 실패 시 기본값
        **kwargs: 키워드 인자

    Returns:
        함수 반환 값 또는 기본값

    Example:
        >>> result = execute_with_fallback(
        ...     load_from_fdr,
        ...     load_from_pykrx,
        ...     ticker="005930",
        ...     default=None
        ... )
    """
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
    **kwargs
) -> Any:
    """
    비동기 함수의 폴백 실행

    Args:
        primary_func: 기본 비동기 함수
        fallback_func: 대체 비동기 함수
        *args: 위치 인자
        default: 모두 실패 시 기본값
        **kwargs: 키워드 인자
    """
    try:
        return await primary_func(*args, **kwargs)
    except Exception as primary_error:
        logger.debug(f"Primary async function failed: {primary_error}")
        try:
            return await fallback_func(*args, **kwargs)
        except Exception as fallback_error:
            logger.warning(f"Fallback async function also failed: {fallback_error}")
            return default


# =============================================================================
# Validation Utilities
# =============================================================================
def validate_required(value: Any, name: str) -> None:
    """
    필수 값 검증

    Args:
        value: 검증할 값
        name: 값 이름 (에러 메시지용)

    Raises:
        ValueError: 값이 None이거나 비어있는 경우
    """
    if value is None:
        raise ValueError(f"{name} is required but was None")
    if isinstance(value, (str, list, dict)) and not value:
        raise ValueError(f"{name} is required but was empty")


def validate_range(
    value: float,
    name: str,
    min_val: float = None,
    max_val: float = None
) -> None:
    """
    범위 검증

    Args:
        value: 검증할 값
        name: 값 이름
        min_val: 최소값 (None이면 검증 안 함)
        max_val: 최대값 (None이면 검증 안 함)

    Raises:
        ValueError: 범위를 벗어난 경우
    """
    if min_val is not None and value < min_val:
        raise ValueError(f"{name} ({value}) is below minimum ({min_val})")
    if max_val is not None and value > max_val:
        raise ValueError(f"{name} ({value}) is above maximum ({max_val})")


def validate_positive(value: float, name: str) -> None:
    """
    양수 검증

    Args:
        value: 검증할 값
        name: 값 이름

    Raises:
        ValueError: 0 이하인 경우
    """
    if value is not None and value <= 0:
        raise ValueError(f"{name} must be positive, got {value}")


# =============================================================================
# Error Response Builders
# =============================================================================
def build_error_response(
    error: Exception,
    status_code: int = 500,
    include_details: bool = False
) -> dict:
    """
    API 에러 응답 빌더

    Args:
        error: 예외 객체
        status_code: HTTP 상태 코드
        include_details: 상세 에러 정보 포함 여부

    Returns:
        에러 응답 dict
    """
    response = {
        "error": True,
        "message": str(error),
        "type": type(error).__name__,
        "category": get_error_category(error)
    }

    if include_details:
        response["details"] = {
            "retryable": is_retryable_error(error),
            "critical": is_critical_error(error)
        }

        if isinstance(error, EngineError) and error.context:
            response["context"] = error.context

    return response


def build_success_response(data: Any, message: str = None) -> dict:
    """
    API 성공 응답 빌더

    Args:
        data: 반환할 데이터
        message: 성공 메시지 (선택)

    Returns:
        성공 응답 dict
    """
    response = {"error": False, "data": data}
    if message:
        response["message"] = message
    return response


# =============================================================================
# Context Manager for Error Handling
# =============================================================================
class ErrorHandler:
    """
    에러 핸들링 컨텍스트 매니저

    Example:
        >>> with ErrorHandler("Data loading", default_return=pd.DataFrame()):
        ...     data = load_from_csv(filepath)
    """

    def __init__(
        self,
        operation: str,
        default_return: Any = None,
        raise_on: tuple = (),
        log_level: str = "error"
    ):
        self.operation = operation
        self.default_return = default_return
        self.raise_on = raise_on
        self.log_level = log_level
        self.error = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            self.error = exc_val

            # Check if error should be raised
            if isinstance(exc_val, self.raise_on):
                return False  # Re-raise

            # Log error
            log_func = getattr(logger, self.log_level, logger.error)
            log_func(f"[{self.operation}] {exc_type.__name__}: {exc_val}")

            return True  # Suppress error
        return False

    def get_result(self):
        """결과 반환 (에러 발생 시 기본값)"""
        if self.error:
            return self.default_return
        return None
