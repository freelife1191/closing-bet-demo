#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Engine - Signal Generation Phases (Pipeline)

Phase 오케스트레이션을 담당합니다.
"""

import logging
from datetime import date
from typing import Dict, List

from engine.exceptions import AllCandidatesFilteredError, NoCandidatesError
from engine.models import Signal, StockData
from engine.phases_analysis import Phase1Analyzer, Phase4SignalFinalizer
from engine.phases_news_llm import Phase2NewsCollector, Phase3LLMAnalyzer

logger = logging.getLogger(__name__)


class SignalGenerationPipeline:
    """
    시그널 생성 파이프라인

    모든 Phase를 순차적으로 실행하고 결과를 집계합니다.
    """

    def __init__(
        self,
        phase1: Phase1Analyzer,
        phase2: Phase2NewsCollector,
        phase3: Phase3LLMAnalyzer,
        phase4: Phase4SignalFinalizer,
    ):
        self.phase1 = phase1
        self.phase2 = phase2
        self.phase3 = phase3
        self.phase4 = phase4

    async def execute(
        self,
        candidates: List[StockData],
        market_status: Dict = None,
        target_date: date = None,
    ) -> List[Signal]:
        """전체 파이프라인 실행."""
        target_date = target_date or date.today()

        logger.info("=" * 60)
        logger.info("[Pipeline] Phase 1: Base Analysis & Pre-Screening")
        phase1_results = await self.phase1.execute(candidates)

        if not phase1_results:
            raise NoCandidatesError("All", "No candidates passed Phase 1")

        logger.info("[Pipeline] Phase 2: News Collection")
        phase2_results = await self.phase2.execute(phase1_results)

        if not phase2_results:
            raise AllCandidatesFilteredError(len(phase1_results), "No candidates with news")

        logger.info("[Pipeline] Phase 3: LLM Batch Analysis")
        llm_results = await self.phase3.execute(phase2_results, market_status)

        logger.info("[Pipeline] Phase 4: Signal Finalization")
        signals = await self.phase4.execute(phase2_results, llm_results, target_date)

        return signals

    def get_pipeline_stats(self) -> Dict[str, Dict]:
        """파이프라인 전체 통계."""
        return {
            "phase1": {
                "stats": self.phase1.get_stats(),
                "drops": self.phase1.get_drop_stats(),
            },
            "phase2": {
                "stats": self.phase2.get_stats(),
                "no_news": self.phase2.get_no_news_count(),
            },
            "phase3": self.phase3.get_stats(),
            "phase4": {
                "stats": self.phase4.get_stats(),
                "grades": self.phase4.get_final_stats(),
            },
        }
