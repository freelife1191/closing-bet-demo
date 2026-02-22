#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Engine - Exception Types
"""


class EngineError(Exception):
    """엔진 기본 예외 클래스"""

    def __init__(self, message: str, context: dict = None):
        self.message = message
        self.context = context or {}
        super().__init__(self.message)

    def __str__(self):
        if self.context:
            context_str = ", ".join(f"{k}={v}" for k, v in self.context.items())
            return f"{self.message} ({context_str})"
        return self.message


class MarketDataError(EngineError):
    """시장 데이터 수집 실패"""


class DataFileNotFoundError(MarketDataError):
    """데이터 파일을 찾을 수 없음"""

    def __init__(self, filepath: str):
        super().__init__(f"Data file not found: {filepath}")
        self.filepath = filepath


class DataValidationError(EngineError):
    """데이터 검증 실패"""


class InsufficientDataError(MarketDataError):
    """데이터가 분석에 필요한 최소 개수 미달"""

    def __init__(self, data_type: str, required: int, actual: int):
        super().__init__(
            f"Insufficient {data_type} data: {actual} < {required}",
            {"required": required, "actual": actual},
        )
        self.data_type = data_type
        self.required = required
        self.actual = actual


class LLMAnalysisError(EngineError):
    """LLM 분석 실패"""


class LLMAPIError(LLMAnalysisError):
    """LLM API 호출 실패"""

    def __init__(self, provider: str, message: str):
        super().__init__(f"{provider} API error: {message}")
        self.provider = provider


class LLMResponseParseError(LLMAnalysisError):
    """LLM 응답 파싱 실패"""

    def __init__(self, response_text: str, parse_error: str):
        super().__init__(f"Failed to parse LLM response: {parse_error}")
        self.response_text = response_text[:500]
        self.parse_error = parse_error


class LLMTimeoutError(LLMAnalysisError):
    """LLM API 타임아웃"""

    def __init__(self, provider: str, timeout_seconds: int):
        super().__init__(
            f"{provider} API timeout after {timeout_seconds}s",
            {"timeout": timeout_seconds},
        )
        self.provider = provider
        self.timeout_seconds = timeout_seconds


class LLMRateLimitError(LLMAnalysisError):
    """LLM API 속도 제한 초과"""

    def __init__(self, provider: str, retry_after: int = None):
        super().__init__(
            f"{provider} rate limit exceeded",
            {"retry_after": retry_after},
        )
        self.provider = provider
        self.retry_after = retry_after


class ScoringError(EngineError):
    """점수 계산 실패"""


class InvalidStockDataError(ScoringError):
    """잘못된 주식 데이터"""

    def __init__(self, ticker: str, reason: str):
        super().__init__(f"Invalid data for {ticker}: {reason}")
        self.ticker = ticker
        self.reason = reason


class GradeCalculationError(ScoringError):
    """등급 계산 실패"""


class ScreeningError(EngineError):
    """스크리닝 실패"""


class NoCandidatesError(ScreeningError):
    """스크리닝 후보가 없음"""

    def __init__(self, market: str, reason: str = ""):
        message = f"No candidates found for {market}"
        if reason:
            message += f": {reason}"
        super().__init__(message)
        self.market = market


class AllCandidatesFilteredError(ScreeningError):
    """모든 후보가 필터링됨"""

    def __init__(self, total_count: int, filter_reason: str):
        super().__init__(
            f"All {total_count} candidates were filtered out: {filter_reason}",
            {"total": total_count},
        )
        self.total_count = total_count
        self.filter_reason = filter_reason


class MarketGateError(EngineError):
    """Market Gate 분석 실패"""


class IndicatorCalculationError(MarketGateError):
    """기술적 지표 계산 실패"""

    def __init__(self, indicator: str, reason: str):
        super().__init__(f"Failed to calculate {indicator}: {reason}")
        self.indicator = indicator


class SignalGenerationError(EngineError):
    """시그널 생성 실패"""


class PositionSizingError(SignalGenerationError):
    """포지션 사이징 실패"""


class EntryPriceCalculationError(SignalGenerationError):
    """진입가 계산 실패"""


class ConfigurationError(EngineError):
    """설정 오류"""


class MissingConfigError(ConfigurationError):
    """필수 설정 값 누락"""

    def __init__(self, config_key: str):
        super().__init__(f"Missing required configuration: {config_key}")
        self.config_key = config_key


class InvalidConfigError(ConfigurationError):
    """잘못된 설정 값"""

    def __init__(self, config_key: str, value: object, expected_type: str):
        super().__init__(
            f"Invalid configuration value for {config_key}: {value} (expected {expected_type})"
        )
        self.config_key = config_key
        self.value = value
        self.expected_type = expected_type


class NetworkError(EngineError):
    """네트워크 오류"""


class APIConnectionError(NetworkError):
    """API 연결 실패"""

    def __init__(self, endpoint: str):
        super().__init__(f"Failed to connect to API endpoint: {endpoint}")
        self.endpoint = endpoint


class APIAuthenticationError(NetworkError):
    """API 인증 실패"""

    def __init__(self, service: str):
        super().__init__(f"Authentication failed for {service}")
        self.service = service


class UserActionError(EngineError):
    """사용자 작업 중단/요청"""


class ScreeningStoppedError(UserActionError):
    """사용자가 스크리닝 중단"""

