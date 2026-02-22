#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Grade Decider Module
"""

from __future__ import annotations

import logging
from typing import Optional

from engine.config import SignalConfig
from engine.constants import PRICE_CHANGE
from engine.models import Grade, ScoreDetail, StockData, SupplyData

logger = logging.getLogger(__name__)


class GradeClassifier:
    """
    등급 판정기

    필터링 통과 종목의 최종 등급을 판정합니다.
    """

    def __init__(self, config: SignalConfig = None):
        self.config = config or SignalConfig()

    def classify(
        self,
        stock: StockData,
        score: ScoreDetail,
        score_details: dict,
        supply: SupplyData,
    ) -> Optional[Grade]:
        """
        최종 등급 판정

        Args:
            stock: 종목 데이터
            score: 점수 상세
            score_details: 점수 상세 딕셔너리
            supply: 수급 데이터
        """
        trading_value = stock.trading_value
        change_pct = stock.change_pct
        total_score = score.total

        if self._is_s_grade(trading_value, change_pct, total_score, supply):
            logger.debug("  -> [S급] 조건 충족!")
            return Grade.S

        if self._is_a_grade(trading_value, change_pct, total_score, supply):
            logger.debug("  -> [A급] 조건 충족!")
            return Grade.A

        if self._is_b_grade(trading_value, change_pct, total_score, supply):
            logger.debug("  -> [B급] 조건 충족!")
            return Grade.B

        logger.debug(f"  -> [Drop] 점수 미달 (Score={total_score} < 8)")
        return None

    def _is_s_grade(
        self,
        trading_value: int,
        change_pct: float,
        total_score: float,
        supply: SupplyData,
    ) -> bool:
        """S급 조건: 1조 이상, 10점 이상, 상승률 3% 이상, 외인+기관 양매수"""
        return (
            trading_value >= self.config.trading_value_s
            and total_score >= self.config.min_s_grade
            and change_pct >= PRICE_CHANGE.MIN
            and self._has_dual_buy(supply)
        )

    def _is_a_grade(
        self,
        trading_value: int,
        change_pct: float,
        total_score: float,
        supply: SupplyData,
    ) -> bool:
        """A급 조건: 5000억 이상, 8점 이상, 상승률 3% 이상, 외인+기관 양매수"""
        return (
            trading_value >= self.config.trading_value_a
            and total_score >= self.config.min_a_grade
            and change_pct >= PRICE_CHANGE.MIN
            and self._has_dual_buy(supply)
        )

    def _is_b_grade(
        self,
        trading_value: int,
        change_pct: float,
        total_score: float,
        supply: SupplyData,
    ) -> bool:
        """B급 조건: 1,000억 이상, 6점 이상, 상승률 3% 이상, 외인+기관 양매수"""
        return (
            trading_value >= self.config.trading_value_b
            and total_score >= self.config.min_b_grade
            and change_pct >= PRICE_CHANGE.MIN
            and self._has_dual_buy(supply)
        )

    @staticmethod
    def _has_dual_buy(supply: SupplyData) -> bool:
        """외인+기관 동반 매수 여부"""
        return supply.foreign_buy_5d > 0 and supply.inst_buy_5d > 0

