#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Engine - Global Constants and Thresholds

All magic numbers and hardcoded values are centralized here.
This improves maintainability and makes configuration changes easier.

Reference: PART_01.md, PART_07.md documentation
"""
from dataclasses import dataclass
from typing import Final


# =============================================================================
# Trading Value Thresholds (KRW)
# =============================================================================
@dataclass(frozen=True)
class TradingValueThresholds:
    """
    거래대금 관련 임계값 (원)

    Attributes:
        S_GRADE: S급 등급 기준 (1조 원)
        A_GRADE: A급 등급 기준 (5000억 원)
        B_GRADE: B급 등급 기준 (1000억 원)
        MINIMUM: 최소 거래대금 (500억 원) - Phase 1 필터링 기준
        NEWS_FALLBACK_S: 뉴스 없어도 S급으로 처리하는 대형주 기준
        NEWS_FALLBACK_A: 뉴스 없어도 A급으로 처리하는 대형주 기준
        NEWS_FALLBACK_B: 뉴스 없어도 B급으로 처리하는 대형주 기준
    """
    S_GRADE: int = 1_000_000_000_000    # 1조
    A_GRADE: int = 500_000_000_000     # 5000억
    B_GRADE: int = 100_000_000_000     # 1000억
    MINIMUM: int = 50_000_000_000      # 500억

    # News fallback thresholds (V2 Logic - for large caps without news)
    NEWS_FALLBACK_S: int = 500_000_000_000   # 5000억
    NEWS_FALLBACK_A: int = 100_000_000_000   # 1000억
    NEWS_FALLBACK_B: int = 50_000_000_000    # 500억


# =============================================================================
# VCP (Volatility Contraction Pattern) Thresholds
# =============================================================================
@dataclass(frozen=True)
class VCPThresholds:
    """
    VCP 패턴 감지 관련 임계값

    Attributes:
        CONTRACTION_RATIO: 변동성 수축 비율 (0.7 이하면 VCP 인정)
        MIN_SCORE: VCP 패턴으로 인정하는 최소 점수
        MAX_LOOKBACK_DAYS: 분석할 최대 과거 일수
        PRICE_NEAR_HIGH_RATIO: 60일 고가 대비 현재가 비율 (0.85 이상)
        ATR_CONTRACTING: 최근 5일 ATR이 20일 ATR보다 낮아야 함
    """
    CONTRACTION_RATIO: float = 0.7
    MIN_SCORE: int = 50
    MAX_LOOKBACK_DAYS: int = 60
    PRICE_NEAR_HIGH_RATIO: float = 0.85  # Current price >= 85% of 60-day high
    MIN_DATA_POINTS: int = 20  # Minimum data points for VCP analysis


# =============================================================================
# Scoring Thresholds (12-point system + bonus)
# =============================================================================
@dataclass(frozen=True)
class ScoringThresholds:
    """
    점수 계산 관련 임계값

    Attributes:
        BASE_MAX: 기본 점수 최대값 (뉴스 3 + 거래대금 3 + 차트 2 + 캔들 1 + 기간조정 1 + 수급 2)
        BONUS_MAX: 가산점 최대값 (거래량 급증 4 + 장대양봉 5)
        TOTAL_MAX: 총점 최대값
        MIN_C_GRADE: C등급 최소 점수
        MIN_B_GRADE: B등급 최소 점수
        MIN_A_GRADE: A등급 최소 점수
        MIN_S_GRADE: S등급 최소 점수
    """
    BASE_MAX: int = 12
    BONUS_MAX: int = 9
    TOTAL_MAX: int = 21

    # Grade thresholds
    MIN_C_GRADE: int = 4
    MIN_B_GRADE: int = 6
    MIN_A_GRADE: int = 8
    MIN_S_GRADE: int = 10


@dataclass(frozen=True)
class VolumeThresholds:
    """
    거래량 관련 임계값

    Attributes:
        RATIO_MIN: 최소 거래량 배수 (2배 이상)
        RATIO_3X: 3배 이상 (2점)
        RATIO_5X: 5배 이상 (3점)
        RATIO_10X: 10배 이상 (4점)
        LOOKBACK_DAYS: 평균 거래량 계산 기간
    """
    RATIO_MIN: float = 2.0
    RATIO_3X: float = 3.0
    RATIO_5X: float = 5.0
    RATIO_10X: float = 10.0
    LOOKBACK_DAYS: int = 20


@dataclass(frozen=True)
class PriceChangeThresholds:
    """
    등락률 관련 임계값

    Attributes:
        MIN: 최소 등락률 (5%)
        MAX: 최대 등락률 (20%) - 상한가 제외
        LIMIT: 상한가 인근 (29.5% 이상) - 제외 대상
        BONUS_5PCT: 5% 이상 (가산점 1점)
        BONUS_10PCT: 10% 이상 (가산점 2점)
        BONUS_15PCT: 15% 이상 (가산점 3점)
        BONUS_20PCT: 20% 이상 (가산점 4점)
        BONUS_25PCT: 25% 이상 (가산점 5점)
    """
    MIN: float = 5.0
    MAX: float = 20.0
    LIMIT: float = 29.5

    # Bonus points for large gains
    BONUS_5PCT: float = 5.0
    BONUS_10PCT: float = 10.0
    BONUS_15PCT: float = 15.0
    BONUS_20PCT: float = 20.0
    BONUS_25PCT: float = 25.0


# =============================================================================
# FX (Foreign Exchange) Thresholds
# =============================================================================
@dataclass(frozen=True)
class FXThresholds:
    """
    환율 관련 임계값 (원/달러)

    Attributes:
        SAFE: 안전 구간 (1420원 이하)
        WARNING: 경고 구간 (1420~1450원)
        DANGER: 위험 구간 (1450원 이상)
        DEFAULT_FALLBACK: 환율 조회 실패 시 기본값
    """
    SAFE: float = 1420.0
    WARNING: float = 1450.0
    DANGER: float = 1480.0
    DEFAULT_FALLBACK: float = 1350.0


# =============================================================================
# Market Gate Thresholds
# =============================================================================
@dataclass(frozen=True)
class MarketGateThresholds:
    """
    Market Gate 점수 관련 임계값

    Attributes:
        MIN_OPEN: 게이트 오픈 최소 점수
        BULLISH_MIN: 강세장 최소 점수
        BULLISH_STATUS: 강세장 상태명
        NEUTRAL_STATUS: 중립 상태명
        BEARISH_STATUS: 약세장 상태명

        # Technical Indicator Scores
        TREND_SCORE: 추세 점수 (정배열 25점)
        RSI_SCORE: RSI 점수 (50-70 구간 25점)
        MACD_SCORE: MACD 점수 (골든크로스 20점)
        VOLUME_SCORE: 거래량 점수 (15점)
        RS_SCORE: RS 점수 (KOSPI 대비 강세 15점)

        # RSI Thresholds
        RSI_OVERBOUGHT: float = 70.0
        RSI_OVERSOLD: float = 30.0
        RSI_NEUTRAL_MIN: float = 50.0
        RSI_NEUTRAL_MAX: float = 70.0

        # MA Periods
        MA_SHORT: int = 20
        MA_LONG: int = 60

        # RS Score Thresholds
        RS_STRONG: float = 2.0  # >2% outperformance
        RS_WEAK: float = -2.0   # <-2% underperformance
    """
    # Gate Status
    MIN_OPEN: int = 40
    BULLISH_MIN: int = 70

    # Status Labels
    BULLISH_STATUS: str = "Bullish"
    NEUTRAL_STATUS: str = "Neutral"
    BEARISH_STATUS: str = "Bearish"

    # Component Scores
    TREND_SCORE: int = 25
    RSI_SCORE: int = 25
    MACD_SCORE: int = 20
    VOLUME_SCORE: int = 15
    RS_SCORE: int = 15

    # RSI Thresholds
    RSI_OVERBOUGHT: float = 70.0
    RSI_OVERSOLD: float = 30.0
    RSI_NEUTRAL_MIN: float = 50.0

    # MA Periods
    MA_SHORT: int = 20
    MA_LONG: int = 60

    # RS Thresholds
    RS_STRONG: float = 2.0
    RS_WEAK: float = -2.0


# =============================================================================
# Supply (Foreign/Institutional) Thresholds
# =============================================================================
@dataclass(frozen=True)
class SupplyThresholds:
    """
    수급 분석 관련 임계값

    Attributes:
        FOREIGN_LARGE: 대량 외인 순매수 기준 (500억 원)
        FOREIGN_MEDIUM: 중간 외인 순매수 기준 (200억 원)
        INST_LARGE: 대량 기관 순매수 기준 (500억 원)
        INST_MEDIUM: 중간 기관 순매수 기준 (200억 원)
        LOOKBACK_DAYS: 수급 추이 분석 기간 (5일)
    """
    FOREIGN_LARGE: int = 50_000_000_000   # 500억
    FOREIGN_MEDIUM: int = 20_000_000_000  # 200억
    INST_LARGE: int = 50_000_000_000      # 500억
    INST_MEDIUM: int = 20_000_000_000     # 200억
    LOOKBACK_DAYS: int = 5


# =============================================================================
# Bollinger Bands Thresholds (Timing Score)
# =============================================================================
@dataclass(frozen=True)
class BollingerThresholds:
    """
    볼린저 밴드 관련 임계값 (기간조정 점수)

    Attributes:
        PERIOD: 분석 기간 (20일)
        MULTIPLIER: 밴드 폭 배수 (2 표준편차)
        CONTRACTION_RATIO: 수축 판정 비율 (최근 5일이 과거의 80% 이하)
        MIN_WIDTH: 절대 수축 기준 (Band Width < 0.15)
        WINDOW_SIZE: 계산 윈도우 크기
    """
    PERIOD: int = 20
    MULTIPLIER: float = 2.0
    CONTRACTION_RATIO: float = 0.8
    MIN_WIDTH: float = 0.15
    WINDOW_SIZE: int = 20


# =============================================================================
# Candlestick Analysis Thresholds
# =============================================================================
@dataclass(frozen=True)
class CandlestickThresholds:
    """
    캔들형태 분석 관련 임계값

    Attributes:
        BODY_TO_RANGE_RATIO: 장대양봉 판정 비율 (몸통이 전체 범위의 2/3 이상)
        UPPER_SHADOW_RATIO: 윗꼬리 허용 비율 (몸통의 30% 이하)
        DROP_THRESHOLD: 윗꼬리 과다 판정 비율 (몸통의 50% 초과 시 탈락)
        LOOKBACK_CANDLES: 분석할 최근 캔들 수
    """
    BODY_TO_RANGE_RATIO: float = 2.0 / 3.0
    UPPER_SHADOW_RATIO: float = 0.3
    DROP_THRESHOLD: float = 0.5
    LOOKBACK_CANDLES: int = 5


# =============================================================================
# LLM Configuration Thresholds
# =============================================================================
@dataclass(frozen=True)
class LLMThresholds:
    """
    LLM 분석 관련 임계값

    Attributes:
        CHUNK_SIZE_ANALYSIS: 분석용 LLM 청크 크기
        CHUNK_SIZE_GENERAL: 일반용 LLM 청크 크기
        CONCURRENCY_ANALYSIS: 분석용 LLM 동시성
        CONCURRENCY_GENERAL: 일반용 LLM 동시성
        REQUEST_DELAY: 요청 간 지연 시간 (초)
        TIMEOUT_ANALYSIS: 분석용 LLM 타임아웃 (초)
        TIMEOUT_GENERAL: 일반용 LLM 타임아웃 (초)
        MAX_RETRIES: 최대 재시도 횟수
        BASE_RETRY_DELAY: 기본 재시도 지연 (초)
    """
    CHUNK_SIZE_ANALYSIS: int = 5
    CHUNK_SIZE_GENERAL: int = 10
    CONCURRENCY_ANALYSIS: int = 2
    CONCURRENCY_GENERAL: int = 3
    REQUEST_DELAY: float = 2.0
    TIMEOUT_ANALYSIS: int = 120
    TIMEOUT_GENERAL: int = 60
    MAX_RETRIES: int = 5
    BASE_RETRY_DELAY: float = 2.0


# =============================================================================
# News Scoring Thresholds
# =============================================================================
@dataclass(frozen=True)
class NewsThresholds:
    """
    뉴스 점수 관련 임계값

    Attributes:
        MAX_SCORE: 최대 뉴스 점수 (3점)
        SCORE_STRONG: 확실한 호재 (3점)
        SCORE_POSITIVE: 긍정적 호재 (2점)
        SCORE_WEAK: 단순/중립적 소식 (1점)
        MIN_WEIGHT: 가중치 1.0 (일반 뉴스)
        IMPORTANT_WEIGHT: 가중치 1.2 이상 (중요 뉴스)
        MAX_NEWS_PER_STOCK: 종목당 최대 뉴스 수
    """
    MAX_SCORE: int = 3
    SCORE_STRONG: int = 3
    SCORE_POSITIVE: int = 2
    SCORE_WEAK: int = 1
    MIN_WEIGHT: float = 1.0
    IMPORTANT_WEIGHT: float = 1.2
    MAX_NEWS_PER_STOCK: int = 3


# =============================================================================
# Screening Configuration
# =============================================================================
@dataclass(frozen=True)
class ScreeningConfig:
    """
    스크리닝 실행 관련 설정

    Attributes:
        DEFAULT_TOP_N: 기본 상승률 상위 종목 수
        MAX_CANDIDATES: 최대 후보 종목 수
        MIN_PRE_SCORE: 1차 필터 통과 최소 점수
        SIGNALS_TO_SHOW: 사용자에게 표시할 최대 시그널 수
        MARKETS: 분석 대상 시장 목록
    """
    DEFAULT_TOP_N: int = 300
    MAX_CANDIDATES: int = 50
    MIN_PRE_SCORE: int = 2  # Deprecated - using grade-based filtering
    SIGNALS_TO_SHOW: int = 20
    MARKETS: tuple = ("KOSPI", "KOSDAQ")


# =============================================================================
# File Path Constants
# =============================================================================
@dataclass(frozen=True)
class FilePaths:
    """
    데이터 파일 경로 상수

    Attributes:
        DATA_DIR: 데이터 디렉토리 경로
        STOCKS_LIST: 한국 주식 리스트 파일
        DAILY_PRICES: 일별 가격 데이터 파일
        INSTITUTIONAL_TREND: 기관/외인 수급 데이터 파일
        MARKET_GATE: Market Gate 결과 파일
        SIGNALS_LOG: 시그널 로그 파일
        JONGGA_RESULTS: 종가베팅 결과 파일 (날짜 포맷)
        JONGGA_LATEST: 종가베팅 최신 결과 파일
        AI_ANALYSIS: AI 분석 결과 파일
    """
    DATA_DIR: str = "data"
    STOCKS_LIST: str = "korean_stocks_list.csv"
    DAILY_PRICES: str = "daily_prices.csv"
    INSTITUTIONAL_TREND: str = "all_institutional_trend_data.csv"
    MARKET_GATE: str = "market_gate.json"
    SIGNALS_LOG: str = "signals_log.csv"

    # Result file templates
    JONGGA_RESULTS_TEMPLATE: str = "jongga_v2_results_{date}.json"
    JONGGA_LATEST: str = "jongga_v2_latest.json"
    AI_ANALYSIS_TEMPLATE: str = "ai_analysis_results_{date}.json"
    AI_ANALYSIS_LATEST: str = "kr_ai_analysis.json"


# =============================================================================
# Ticker Symbols
# =============================================================================
@dataclass(frozen=True)
class TickerSymbols:
    """
    주요 티커 심볼

    Attributes:
        KODEX_200: KODEX 200 ETF (시장 지표)
        KOSPI_INDEX: KOSPI 지수 (yfinance)
        KOSDAQ_INDEX: KOSDAQ 지수 (yfinance)
        KOSPI_CODE: KOSPI 지수 코드 (pykrx)
        KOSDAQ_CODE: KOSDAQ 지수 코드 (pykrx)
        USD_KRW: 원/달러 환율 (yfinance)
    """
    KODEX_200: str = "069500"
    KOSPI_INDEX: str = "^KS11"
    KOSDAQ_INDEX: str = "^KQ11"
    KOSPI_CODE: str = "1001"
    KOSDAQ_CODE: str = "2001"
    USD_KRW: str = "USDKRW=X"


# =============================================================================
# Grade Labels
# =============================================================================
class GradeLabels:
    """등급 라벨 상수"""
    S: str = "S"
    A: str = "A"
    B: str = "B"
    C: str = "C"
    D: str = "D"

    # Grade order for sorting (higher value = better grade)
    GRADE_ORDER: dict = frozenset({
        "S": 5,
        "A": 4,
        "B": 3,
        "C": 2,
        "D": 1,
    })


# =============================================================================
# Status Labels
# =============================================================================
class StatusLabels:
    """상태 라벨 상수"""
    OPEN: str = "OPEN"
    CLOSED: str = "CLOSED"
    PENDING: str = "PENDING"
    FILLED: str = "FILLED"
    CANCELLED: str = "CANCELLED"


# =============================================================================
# API Response Status
# =============================================================================
class ResponseStatus:
    """API 응답 상태"""
    SUCCESS: str = "success"
    ERROR: str = "error"
    WARNING: str = "warning"
    INFO: str = "info"


# =============================================================================
# Singleton instances for easy import
# =============================================================================
# 사용 편의를 위해 싱글톤 인스턴스 제공
TRADING_VALUES: Final[TradingValueThresholds] = TradingValueThresholds()
VCP_THRESHOLDS: Final[VCPThresholds] = VCPThresholds()
SCORING: Final[ScoringThresholds] = ScoringThresholds()
VOLUME: Final[VolumeThresholds] = VolumeThresholds()
PRICE_CHANGE: Final[PriceChangeThresholds] = PriceChangeThresholds()
FX: Final[FXThresholds] = FXThresholds()
MARKET_GATE: Final[MarketGateThresholds] = MarketGateThresholds()
SUPPLY: Final[SupplyThresholds] = SupplyThresholds()
BOLLINGER: Final[BollingerThresholds] = BollingerThresholds()
CANDLESTICK: Final[CandlestickThresholds] = CandlestickThresholds()
LLM: Final[LLMThresholds] = LLMThresholds()
NEWS: Final[NewsThresholds] = NewsThresholds()
SCREENING: Final[ScreeningConfig] = ScreeningConfig()
FILE_PATHS: Final[FilePaths] = FilePaths()
TICKERS: Final[TickerSymbols] = TickerSymbols()


# =============================================================================
# News Collection Thresholds
# =============================================================================
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
        GRADE_PRIORITY: 등급 우선순위 (S=0, A=1, B=2, C=3, D=4)
    """
    TELEGRAM_MAX_LENGTH: int = 4000
    DISCORD_FIELD_MAX_LENGTH: int = 1000
    DISCORD_FIELD_TRUNCATE_LENGTH: int = 950
    AI_REASON_MAX_LENGTH: int = 60

    @property
    def GRADE_PRIORITY(self) -> dict:
        return frozenset({
            "S": 0, "A": 1, "B": 2, "C": 3, "D": 4
        })


# =============================================================================
# Singleton instances for easy import (NEW)
# =============================================================================
NEWS_COLLECTION: Final[NewsCollectionThresholds] = NewsCollectionThresholds()
NEWS_SOURCE_WEIGHTS: Final[NewsSourceWeights] = NewsSourceWeights()
AI_ANALYSIS: Final[AIAnalysisThresholds] = AIAnalysisThresholds()
MESSENGER: Final[MessengerThresholds] = MessengerThresholds()
