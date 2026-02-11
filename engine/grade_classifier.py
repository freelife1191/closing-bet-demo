#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Grade Classifier Module

등급 판정 로직을 분리한 모듈입니다.
FilterValidator와 GradeClassifier로 나뉘어 있습니다.

Created: 2025-02-11 (Phase 4 Refactoring)
"""
import logging
from typing import Optional
from dataclasses import dataclass

from engine.models import StockData, ScoreDetail, Grade, ChartData, SupplyData
from engine.config import SignalConfig
from engine.constants import VOLUME, PRICE_CHANGE

logger = logging.getLogger(__name__)


# =============================================================================
# Filter Result
# =============================================================================
@dataclass
class FilterResult:
    """
    필터링 결과

    Attributes:
        passed: 통과 여부
        reason: 실패 사유 (passed=False인 경우)
    """
    passed: bool
    reason: Optional[str] = None


# =============================================================================
# Filter Validator
# =============================================================================
class FilterValidator:
    """
    필터링 조건 검증기

    종목이 시그널 생성 대상으로 적합한지 검증합니다.
    모든 조건을 통과해야 등급 판정 대상이 됩니다.
    """

    def __init__(self, config: SignalConfig = None):
        """
        초기화

        Args:
            config: (Optional) SignalConfig 인스턴스
        """
        self.config = config or SignalConfig()

    def validate(
        self,
        stock: StockData,
        score: ScoreDetail,
        score_details: dict,
        supply: SupplyData,
        charts: ChartData,
        allow_no_news: bool = False
    ) -> FilterResult:
        """
        종목 필터링 검증

        Args:
            stock: 종목 데이터
            score: 점수 상세
            score_details: 점수 상세 딕셔너리
            supply: 수급 데이터
            charts: 차트 데이터
            allow_no_news: 뉴스 없음 허용 여부 (Phase 1 선별용)

        Returns:
            FilterResult 객체
        """
        trading_value = stock.trading_value
        change_pct = stock.change_pct
        volume_ratio = score_details.get('volume_ratio', 0.0)

        # 1. 거래대금 필터
        result = self._validate_trading_value(trading_value)
        if not result.passed:
            return result

        # 2. 등락률 필터
        result = self._validate_price_change(change_pct)
        if not result.passed:
            return result

        # 3. 뉴스 필터
        result = self._validate_news(score.news, allow_no_news)
        if not result.passed:
            return result

        # 4. 윗꼬리 필터
        result = self._validate_upper_shadow(charts)
        if not result.passed:
            return result

        # 5. 거래량 배수 필터
        result = self._validate_volume_ratio(volume_ratio)
        if not result.passed:
            return result

        # 모든 필터 통과
        return FilterResult(passed=True)

    def _validate_trading_value(self, trading_value: int) -> FilterResult:
        """
        거래대금 필터 (500억 이상)

        Args:
            trading_value: 거래대금

        Returns:
            FilterResult
        """
        min_value = self.config.trading_value_min  # 500억
        if trading_value < min_value:
            return FilterResult(
                passed=False,
                reason=f"거래대금 부족: {trading_value//100_000_000}억 < {min_value//100_000_000}억"
            )
        return FilterResult(passed=True)

    def _validate_price_change(self, change_pct: float) -> FilterResult:
        """
        등락률 필터 (5~30% 이내)

        Args:
            change_pct: 등락률

        Returns:
            FilterResult
        """
        if not (PRICE_CHANGE.MIN <= change_pct <= PRICE_CHANGE.MAX):
            return FilterResult(
                passed=False,
                reason=f"등락률 조건 위배: {change_pct:.1f}% (Target: {PRICE_CHANGE.MIN}~{PRICE_CHANGE.MAX}%)"
            )
        return FilterResult(passed=True)

    def _validate_news(self, news_score: int, allow_no_news: bool) -> FilterResult:
        """
        뉴스 필터 (뉴스/재료 확인)

        Args:
            news_score: 뉴스 점수
            allow_no_news: 뉴스 없음 허용 여부

        Returns:
            FilterResult
        """
        if not allow_no_news and news_score == 0:
            return FilterResult(
                passed=False,
                reason="뉴스/재료 없음"
            )
        return FilterResult(passed=True)

    def _validate_upper_shadow(self, charts: ChartData) -> FilterResult:
        """
        윗꼬리 필터 (윗꼬리가 긴 캔들 회피)

        Args:
            charts: 차트 데이터

        Returns:
            FilterResult
        """
        if not charts or len(charts.opens) < 1:
            return FilterResult(passed=True)

        try:
            open_p = charts.opens[-1]
            close_p = charts.closes[-1]
            high_p = charts.highs[-1]

            body = abs(close_p - open_p)
            upper_shadow = high_p - max(open_p, close_p)

            if body > 0 and upper_shadow > body * 0.5:
                return FilterResult(
                    passed=False,
                    reason=f"윗꼬리 과다: Shadow({upper_shadow}) > Body({body}*0.5)"
                )
        except Exception:
            pass

        return FilterResult(passed=True)

    def _validate_volume_ratio(self, volume_ratio: float) -> FilterResult:
        """
        거래량 배수 필터 (기본 2배 이상)

        Args:
            volume_ratio: 거래량 배수

        Returns:
            FilterResult
        """
        min_ratio = VOLUME.RATIO_MIN  # 2.0
        if volume_ratio < min_ratio:
            return FilterResult(
                passed=False,
                reason=f"거래량배수 부족: {volume_ratio:.1f} < {min_ratio}"
            )
        return FilterResult(passed=True)


# =============================================================================
# Grade Classifier
# =============================================================================
class GradeClassifier:
    """
    등급 판정기

    필터링 통과 종목의 최종 등급을 판정합니다.
    """

    def __init__(self, config: SignalConfig = None):
        """
        초기화

        Args:
            config: (Optional) SignalConfig 인스턴스
        """
        self.config = config or SignalConfig()

    def classify(
        self,
        stock: StockData,
        score: ScoreDetail,
        score_details: dict,
        supply: SupplyData
    ) -> Optional[Grade]:
        """
        최종 등급 판정

        Args:
            stock: 종목 데이터
            score: 점수 상세
            score_details: 점수 상세 딕셔너리
            supply: 수급 데이터

        Returns:
            Grade 객체 또는 None (미달)
        """
        trading_value = stock.trading_value
        change_pct = stock.change_pct
        volume_ratio = score_details.get('volume_ratio', 0.0)
        total_score = score.total

        # S급 판정
        if self._is_s_grade(trading_value, total_score, volume_ratio):
            logger.debug("  -> [S급] 조건 충족!")
            return Grade.S

        # A급 판정
        if self._is_a_grade(trading_value, total_score, volume_ratio):
            logger.debug("  -> [A급] 조건 충족!")
            return Grade.A

        # B급 판정
        if self._is_b_grade(trading_value, total_score, volume_ratio):
            logger.debug("  -> [B급] 조건 충족!")
            return Grade.B

        # C급 판정 (강소 주도주)
        if self._is_c_grade(total_score, change_pct, volume_ratio, supply):
            logger.debug("  -> [C급] 조건 충족!")
            return Grade.C

        # 점수 미달
        logger.debug(f"  -> [Drop] 점수 미달 (Score={total_score} < 8)")
        return None

    def _is_s_grade(
        self,
        trading_value: int,
        total_score: float,
        volume_ratio: float
    ) -> bool:
        """S급 조건: 1조 이상, 15점 이상, 5배 이상"""
        return (
            trading_value >= self.config.trading_value_s and  # 1조
            total_score >= self.config.min_s_grade and        # 15점
            volume_ratio >= 5.0                               # 5배
        )

    def _is_a_grade(
        self,
        trading_value: int,
        total_score: float,
        volume_ratio: float
    ) -> bool:
        """A급 조건: 5000억 이상, 12점 이상, 3배 이상"""
        return (
            trading_value >= self.config.trading_value_a and  # 5000억
            total_score >= self.config.min_a_grade and        # 12점
            volume_ratio >= 3.0                               # 3배
        )

    def _is_b_grade(
        self,
        trading_value: int,
        total_score: float,
        volume_ratio: float
    ) -> bool:
        """B급 조건: 1000억 이상, 10점 이상, 2배 이상"""
        return (
            trading_value >= self.config.trading_value_b and  # 1000억
            total_score >= self.config.min_b_grade and        # 10점
            volume_ratio >= 2.0                               # 2배
        )

    def _is_c_grade(
        self,
        total_score: float,
        change_pct: float,
        volume_ratio: float,
        supply: SupplyData
    ) -> bool:
        """
        C급 조건 (강소 주도주):
        - 8점 이상
        - 10% 이상 상승
        - 거래량 5배 이상
        - 외인+기관 양매수
        """
        return (
            total_score >= 8 and
            change_pct >= 10.0 and
            volume_ratio >= 5.0 and
            supply.foreign_buy_5d > 0 and
            supply.inst_buy_5d > 0
        )


# =============================================================================
# Convenience Functions
# =============================================================================
def create_filter_validator(config: SignalConfig = None) -> FilterValidator:
    """
    FilterValidator 인스턴스 생성 (Convenience Factory)

    Args:
        config: (Optional) SignalConfig 인스턴스

    Returns:
        FilterValidator 인스턴스
    """
    return FilterValidator(config)


def create_grade_classifier(config: SignalConfig = None) -> GradeClassifier:
    """
    GradeClassifier 인스턴스 생성 (Convenience Factory)

    Args:
        config: (Optional) SignalConfig 인스턴스

    Returns:
        GradeClassifier 인스턴스
    """
    return GradeClassifier(config)
