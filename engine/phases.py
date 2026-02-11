#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Engine - Signal Generation Phases

SignalGenerator의 단계별 로직을 분리하여 독립적인 클래스로 구현합니다.
각 클래스는 단일 책임(Single Responsibility Principle)을 가집니다.

Reference: PART_01.md documentation
"""
import logging
import time
import asyncio
from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Any
from datetime import date, datetime

from engine.models import StockData, Signal, ScoreDetail, ChartData, Grade, SignalStatus
from engine.scorer import Scorer
from engine.llm_analyzer import LLMAnalyzer
from engine.constants import (
    TRADING_VALUES,
    VOLUME,
    PRICE_CHANGE,
    LLM as LLM_THRESHOLD,
)
from engine.exceptions import (
    NoCandidatesError,
    AllCandidatesFilteredError,
    ScreeningStoppedError
)
import engine.shared as shared_state

logger = logging.getLogger(__name__)


# =============================================================================
# Base Phase
# =============================================================================
class BasePhase(ABC):
    """
    모든 Phase의 기본 클래스
    """

    def __init__(self, name: str):
        self.name = name
        self.stats = {"processed": 0, "passed": 0, "failed": 0}

    @abstractmethod
    async def execute(self, *args, **kwargs) -> Any:
        """Phase 실행"""
        pass

    def _check_stop_requested(self) -> None:
        """사용자 중단 요청 확인"""
        if shared_state.STOP_REQUESTED:
            raise ScreeningStoppedError(f"User requested stop during {self.name}")

    def get_stats(self) -> Dict[str, int]:
        """통계 정보 반환"""
        return self.stats.copy()


# =============================================================================
# Phase 1: Base Analysis & Pre-Screening
# =============================================================================
class Phase1Analyzer(BasePhase):
    """
    1단계: 기본 분석 및 사전 필터링

    - 상승률 상위 종목에 대해 기본 분석 수행
    - 차트, 수급 데이터 수집
    - Pre-Score 계산 (뉴스/LLM 제외)
    - 필터 조건 검증 (거래대금, 거래량 배수)
    - 등급 미달 사전 차단
    """

    def __init__(
        self,
        collector,
        scorer: Scorer,
        trading_value_min: int = None,
        volume_ratio_min: float = None
    ):
        super().__init__("Phase1: Base Analysis")
        self.collector = collector
        self.scorer = scorer

        # Thresholds from constants
        self.trading_value_min = trading_value_min or TRADING_VALUES.MINIMUM
        self.volume_ratio_min = volume_ratio_min or VOLUME.RATIO_MIN

        # Drop statistics
        self.drop_stats = {
            "low_trading_value": 0,
            "low_volume_ratio": 0,
            "grade_fail": 0,
            "other": 0
        }

    async def execute(
        self,
        candidates: List[StockData]
    ) -> List[Dict]:
        """
        1단계 분석 실행

        Args:
            candidates: 상승률 상위 종목 리스트

        Returns:
            필터링된 후보 리스트 (dict 형태)
        """
        self.stats["processed"] = len(candidates)
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

                # Progress logging
                if (i + 1) % 10 == 0:
                    logger.debug(f"Phase 1: Processed {i + 1}/{len(candidates)}")

            except Exception as e:
                logger.debug(f"Phase 1 analysis failed for {stock.name}: {e}")
                self.stats["failed"] += 1

        logger.info(
            f"[Phase 1] Complete: {self.stats['passed']} passed, "
            f"{self.stats['failed']} failed (Drops: TV={self.drop_stats['low_trading_value']}, "
            f"VR={self.drop_stats['low_volume_ratio']}, Grade={self.drop_stats['grade_fail']})"
        )

        return results

    async def _analyze_stock(self, stock: StockData) -> Optional[Dict]:
        """
        개별 종목 분석

        Args:
            stock: 종목 데이터

        Returns:
            분석 결과 dict 또는 None (필터링됨)
        """
        try:
            # 1. 상세 정보 조회
            detail = await self.collector.get_stock_detail(stock.code)
            if detail:
                stock.high_52w = detail.get('high_52w', stock.high_52w)
                stock.low_52w = detail.get('low_52w', stock.low_52w)

            # 2. 차트 데이터
            charts = await self.collector.get_chart_data(stock.code, 60)

            # 3. 수급 데이터
            supply = await self.collector.get_supply_data(stock.code)

            # 4. Pre-Score 계산 (뉴스/LLM 없음)
            pre_score, _, score_details = self.scorer.calculate(
                stock, charts, [], supply, None
            )

            # 5. 필터 조건 검증
            volume_ratio = score_details.get('volume_ratio', 0)
            trading_value = getattr(stock, 'trading_value', 0)

            # 필터 1: 거래대금
            if trading_value < self.trading_value_min:
                self.drop_stats["low_trading_value"] += 1
                logger.debug(f"[Drop] {stock.name}: Trading value {trading_value // 100_000_000}B < {self.trading_value_min // 100_000_000}B")
                return None

            # 필터 2: 거래량 배수
            if volume_ratio < self.volume_ratio_min:
                self.drop_stats["low_volume_ratio"] += 1
                logger.debug(f"[Drop] {stock.name}: Volume ratio {volume_ratio} < {self.volume_ratio_min}")
                return None

            # 필터 3: 등급 미달 사전 차단
            temp_grade = self.scorer.determine_grade(
                stock, pre_score, score_details, supply, charts, allow_no_news=True
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
                'temp_grade': temp_grade
            }

        except Exception as e:
            logger.debug(f"Analysis error for {stock.name}: {e}")
            self.drop_stats["other"] += 1
            return None

    def get_drop_stats(self) -> Dict[str, int]:
        """탈락 통계 반환"""
        return self.drop_stats.copy()


# =============================================================================
# Phase 2: News Collection
# =============================================================================
class Phase2NewsCollector(BasePhase):
    """
    2단계: 뉴스 수집

    - 필터링된 후보 종목의 뉴스 수집
    - 뉴스 없는 종목 제외
    """

    def __init__(self, news_collector, max_news_per_stock: int = 3):
        super().__init__("Phase2: News Collection")
        self.news_collector = news_collector
        self.max_news_per_stock = max_news_per_stock
        self.no_news_count = 0

    async def execute(
        self,
        items: List[Dict]
    ) -> List[Dict]:
        """
        뉴스 수집 실행

        Args:
            items: Phase 1 결과 리스트

        Returns:
            뉴스가 추가된 리스트
        """
        self.stats["processed"] = len(items)
        results = []

        for item in items:
            self._check_stop_requested()

            try:
                stock = item['stock']
                news_list = await self.news_collector.get_stock_news(
                    stock.code,
                    self.max_news_per_stock,
                    stock.name
                )

                if news_list:
                    item['news'] = news_list
                    results.append(item)
                    self.stats["passed"] += 1
                    logger.debug(f"[News] {stock.name}: {len(news_list)} collected")
                else:
                    self.no_news_count += 1
                    self.stats["failed"] += 1
                    logger.debug(f"[No News] {stock.name}")

            except Exception as e:
                logger.debug(f"News collection failed: {e}")
                self.stats["failed"] += 1

        logger.info(
            f"[Phase 2] Complete: {self.stats['passed']} with news, "
            f"{self.no_news_count} without news"
        )

        return results

    def get_no_news_count(self) -> int:
        """뉴스 없는 종목 수 반환"""
        return self.no_news_count


# =============================================================================
# Phase 3: LLM Batch Analysis
# =============================================================================
class Phase3LLMAnalyzer(BasePhase):
    """
    3단계: 배치 LLM 분석

    - 뉴스가 있는 종목을 LLM으로 일괄 분석
    - 청크 단위로 병렬 처리
    - Rate Limit 방지를 위한 지연 시간 적용
    """

    def __init__(
        self,
        llm_analyzer: LLMAnalyzer,
        chunk_size: int = None,
        concurrency: int = None,
        request_delay: float = None
    ):
        super().__init__("Phase3: LLM Analysis")
        self.llm_analyzer = llm_analyzer

        # Thresholds from constants
        self.chunk_size = chunk_size or LLM_THRESHOLD.CHUNK_SIZE_ANALYSIS
        self.concurrency = concurrency or LLM_THRESHOLD.CONCURRENCY_ANALYSIS
        self.request_delay = request_delay or LLM_THRESHOLD.REQUEST_DELAY

    async def execute(
        self,
        items: List[Dict],
        market_status: Dict = None
    ) -> Dict[str, Dict]:
        """
        LLM 배치 분석 실행

        Args:
            items: Phase 2 결과 리스트 (뉴스 포함)
            market_status: Market Gate 상태

        Returns:
            {종목명: {score, action, confidence, reason}} 형태의 dict
        """
        self.stats["processed"] = len(items)

        if not self.llm_analyzer.client or not items:
            logger.info("[Phase 3] Skipped: No LLM client or items")
            return {}

        # Split into chunks
        chunks = self._create_chunks(items, self.chunk_size)
        total_chunks = len(chunks)

        logger.info(f"[Phase 3] Processing {len(items)} items in {total_chunks} chunks...")

        # Process chunks with concurrency control
        semaphore = asyncio.Semaphore(self.concurrency)
        results = {}

        async def process_chunk(chunk_idx: int, chunk_data: List[Dict]) -> Dict:
            async with semaphore:
                self._check_stop_requested()

                start = time.time()
                logger.info(f"[LLM Batch] Chunk {chunk_idx}/{total_chunks} ({len(chunk_data)} stocks)...")

                try:
                    chunk_result = await self.llm_analyzer.analyze_news_batch(
                        chunk_data,
                        market_status
                    )

                    # Rate limit delay
                    if self.request_delay > 0:
                        await asyncio.sleep(self.request_delay)

                    elapsed = time.time() - start
                    logger.info(f"[LLM Batch] Chunk {chunk_idx} done in {elapsed:.2f}s")
                    self.stats["passed"] += len(chunk_result)
                    return chunk_result

                except Exception as e:
                    logger.warning(f"[LLM Batch] Chunk {chunk_idx} error: {e}")
                    self.stats["failed"] += len(chunk_data)
                    return {}

        # Run all chunks
        tasks = [
            process_chunk(i, chunk)
            for i, chunk in enumerate(chunks, 1)
        ]

        chunk_results = await asyncio.gather(*tasks)

        # Merge results
        for result in chunk_results:
            if result:
                results.update(result)

        logger.info(
            f"[Phase 3] Complete: {len(results)} stocks analyzed, "
            f"{self.stats['failed']} failed"
        )

        return results

    def _create_chunks(self, items: List[Any], size: int) -> List[List[Any]]:
        """리스트를 청크로 분할"""
        return [items[i:i + size] for i in range(0, len(items), size)]


# =============================================================================
# Phase 4: Signal Finalization
# =============================================================================
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
        include_c_grade: bool = False
    ):
        super().__init__("Phase4: Signal Finalization")
        self.scorer = scorer
        self.position_sizer = position_sizer
        self.naver_collector = naver_collector
        self.include_c_grade = include_c_grade

        self.final_stats = {"S": 0, "A": 0, "B": 0, "C": 0}

    async def execute(
        self,
        items: List[Dict],
        llm_results: Dict[str, Dict],
        target_date: date
    ) -> List[Signal]:
        """
        최종 시그널 생성 실행

        Args:
            items: Phase 2 결과 리스트
            llm_results: Phase 3 LLM 분석 결과
            target_date: 대상 날짜

        Returns:
            최종 시그널 리스트
        """
        self.stats["processed"] = len(items)
        signals = []

        for item in items:
            self._check_stop_requested()

            try:
                signal = await self._create_signal(
                    item,
                    llm_results,
                    target_date
                )

                if signal:
                    # C급 제외 옵션
                    grade_val = getattr(signal.grade, 'value', signal.grade)
                    if not self.include_c_grade and grade_val == 'C':
                        logger.info(f"[Drop Phase4] {signal.stock_name}: C grade excluded (Score={signal.score.total})")
                        continue

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
            f"B:{self.final_stats['B']}, C:{self.final_stats['C']})"
        )

        return signals

    async def _create_signal(
        self,
        item: Dict,
        llm_results: Dict[str, Dict],
        target_date: date
    ) -> Optional[Signal]:
        """
        시그널 생성

        Args:
            item: 종목 데이터 dict
            llm_results: LLM 분석 결과 맵
            target_date: 대상 날짜

        Returns:
            Signal 객체 또는 None
        """
        stock = item['stock']
        news = item.get('news', [])
        charts = item['charts']
        supply = item['supply']
        llm_result = llm_results.get(stock.name)

        # 최종 점수 계산
        score, checklist, score_details = self.scorer.calculate(
            stock, charts, news, supply, llm_result
        )

        # AI 분석 결과 보존
        if llm_result:
            score_details['ai_evaluation'] = llm_result
            score.ai_evaluation = llm_result

        # 등급 판정
        grade = self.scorer.determine_grade(
            stock, score, score_details, supply, charts
        )

        if not grade:
            logger.info(f"   [Drop Phase4] {stock.name}: Grade Fail. Score={score.total}, TV={stock.trading_value//100_000_000}억, VR={score_details.get('volume_ratio')}")
            return None

        # 포지션 계산
        position = self.position_sizer.calculate(stock.close, grade)

        # 테마 수집
        themes = []
        if self.naver_collector:
            themes = await self.naver_collector.get_themes(stock.code)

        # 시그널 생성
        return Signal(
            stock_code=stock.code,
            stock_name=stock.name,
            market=stock.market,
            sector=stock.sector,
            signal_date=target_date,
            signal_time=datetime.now(),
            grade=grade,
            score=score,
            checklist=checklist,
            news_items=[{
                "title": n.title,
                "source": n.source,
                "published_at": n.published_at.isoformat() if n.published_at else "",
                "url": n.url,
                "weight": getattr(n, 'weight', 1.0)
            } for n in news[:5]],
            current_price=stock.close,
            change_pct=stock.change_pct,
            entry_price=position.entry_price,
            stop_price=position.stop_price,
            target_price=position.target_price,
            r_value=position.r_value,
            position_size=position.position_size,
            quantity=position.quantity,
            r_multiplier=position.r_multiplier,
            trading_value=stock.trading_value,
            volume_ratio=int(score_details.get('volume_ratio', 0.0)),
            status=SignalStatus.PENDING,
            created_at=datetime.now(),
            score_details=score_details,
            themes=themes
        )

    def _update_grade_stats(self, grade: str):
        """등급별 통계 업데이트"""
        grade_upper = str(grade).upper()
        if grade_upper in self.final_stats:
            self.final_stats[grade_upper] += 1

    def get_final_stats(self) -> Dict[str, int]:
        """최종 등급별 통계 반환"""
        return self.final_stats.copy()


# =============================================================================
# Pipeline Orchestrator
# =============================================================================
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
        phase4: Phase4SignalFinalizer
    ):
        self.phase1 = phase1
        self.phase2 = phase2
        self.phase3 = phase3
        self.phase4 = phase4

    async def execute(
        self,
        candidates: List[StockData],
        market_status: Dict = None,
        target_date: date = None
    ) -> List[Signal]:
        """
        전체 파이프라인 실행

        Args:
            candidates: 상승률 상위 종목 리스트
            market_status: Market Gate 상태
            target_date: 대상 날짜

        Returns:
            최종 시그널 리스트
        """
        target_date = target_date or date.today()

        # Phase 1: Base Analysis
        logger.info("=" * 60)
        logger.info("[Pipeline] Phase 1: Base Analysis & Pre-Screening")
        phase1_results = await self.phase1.execute(candidates)

        if not phase1_results:
            raise NoCandidatesError("All", "No candidates passed Phase 1")

        # Phase 2: News Collection
        logger.info("[Pipeline] Phase 2: News Collection")
        phase2_results = await self.phase2.execute(phase1_results)

        if not phase2_results:
            raise AllCandidatesFilteredError(
                len(phase1_results),
                "No candidates with news"
            )

        # Phase 3: LLM Batch Analysis
        logger.info("[Pipeline] Phase 3: LLM Batch Analysis")
        llm_results = await self.phase3.execute(phase2_results, market_status)

        # Phase 4: Signal Finalization
        logger.info("[Pipeline] Phase 4: Signal Finalization")
        signals = await self.phase4.execute(
            phase2_results,
            llm_results,
            target_date
        )

        return signals

    def get_pipeline_stats(self) -> Dict[str, Dict]:
        """파이프라인 전체 통계"""
        return {
            "phase1": {
                "stats": self.phase1.get_stats(),
                "drops": self.phase1.get_drop_stats()
            },
            "phase2": {
                "stats": self.phase2.get_stats(),
                "no_news": self.phase2.get_no_news_count()
            },
            "phase3": self.phase3.get_stats(),
            "phase4": {
                "stats": self.phase4.get_stats(),
                "grades": self.phase4.get_final_stats()
            }
        }
