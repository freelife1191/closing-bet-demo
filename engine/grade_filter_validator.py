#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Grade Filter Validator Module
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from engine.config import SignalConfig
from engine.constants import PRICE_CHANGE
from engine.models import ChartData, ScoreDetail, StockData, SupplyData

logger = logging.getLogger(__name__)


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


class FilterValidator:
    """
    필터링 조건 검증기

    종목이 시그널 생성 대상으로 적합한지 검증합니다.
    모든 조건을 통과해야 등급 판정 대상이 됩니다.
    """

    def __init__(self, config: SignalConfig = None):
        self.config = config or SignalConfig()

    def validate(
        self,
        stock: StockData,
        score: ScoreDetail,
        score_details: dict,
        supply: SupplyData,
        charts: ChartData,
        allow_no_news: bool = False,
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
        """
        trading_value = stock.trading_value
        change_pct = stock.change_pct

        result = self._validate_trading_value(trading_value)
        if not result.passed:
            return result

        result = self._validate_price_change(change_pct)
        if not result.passed:
            return result

        result = self._validate_news(score.news, allow_no_news)
        if not result.passed:
            return result

        result = self._validate_upper_shadow(charts)
        if not result.passed:
            return result

        return FilterResult(passed=True)

    def _validate_trading_value(self, trading_value: int) -> FilterResult:
        min_value = self.config.trading_value_min
        if trading_value < min_value:
            return FilterResult(
                passed=False,
                reason=f"거래대금 부족: {trading_value//100_000_000}억 < {min_value//100_000_000}억",
            )
        return FilterResult(passed=True)

    def _validate_price_change(self, change_pct: float) -> FilterResult:
        max_change = max(
            30.0,
            PRICE_CHANGE.MAX,
            getattr(PRICE_CHANGE, "LIMIT", PRICE_CHANGE.MAX),
        )
        if not (PRICE_CHANGE.MIN <= change_pct <= max_change):
            return FilterResult(
                passed=False,
                reason=f"등락률 조건 위배: {change_pct:.1f}% (Target: {PRICE_CHANGE.MIN}~{max_change}%)",
            )
        return FilterResult(passed=True)

    def _validate_news(self, news_score: int, allow_no_news: bool) -> FilterResult:
        if not allow_no_news and news_score == 0:
            return FilterResult(passed=False, reason="뉴스/재료 없음")
        return FilterResult(passed=True)

    def _validate_upper_shadow(self, charts: ChartData) -> FilterResult:
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
                    reason=f"윗꼬리 과다: Shadow({upper_shadow}) > Body({body}*0.5)",
                )
        except (IndexError, TypeError, ValueError) as error:
            logger.debug(f"윗꼬리 필터 계산 실패, 필터 통과 처리: {error}")

        return FilterResult(passed=True)
