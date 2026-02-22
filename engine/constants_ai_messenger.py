#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Engine - AI/Messenger Constants and Thresholds

AI 분석/뉴스 수집/메신저 포맷팅 관련 상수 모음.
"""

from dataclasses import dataclass
from typing import Final

@dataclass(frozen=True)
class NewsCollectionThresholds:
    """
    뉴스 수집 관련 임계값

    Attributes:
        MAX_NEWS_PER_SOURCE: 소스당 최대 뉴스 수 (5개)
        MAX_TOTAL_NEWS: 총 최대 뉴스 수 (10개)
        MIN_TITLE_LENGTH: 최소 제목 길이 (5글자 미만 제외)
        REQUEST_TIMEOUT: 요청 타임아웃 (초)
        MAX_RETRIES_PER_SOURCE: 소스별 최대 재시도 횟수
    """
    MAX_NEWS_PER_SOURCE: int = 5
    MAX_TOTAL_NEWS: int = 10
    MIN_TITLE_LENGTH: int = 5
    REQUEST_TIMEOUT: int = 10


@dataclass(frozen=True)
class NewsSourceWeights:
    """
    뉴스 소스별 신뢰도 가중치

    Attributes:
        KOREA_ECONOMY: 한국경제 (0.9)
        MK_ECONOMY: 매일경제 (0.9)
        MONEY_TODAY: 머니투데이 (0.85)
        SEOUL_ECONOMY: 서울경제 (0.85)
        EDAILY: 이데일리 (0.85)
        YONHAP: 연합뉴스 (0.85)
        NEWS1: 뉴스1 (0.8)
        DEFAULT: 기본 가중치 (0.7)
    """
    KOREA_ECONOMY: float = 0.9
    MK_ECONOMY: float = 0.9
    MONEY_TODAY: float = 0.85
    SEOUL_ECONOMY: float = 0.85
    EDAILY: float = 0.85
    YONHAP: float = 0.85
    NEWS1: float = 0.8
    DEFAULT: float = 0.7

    def get_weight(self, source: str) -> float:
        """소스명으로 가중치 조회"""
        weight_map = {
            "한국경제": self.KOREA_ECONOMY,
            "매일경제": self.MK_ECONOMY,
            "머니투데이": self.MONEY_TODAY,
            "서울경제": self.SEOUL_ECONOMY,
            "이데일리": self.EDAILY,
            "연합뉴스": self.YONHAP,
            "뉴스1": self.NEWS1,
        }
        return weight_map.get(source, self.DEFAULT)


# =============================================================================
# AI Analysis Mock Data Thresholds
# =============================================================================
@dataclass(frozen=True)
class AIAnalysisThresholds:
    """
    AI 분석 관련 임계값

    Attributes:
        CONFIDENCE_MIN: 최소 신뢰도 (50%)
        CONFIDENCE_MAX: 최대 신뢰도 (95%)
        CONFIDENCE_BUY_MIN: BUY 추천 최소 신뢰도 (75%)
        TARGET_PRICE_RATIO: 목표가 배수 (1.15배)
        STOP_LOSS_RATIO: 손절가 비율 (0.95배)
    """
    CONFIDENCE_MIN: int = 50
    CONFIDENCE_MAX: int = 95
    CONFIDENCE_BUY_MIN: int = 75
    TARGET_PRICE_RATIO: float = 1.15
    STOP_LOSS_RATIO: float = 0.95


# =============================================================================
# Messenger Formatting Thresholds
# =============================================================================
@dataclass(frozen=True)
class MessengerThresholds:
    """
    메신저 포맷팅 관련 임계값

    Attributes:
        TELEGRAM_MAX_LENGTH: 텔레그램 최대 메시지 길이 (4000자)
        DISCORD_FIELD_MAX_LENGTH: 디스코드 필드 최대 길이 (1000자)
        DISCORD_FIELD_TRUNCATE_LENGTH: 디스코드 필드 자르기 길이 (950자)
        AI_REASON_MAX_LENGTH: AI 의견 최대 길이 (60자)
        GRADE_PRIORITY: 등급 우선순위 (S=0, A=1, B=2, D=3)
    """
    TELEGRAM_MAX_LENGTH: int = 4000
    DISCORD_FIELD_MAX_LENGTH: int = 1000
    DISCORD_FIELD_TRUNCATE_LENGTH: int = 950
    AI_REASON_MAX_LENGTH: int = 60

    @property
    def GRADE_PRIORITY(self) -> dict:
        return {
            "S": 0, "A": 1, "B": 2, "D": 3
        }


# =============================================================================
# Singleton instances for easy import (NEW)
# =============================================================================
NEWS_COLLECTION: Final[NewsCollectionThresholds] = NewsCollectionThresholds()
NEWS_SOURCE_WEIGHTS: Final[NewsSourceWeights] = NewsSourceWeights()
AI_ANALYSIS: Final[AIAnalysisThresholds] = AIAnalysisThresholds()
MESSENGER: Final[MessengerThresholds] = MessengerThresholds()
