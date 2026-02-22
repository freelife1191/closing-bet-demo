#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Engine - Scorer (12점 점수 시스템)

Refactored to use GradeClassifier module for grade determination logic.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional

from engine.config import SignalConfig
from engine.constants import PRICE_CHANGE
from engine.grade_classifier import FilterValidator, GradeClassifier
from engine.models import ChartData, ChecklistDetail, Grade, NewsItem, ScoreDetail, StockData, SupplyData
from engine.scorer_scoring_mixin import ScorerScoringMixin


logger = logging.getLogger(__name__)


class Scorer(ScorerScoringMixin):
    """
    12점 점수 시스템.

    Changes:
    - Grade determination logic extracted to GradeClassifier
    - Filter validation extracted to FilterValidator
    - Scoring detail methods extracted to ScorerScoringMixin
    """

    def __init__(self, config: SignalConfig = None):
        self.config = config or SignalConfig()
        self.max_score = 12
        self.filter_validator = FilterValidator(self.config)
        self.grade_classifier = GradeClassifier(self.config)

    def calculate(
        self,
        stock: StockData,
        charts: Optional[ChartData] = None,
        news: Optional[List[NewsItem]] = None,
        supply: Optional[SupplyData] = None,
        llm_result: Optional[Dict] = None,
    ) -> tuple[ScoreDetail, ChecklistDetail, Dict]:
        """점수 계산."""
        score = ScoreDetail()
        checklist = ChecklistDetail()

        (
            score.news,
            checklist.has_news,
            checklist.news_sources,
            score.llm_reason,
        ) = self._score_news(news, llm_result, stock)

        score.volume = self._score_volume(stock)
        (
            score.chart,
            checklist.is_new_high,
            checklist.is_breakout,
            checklist.ma_aligned,
        ) = self._score_chart(stock, charts)
        score.candle = self._score_candle(charts)
        score.timing = self._score_timing(stock, charts)
        score.supply, checklist.supply_positive = self._score_supply(stock.trading_value, supply)

        base_score = (
            score.news
            + score.volume
            + score.chart
            + score.candle
            + score.timing
            + score.supply
        )

        volume_ratio = self._calculate_volume_ratio(stock, charts)
        is_limit_up = stock.change_pct >= PRICE_CHANGE.LIMIT
        bonus_score, bonus_breakdown = self._calculate_bonus(volume_ratio, score.chart, is_limit_up)
        score.total = base_score + bonus_score

        details = self._build_score_details(
            stock,
            supply,
            score,
            base_score,
            bonus_score,
            volume_ratio,
            bonus_breakdown,
            checklist.is_new_high,
            is_limit_up,
        )
        return score, checklist, details

    def determine_grade(
        self,
        stock: StockData,
        score: ScoreDetail,
        score_details: Dict,
        supply: SupplyData,
        charts: ChartData,
        allow_no_news: bool = False,
    ) -> Optional[Grade]:
        """
        최종 등급 판정 (S/A/B).

        - 필터링 검증: FilterValidator
        - 등급 판정: GradeClassifier
        """
        filter_result = self.filter_validator.validate(
            stock=stock,
            score=score,
            score_details=score_details,
            supply=supply,
            charts=charts,
            allow_no_news=allow_no_news,
        )

        if not filter_result.passed:
            logger.debug(f"  -> [Drop] {filter_result.reason}")
            return None

        return self.grade_classifier.classify(
            stock=stock,
            score=score,
            score_details=score_details,
            supply=supply,
        )
