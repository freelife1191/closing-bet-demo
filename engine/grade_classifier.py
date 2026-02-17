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
from engine.constants import PRICE_CHANGE

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

        # 모든 필터 통과
        return FilterResult(passed=True)

    def _validate_trading_value(self, trading_value: int) -> FilterResult:
        """
        거래대금 필터 (최소값)

        Args:
            trading_value: 거래대금

        Returns:
            FilterResult
        """
        min_value = self.config.trading_value_min
        if trading_value < min_value:
            return FilterResult(
                passed=False,
                reason=f"거래대금 부족: {trading_value//100_000_000}억 < {min_value//100_000_000}억"
            )
        return FilterResult(passed=True)

    def _validate_price_change(self, change_pct: float) -> FilterResult:
        """
        등락률 필터 (PRICE_CHANGE.MIN~PRICE_CHANGE.MAX 이내)

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
        total_score = score.total

        # S급 판정
        if self._is_s_grade(trading_value, change_pct, total_score, supply):
            logger.debug("  -> [S급] 조건 충족!")
            return Grade.S

        # A급 판정
        if self._is_a_grade(trading_value, change_pct, total_score, supply):
            logger.debug("  -> [A급] 조건 충족!")
            return Grade.A

        # B급 판정
        if self._is_b_grade(trading_value, change_pct, total_score, supply):
            logger.debug("  -> [B급] 조건 충족!")
            return Grade.B

        # 점수 미달
        logger.debug(f"  -> [Drop] 점수 미달 (Score={total_score} < 8)")
        return None

    def _is_s_grade(
        self,
        trading_value: int,
        change_pct: float,
        total_score: float,
        supply: SupplyData
    ) -> bool:
        """S급 조건: 1조 이상, 10점 이상, 상승률 3% 이상, 외인+기관 양매수"""
        return (
            trading_value >= self.config.trading_value_s and  # 1조
            total_score >= self.config.min_s_grade and        # 10점
            change_pct >= PRICE_CHANGE.MIN and                # 상승률 3%
            self._has_dual_buy(supply)                       # 외인+기관 동반 매수
        )

    def _is_a_grade(
        self,
        trading_value: int,
        change_pct: float,
        total_score: float,
        supply: SupplyData
    ) -> bool:
        """A급 조건: 5000억 이상, 8점 이상, 상승률 3% 이상, 외인+기관 양매수"""
        return (
            trading_value >= self.config.trading_value_a and  # 5000억
            total_score >= self.config.min_a_grade and        # 8점
            change_pct >= PRICE_CHANGE.MIN and                # 상승률 3%
            self._has_dual_buy(supply)                       # 외인+기관 동반 매수
        )

    def _is_b_grade(
        self,
        trading_value: int,
        change_pct: float,
        total_score: float,
        supply: SupplyData
    ) -> bool:
        """B급 조건: 1,000억 이상, 6점 이상, 상승률 3% 이상, 외인+기관 양매수"""
        return (
            trading_value >= self.config.trading_value_b and  # 1000억
            total_score >= self.config.min_b_grade and        # 6점
            change_pct >= PRICE_CHANGE.MIN and                # 상승률 3%
            self._has_dual_buy(supply)                       # 외인+기관 동반 매수
        )

    @staticmethod
    def _has_dual_buy(supply: SupplyData) -> bool:
        """외인+기관 동반 매수 여부"""
        return supply.foreign_buy_5d > 0 and supply.inst_buy_5d > 0


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
