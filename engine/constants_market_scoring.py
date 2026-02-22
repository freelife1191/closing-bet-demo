#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Engine - Market Constants (Scoring/Thresholds)
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TradingValueThresholds:
    """거래대금 관련 임계값 (원)"""

    S_GRADE: int = 1_000_000_000_000
    A_GRADE: int = 500_000_000_000
    B_GRADE: int = 100_000_000_000
    MINIMUM: int = 100_000_000_000

    NEWS_FALLBACK_S: int = 500_000_000_000
    NEWS_FALLBACK_A: int = 100_000_000_000
    NEWS_FALLBACK_B: int = 100_000_000_000


@dataclass(frozen=True)
class VCPThresholds:
    """VCP 패턴 감지 관련 임계값"""

    CONTRACTION_RATIO: float = 0.7
    MIN_SCORE: int = 50
    MAX_LOOKBACK_DAYS: int = 60
    PRICE_NEAR_HIGH_RATIO: float = 0.85
    MIN_DATA_POINTS: int = 20


@dataclass(frozen=True)
class ScoringThresholds:
    """점수 계산 관련 임계값"""

    BASE_MAX: int = 12
    BONUS_MAX: int = 7
    TOTAL_MAX: int = 19

    MIN_C_GRADE: int = 8
    MIN_B_GRADE: int = 10
    MIN_A_GRADE: int = 12
    MIN_S_GRADE: int = 15


@dataclass(frozen=True)
class VolumeThresholds:
    """거래량 관련 임계값"""

    RATIO_MIN: float = 2.0
    RATIO_4X: float = 4.0
    RATIO_3X: float = 3.0
    RATIO_5X: float = 5.0
    RATIO_6X: float = 6.0
    RATIO_10X: float = 10.0
    LOOKBACK_DAYS: int = 20


@dataclass(frozen=True)
class PriceChangeThresholds:
    """등락률 관련 임계값"""

    MIN: float = 5.0
    MAX: float = 20.0
    LIMIT: float = 29.5

    BONUS_5PCT: float = 5.0
    BONUS_10PCT: float = 10.0
    BONUS_15PCT: float = 15.0
    BONUS_20PCT: float = 20.0
    BONUS_25PCT: float = 25.0


@dataclass(frozen=True)
class SupplyThresholds:
    """수급 분석 관련 임계값"""

    FOREIGN_LARGE: int = 50_000_000_000
    FOREIGN_MEDIUM: int = 20_000_000_000
    INST_LARGE: int = 50_000_000_000
    INST_MEDIUM: int = 20_000_000_000
    LOOKBACK_DAYS: int = 5


@dataclass(frozen=True)
class BollingerThresholds:
    """볼린저 밴드 관련 임계값"""

    PERIOD: int = 20
    MULTIPLIER: float = 2.0
    CONTRACTION_RATIO: float = 0.8
    MIN_WIDTH: float = 0.15
    WINDOW_SIZE: int = 20


@dataclass(frozen=True)
class CandlestickThresholds:
    """캔들형태 분석 관련 임계값"""

    BODY_TO_RANGE_RATIO: float = 2.0 / 3.0
    UPPER_SHADOW_RATIO: float = 0.3
    DROP_THRESHOLD: float = 0.5
    LOOKBACK_CANDLES: int = 5


@dataclass(frozen=True)
class NewsThresholds:
    """뉴스 점수 관련 임계값"""

    MAX_SCORE: int = 3
    SCORE_STRONG: int = 3
    SCORE_POSITIVE: int = 2
    SCORE_WEAK: int = 1
    MIN_WEIGHT: float = 1.0
    IMPORTANT_WEIGHT: float = 1.2
    MAX_NEWS_PER_STOCK: int = 3


__all__ = [
    "BollingerThresholds",
    "CandlestickThresholds",
    "NewsThresholds",
    "PriceChangeThresholds",
    "ScoringThresholds",
    "SupplyThresholds",
    "TradingValueThresholds",
    "VCPThresholds",
    "VolumeThresholds",
]
