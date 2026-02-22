#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Engine - Market Constants (System/Labels/File Paths)
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FXThresholds:
    """환율 관련 임계값 (원/달러)"""

    SAFE: float = 1420.0
    WARNING: float = 1450.0
    DANGER: float = 1480.0
    DEFAULT_FALLBACK: float = 1350.0


@dataclass(frozen=True)
class MarketGateThresholds:
    """Market Gate 점수 관련 임계값"""

    MIN_OPEN: int = 40
    BULLISH_MIN: int = 70

    BULLISH_STATUS: str = "Bullish"
    NEUTRAL_STATUS: str = "Neutral"
    BEARISH_STATUS: str = "Bearish"

    TREND_SCORE: int = 25
    RSI_SCORE: int = 25
    MACD_SCORE: int = 20
    VOLUME_SCORE: int = 15
    RS_SCORE: int = 15

    RSI_OVERBOUGHT: float = 70.0
    RSI_OVERSOLD: float = 30.0
    RSI_NEUTRAL_MIN: float = 50.0

    MA_SHORT: int = 20
    MA_LONG: int = 60

    RS_STRONG: float = 2.0
    RS_WEAK: float = -2.0


@dataclass(frozen=True)
class LLMThresholds:
    """LLM 분석 관련 임계값"""

    CHUNK_SIZE_ANALYSIS: int = 5
    CHUNK_SIZE_GENERAL: int = 10
    CONCURRENCY_ANALYSIS: int = 2
    CONCURRENCY_GENERAL: int = 3
    REQUEST_DELAY: float = 2.0
    TIMEOUT_ANALYSIS: int = 120
    TIMEOUT_GENERAL: int = 60
    MAX_RETRIES: int = 5
    BASE_RETRY_DELAY: float = 2.0


@dataclass(frozen=True)
class ScreeningConfig:
    """스크리닝 실행 관련 설정"""

    DEFAULT_TOP_N: int = 300
    MAX_CANDIDATES: int = 50
    MIN_PRE_SCORE: int = 2
    SIGNALS_TO_SHOW: int = 20
    MARKETS: tuple = ("KOSPI", "KOSDAQ")


@dataclass(frozen=True)
class FilePaths:
    """데이터 파일 경로 상수"""

    DATA_DIR: str = "data"
    STOCKS_LIST: str = "korean_stocks_list.csv"
    DAILY_PRICES: str = "daily_prices.csv"
    INSTITUTIONAL_TREND: str = "all_institutional_trend_data.csv"
    MARKET_GATE: str = "market_gate.json"
    SIGNALS_LOG: str = "signals_log.csv"

    JONGGA_RESULTS_TEMPLATE: str = "jongga_v2_results_{date}.json"
    JONGGA_LATEST: str = "jongga_v2_latest.json"
    AI_ANALYSIS_TEMPLATE: str = "ai_analysis_results_{date}.json"
    AI_ANALYSIS_LATEST: str = "kr_ai_analysis.json"


@dataclass(frozen=True)
class TickerSymbols:
    """주요 티커 심볼"""

    KODEX_200: str = "069500"
    KOSPI_INDEX: str = "^KS11"
    KOSDAQ_INDEX: str = "^KQ11"
    KOSPI_CODE: str = "1001"
    KOSDAQ_CODE: str = "2001"
    USD_KRW: str = "USDKRW=X"


class GradeLabels:
    """등급 라벨 상수"""

    S: str = "S"
    A: str = "A"
    B: str = "B"
    C: str = "C"
    D: str = "D"

    GRADE_ORDER: dict = frozenset({
        "S": 5,
        "A": 4,
        "B": 3,
        "C": 2,
        "D": 1,
    })


class StatusLabels:
    """상태 라벨 상수"""

    OPEN: str = "OPEN"
    CLOSED: str = "CLOSED"
    PENDING: str = "PENDING"
    FILLED: str = "FILLED"
    CANCELLED: str = "CANCELLED"


class ResponseStatus:
    """API 응답 상태"""

    SUCCESS: str = "success"
    ERROR: str = "error"
    WARNING: str = "warning"
    INFO: str = "info"


__all__ = [
    "FXThresholds",
    "FilePaths",
    "GradeLabels",
    "LLMThresholds",
    "MarketGateThresholds",
    "ResponseStatus",
    "ScreeningConfig",
    "StatusLabels",
    "TickerSymbols",
]

