#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Engine - Signal Generation Phases (Analysis)

Phase1(기본 분석) / Phase4(최종 시그널 생성) 로직을 담당합니다.
"""

import logging
from datetime import date
from typing import Dict, List, Optional

from engine.constants import TRADING_VALUES
from engine.models import Signal, StockData
from engine.phases_base import BasePhase
from engine.phases_phase1_helpers import analyze_vcp_for_stock as analyze_vcp_for_stock_impl
from engine.phases_phase4_helpers import (
    build_signal as build_signal_impl,
    merge_vcp_score_details as merge_vcp_score_details_impl,
    serialize_news_items as serialize_news_items_impl,
)
from engine.scorer import Scorer

logger = logging.getLogger(__name__)


class Phase1Analyzer(BasePhase):
    """
    1단계: 기본 분석 및 사전 필터링

    - 상승률 상위 종목에 대해 기본 분석 수행
    - 차트, 수급 데이터 수집
    - Pre-Score 계산 (뉴스/LLM 제외)
    - 필터 조건 검증 (거래대금, 가격/뉴스/등락 필터)
    - 등급 미달 사전 차단
    """

    def __init__(
        self,
        collector,
        scorer: Scorer,
        trading_value_min: int = None,
    ):
        super().__init__("Phase1: Base Analysis")
        self.collector = collector
        self.scorer = scorer

        self.trading_value_min = trading_value_min or TRADING_VALUES.MINIMUM

        self.drop_stats = {
            "low_trading_value": 0,
            "grade_fail": 0,
            "other": 0,
        }

    async def execute(self, candidates: List[StockData]) -> List[Dict]:
        """1단계 분석 실행."""
        self.stats["processed"] += len(candidates)
        results = []

        for i, stock in enumerate(candidates):
            self._check_stop_requested()

            try:
                result = await self._analyze_stock(stock)
                if result:
                    results.append(result)
                    self.stats["passed"] += 1
                else:
                    self.stats["failed"] += 1

                if (i + 1) % 10 == 0:
                    logger.debug(f"Phase 1: Processed {i + 1}/{len(candidates)}")

            except Exception as e:
                logger.debug(f"Phase 1 analysis failed for {stock.name}: {e}")
                self.stats["failed"] += 1

        logger.info(
            f"[Phase 1] Complete: {self.stats['passed']} passed, "
            f"{self.stats['failed']} failed (Drops: TV={self.drop_stats['low_trading_value']}, "
            f"Grade={self.drop_stats['grade_fail']}, Other={self.drop_stats['other']})"
        )

        return results

    async def _analyze_stock(self, stock: StockData) -> Optional[Dict]:
        """개별 종목 분석."""
        try:
            detail = await self.collector.get_stock_detail(stock.code)
            if detail:
                stock.high_52w = detail.get('high_52w', stock.high_52w)
                stock.low_52w = detail.get('low_52w', stock.low_52w)

            charts = await self.collector.get_chart_data(stock.code, 60)
            supply = await self.collector.get_supply_data(stock.code)

            pre_score, _, score_details = self.scorer.calculate(stock, charts, [], supply, None)

            vcp_data = analyze_vcp_for_stock_impl(stock=stock, charts=charts, logger=logger)

            trading_value = getattr(stock, 'trading_value', 0)
            if trading_value < self.trading_value_min:
                self.drop_stats["low_trading_value"] += 1
                logger.debug(
                    f"[Drop] {stock.name}: Trading value {trading_value // 100_000_000}B < "
                    f"{self.trading_value_min // 100_000_000}B"
                )
                return None

            temp_grade = self.scorer.determine_grade(
                stock,
                pre_score,
                score_details,
                supply,
                charts,
                allow_no_news=True,
            )

            if not temp_grade:
                self.drop_stats["grade_fail"] += 1
                return None

            return {
                'stock': stock,
                'charts': charts,
                'supply': supply,
                'pre_score': pre_score,
                'score_details': score_details,
                'temp_grade': temp_grade,
                'vcp': vcp_data,
            }

        except Exception as e:
            logger.debug(f"Analysis error for {stock.name}: {e}")
            self.drop_stats["other"] += 1
            return None

    def get_drop_stats(self) -> Dict[str, int]:
        """탈락 통계 반환."""
        return self.drop_stats.copy()


class Phase4SignalFinalizer(BasePhase):
    """
    4단계: 최종 시그널 생성

    - LLM 결과를 포함하여 최종 점수 계산
    - 등급 판정
    - 포지션 계산
    - 시그널 객체 생성
    """

    def __init__(
        self,
        scorer: Scorer,
        position_sizer,
        naver_collector,
        include_c_grade: bool = False,
    ):
        super().__init__("Phase4: Signal Finalization")
        self.scorer = scorer
        self.position_sizer = position_sizer
        self.naver_collector = naver_collector
        self.include_c_grade = include_c_grade

        self.final_stats = {"S": 0, "A": 0, "B": 0}

    async def execute(
        self,
        items: List[Dict],
        llm_results: Dict[str, Dict],
        target_date: date,
    ) -> List[Signal]:
        """최종 시그널 생성 실행."""
        self.stats["processed"] += len(items)
        signals = []

        for item in items:
            self._check_stop_requested()

            try:
                signal = await self._create_signal(item, llm_results, target_date)

                if signal:
                    grade_val = getattr(signal.grade, 'value', signal.grade)
                    signals.append(signal)
                    self._update_grade_stats(grade_val)
                    self.stats["passed"] += 1
                else:
                    self.stats["failed"] += 1

            except Exception as e:
                logger.info(f"[Error Phase4] Signal creation failed for {item['stock'].name}: {e}")
                self.stats["failed"] += 1

        logger.info(
            f"[Phase 4] Complete: {len(signals)} signals created "
            f"(S:{self.final_stats['S']}, A:{self.final_stats['A']}, "
            f"B:{self.final_stats['B']})"
        )

        return signals

    async def _create_signal(
        self,
        item: Dict,
        llm_results: Dict[str, Dict],
        target_date: date,
    ) -> Optional[Signal]:
        """시그널 생성."""
        stock = item['stock']
        news = item.get('news', [])
        charts = item['charts']
        supply = item['supply']
        llm_result = llm_results.get(stock.name)

        score, checklist, score_details = self.scorer.calculate(stock, charts, news, supply, llm_result)

        if llm_result:
            score_details['ai_evaluation'] = llm_result
            score.ai_evaluation = llm_result

        grade = self.scorer.determine_grade(stock, score, score_details, supply, charts)

        vcp_data = item.get("vcp")
        score_details = merge_vcp_score_details_impl(score_details=score_details, vcp_data=vcp_data)

        if not grade:
            logger.info(
                f"   [Drop Phase4] {stock.name}: Grade Fail. "
                f"Score={score.total}, TV={stock.trading_value//100_000_000}억"
            )
            return None

        position = self.position_sizer.calculate(stock.close, grade)

        themes = []
        if self.naver_collector:
            themes = await self.naver_collector.get_themes(stock.code)

        return build_signal_impl(
            stock=stock,
            target_date=target_date,
            grade=grade,
            score=score,
            checklist=checklist,
            score_details=score_details,
            news_items=serialize_news_items_impl(news),
            position=position,
            themes=themes,
        )

    def _update_grade_stats(self, grade: str) -> None:
        """등급별 통계 업데이트."""
        grade_upper = str(grade).upper()
        if grade_upper in self.final_stats:
            self.final_stats[grade_upper] += 1

    def get_final_stats(self) -> Dict[str, int]:
        """최종 등급별 통계 반환."""
        return self.final_stats.copy()
