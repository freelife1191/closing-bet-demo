#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Engine - SignalGenerator Runtime Mixin

SignalGenerator의 런타임/파이프라인 실행 메서드를 분리한다.
"""

from __future__ import annotations

import logging
import time
from datetime import date, datetime
from typing import Dict, List, Optional

from engine.collectors import KRXCollector
try:
    from engine.collectors.naver import NaverFinanceCollector
except Exception:  # pragma: no cover - legacy collectors 모듈 fallback
    from engine.collectors import NaverFinanceCollector
try:
    from engine.collectors.news import EnhancedNewsCollector
except Exception:  # pragma: no cover - legacy collectors 모듈 fallback
    from engine.collectors import EnhancedNewsCollector
from engine.exceptions import NoCandidatesError
from engine.generator_helpers import (
    analyze_base as _analyze_base_impl,
    analyze_stock as _analyze_stock_impl,
    build_signal_summary as _build_signal_summary_impl,
    create_final_signal as _create_final_signal_impl,
    get_market_status as _get_market_status_impl,
    sync_toss_data as _sync_toss_data_impl,
    update_pipeline_drop_stats as _update_pipeline_drop_stats_impl,
)
from engine.models import Signal, StockData
from engine.phases import (
    Phase1Analyzer,
    Phase2NewsCollector,
    Phase3LLMAnalyzer,
    Phase4SignalFinalizer,
    SignalGenerationPipeline,
)
from engine.toss_collector import TossCollector

logger = logging.getLogger(__name__)


class SignalGeneratorRuntimeMixin:
    async def __aenter__(self):
        self._collector = KRXCollector(self.config)
        await self._collector.__aenter__()

        self._news = EnhancedNewsCollector(self.config)
        await self._news.__aenter__()

        self._naver = NaverFinanceCollector(self.config)
        self._toss_collector = TossCollector(self.config)

        # [REFACTORED] Initialize the signal generation pipeline
        self._pipeline = self._create_pipeline()

        return self

    def _create_pipeline(self) -> SignalGenerationPipeline:
        """
        Create the signal generation pipeline with all phases.

        This method encapsulates the dependency injection of all phases.
        """
        # Phase 1: Base Analysis & Pre-Screening
        phase1 = Phase1Analyzer(
            collector=self._collector,
            scorer=self.scorer,
            trading_value_min=self.config.trading_value_min,
        )

        # Phase 2: News Collection
        phase2 = Phase2NewsCollector(
            news_collector=self._news,
            max_news_per_stock=3,
        )

        # Phase 3: LLM Batch Analysis
        phase3 = Phase3LLMAnalyzer(
            llm_analyzer=self.llm_analyzer,
            chunk_size=10,
            request_delay=2.0,
        )

        # Phase 4: Signal Finalization
        phase4 = Phase4SignalFinalizer(
            scorer=self.scorer,
            position_sizer=self.position_sizer,
            naver_collector=self._naver,
            include_c_grade=False,
        )

        return SignalGenerationPipeline(
            phase1=phase1,
            phase2=phase2,
            phase3=phase3,
            phase4=phase4,
        )

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._collector:
            await self._collector.__aexit__(exc_type, exc_val, exc_tb)
        if self._news:
            await self._news.__aexit__(exc_type, exc_val, exc_tb)

        if self.llm_analyzer:
            await self.llm_analyzer.close()

    async def generate(
        self,
        target_date: date = None,
        markets: List[str] = None,
        top_n: int = 300,
    ) -> List[Signal]:
        """
        시그널 생성 (Refactored to use SignalGenerationPipeline)

        Uses the 4-phase pipeline for cleaner separation of concerns:
        - Phase 1: Base Analysis & Pre-Screening
        - Phase 2: News Collection
        - Phase 3: LLM Batch Analysis
        - Phase 4: Signal Finalization
        """
        start_time = time.time()

        # 주말/휴일 처리: 제공된 날짜가 없으면 가장 최근 장 마감 날짜 사용
        if target_date is None:
            latest_str = self._collector._get_latest_market_date()
            target_date = datetime.strptime(latest_str, '%Y%m%d').date()

        markets = markets or ["KOSPI", "KOSDAQ"]
        all_signals = []

        # 스캔 통계 초기화 (run 당 1회)
        self.scan_stats = {
            "scanned": 0,
            "phase1": 0,
            "phase2": 0,
            "final": 0,
        }

        # 탈락 통계 초기화
        self.drop_stats = {
            "low_trading_value": 0,
            "low_pre_score": 0,
            "no_news": 0,
            "grade_fail": 0,
            "other": 0,
        }

        for market in markets:
            logger.info(f"=" * 60)
            logger.info(f"[종가베팅] {market} 스크리닝 시작 (v3.0 Pipeline)")
            logger.info(f"=" * 60)
            print(f"\n[{market}] 상승률 상위 종목 스크리닝... (v3.0 Pipeline)")

            # 1. 상승률 상위 종목 조회
            target_date_str = target_date.strftime('%Y%m%d') if target_date else None
            candidates = await self._collector.get_top_gainers(market, top_n, target_date_str)
            logger.info(f"[{market}] 상승률 상위 데이터 수집 완료: {len(candidates)}개")
            print(f"  - 1차 필터 통과: {len(candidates)}개")

            # 통계 업데이트
            self.scan_stats["scanned"] += len(candidates)

            if not candidates:
                print(f"  - No candidates for {market}")
                continue

            # Toss 데이터 동기화 (Hybrid 모드)
            await self._sync_toss_data(candidates, target_date)

            phase1_pass_before = 0
            phase2_pass_before = 0
            if self._pipeline and hasattr(self._pipeline, 'phase1'):
                phase1_pass_before = self._pipeline.phase1.get_stats().get('passed', 0)
            if self._pipeline and hasattr(self._pipeline, 'phase2'):
                phase2_pass_before = self._pipeline.phase2.get_stats().get('passed', 0)

            # [REFACTORED] Use SignalGenerationPipeline
            try:
                market_status = await self._get_market_status(target_date)
                signals = await self._pipeline.execute(
                    candidates=candidates,
                    market_status=market_status,
                    target_date=target_date,
                )

                all_signals.extend(signals)

                elapsed = time.time() - start_time
                print(f"  ✓ {market} 완료: {len(signals)}개 시그널 ({elapsed:.1f}초)")

            except NoCandidatesError as e:
                logger.warning(f"[{market}] {e}")
                print(f"  - {market}: 조건에 맞는 후보 종목이 없습니다. ({e})")
                continue
            except Exception as e:
                logger.error(f"[{market}] Pipeline execution failed: {e}")
                print(f"  ✗ {market} 실패: {e}")
                continue
            finally:
                if self._pipeline and hasattr(self._pipeline, 'phase1'):
                    phase1_pass_after = self._pipeline.phase1.get_stats().get('passed', 0)
                    self.scan_stats["phase1"] += max(0, phase1_pass_after - phase1_pass_before)
                if self._pipeline and hasattr(self._pipeline, 'phase2'):
                    phase2_pass_after = self._pipeline.phase2.get_stats().get('passed', 0)
                    self.scan_stats["phase2"] += max(0, phase2_pass_after - phase2_pass_before)

        # 요약
        total_elapsed = time.time() - start_time
        logger.info(f"=" * 60)
        logger.info(f"[종가베팅] 전체 완료: {len(all_signals)}개 시그널 ({total_elapsed:.1f}초)")
        logger.info(f"=" * 60)
        self.scan_stats["final"] = len(all_signals)

        # 파이프라인 통계 저장 (최종 누적)
        if self._pipeline:
            self.pipeline_stats = self._pipeline.get_pipeline_stats()
            self.drop_stats = self.pipeline_stats.get('phase1', {}).get('drops', self.drop_stats)

        return all_signals

    async def _sync_toss_data(self, candidates: List[StockData], target_date: date = None) -> None:
        """
        Toss 증권 데이터 동기화 (Hybrid 모드)

        Toss API를 통해 실시간 가격 데이터를 후보 종목에 동기화합니다.
        """
        await _sync_toss_data_impl(
            candidates=candidates,
            target_date=target_date,
            config=self.config,
            scorer=self.scorer,
            logger=logger,
        )

    async def _get_market_status(self, target_date: date) -> Dict:
        """
        Market Gate 상태 조회

        Returns market status dict for use in pipeline phases.
        """
        return await _get_market_status_impl(
            target_date=target_date,
            data_dir=self.config.DATA_DIR,
            logger=logger,
        )

    def _update_pipeline_stats(self) -> None:
        """
        파이프라인 통계 업데이트

        Updates drop_stats from pipeline phases.
        """
        self.drop_stats = _update_pipeline_drop_stats_impl(
            pipeline=self._pipeline,
            current_drop_stats=self.drop_stats,
        )

    async def _analyze_base(self, stock: StockData) -> Optional[Dict]:
        """1단계: 기본 분석 (차트, 수급, Pre-Score)"""
        return await _analyze_base_impl(
            stock=stock,
            collector=self._collector,
            scorer=self.scorer,
            config=self.config,
        )

    def _create_final_signal(
        self,
        stock,
        target_date,
        news_list,
        llm_result,
        charts,
        supply,
        themes: List[str] = None,
    ) -> Optional[Signal]:
        """최종 시그널 생성 헬퍼"""
        return _create_final_signal_impl(
            stock=stock,
            target_date=target_date,
            news_list=news_list,
            llm_result=llm_result,
            charts=charts,
            supply=supply,
            scorer=self.scorer,
            position_sizer=self.position_sizer,
            themes=themes,
        )

    async def _analyze_stock(self, stock: StockData, target_date: date) -> Optional[Signal]:
        """단일 종목 분석 (기존 호환용 - Batch 미사용)"""
        return await _analyze_stock_impl(
            stock=stock,
            target_date=target_date,
            collector=self._collector,
            news_collector=self._news,
            llm_analyzer=self.llm_analyzer,
            scorer=self.scorer,
            position_sizer=self.position_sizer,
            config=self.config,
        )

    def get_summary(self, signals: List[Signal]) -> Dict:
        """시그널 요약 정보"""
        return _build_signal_summary_impl(signals)
