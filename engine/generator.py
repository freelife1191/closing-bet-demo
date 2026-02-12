#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
시그널 생성기 (Main Engine)
- Collector로부터 데이터 수집
- Scorer로 점수 계산
- PositionSizer로 자금 관리
- 최종 Signal 생성 (Batch LLM 지원)

REFACTORED: Now uses SignalGenerationPipeline from phases.py
for cleaner separation of concerns.
"""

import asyncio
from datetime import date, datetime, timedelta
from typing import List, Optional, Dict
import time
import sys
import os
import json
import logging

# 모듈 경로 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.config import config as default_config, app_config
import engine.shared as shared_state
from engine.models import (
    StockData, Signal, SignalStatus, ScoreDetail, ChecklistDetail, ScreenerResult, ChartData, Grade
)
from engine.exceptions import NoCandidatesError
from engine.collectors import KRXCollector, EnhancedNewsCollector, NaverFinanceCollector
from engine.toss_collector import TossCollector
from engine.scorer import Scorer
from engine.position_sizer import PositionSizer
from engine.llm_analyzer import LLMAnalyzer
from engine.market_gate import MarketGate
from engine.utils import NumpyEncoder

# [REFACTORED] Import the phase-based pipeline
from engine.phases import (
    SignalGenerationPipeline,
    Phase1Analyzer,
    Phase2NewsCollector,
    Phase3LLMAnalyzer,
    Phase4SignalFinalizer
)

logger = logging.getLogger(__name__)


class SignalGenerator:
    """종가베팅 시그널 생성기 (v2)"""

    def __init__(
        self,
        config=None,
        capital: float = 10_000_000,
    ):
        """
        Args:
            capital: 총 자본금 (기본 5천만원)
            config: 설정 (기본 설정 사용)
        """
        # [Fix] config가 None으로 전달되면 기본 설정(default_config) 사용
        self.config = config if config else default_config
        self.capital = capital

        self.scorer = Scorer(self.config)
        self.position_sizer = PositionSizer(capital, self.config)
        self.llm_analyzer = LLMAnalyzer()

        self._collector: Optional[KRXCollector] = None
        self._news: Optional[EnhancedNewsCollector] = None
        self._naver: Optional[NaverFinanceCollector] = None
        self._toss_collector: Optional[TossCollector] = None
        
        # 스캔 통계
        self.scan_stats = {
            "scanned": 0,
            "phase1": 0,
            "phase2": 0,
            "final": 0
        }
        
        # 탈락 통계 (진단용)
        self.drop_stats = {
            "low_trading_value": 0,
            "low_volume_ratio": 0,
            "low_pre_score": 0,
            "no_news": 0,
            "grade_fail": 0,
            "other": 0
        }

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
            volume_ratio_min=2.0  # Default volume ratio minimum
        )

        # Phase 2: News Collection
        phase2 = Phase2NewsCollector(
            news_collector=self._news,
            max_news_per_stock=3
        )

        # Phase 3: LLM Batch Analysis
        phase3 = Phase3LLMAnalyzer(
            llm_analyzer=self.llm_analyzer,
            chunk_size=10,
            request_delay=2.0
        )

        # Phase 4: Signal Finalization
        phase4 = Phase4SignalFinalizer(
            scorer=self.scorer,
            position_sizer=self.position_sizer,
            naver_collector=self._naver,
            include_c_grade=False
        )

        return SignalGenerationPipeline(
            phase1=phase1,
            phase2=phase2,
            phase3=phase3,
            phase4=phase4
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

        # 탈락 통계 초기화
        self.drop_stats = {
            "low_trading_value": 0,
            "low_volume_ratio": 0,
            "low_pre_score": 0,
            "no_news": 0,
            "grade_fail": 0,
            "other": 0
        }

        for market in markets:
            logger.info(f"="*60)
            logger.info(f"[종가베팅] {market} 스크리닝 시작 (v3.0 Pipeline)")
            logger.info(f"="*60)
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

            # [REFACTORED] Use SignalGenerationPipeline
            try:
                market_status = await self._get_market_status(target_date)
                signals = await self._pipeline.execute(
                    candidates=candidates,
                    market_status=market_status,
                    target_date=target_date
                )

                # Update statistics from pipeline
                self._update_pipeline_stats()

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

        # 요약
        total_elapsed = time.time() - start_time
        logger.info(f"="*60)
        logger.info(f"[종가베팅] 전체 완료: {len(all_signals)}개 시그널 ({total_elapsed:.1f}초)")
        logger.info(f"="*60)

        # 파이프라인 통계 저장 (최종 누적)
        if self._pipeline:
            self.pipeline_stats = self._pipeline.get_pipeline_stats()

        return all_signals

    async def _sync_toss_data(self, candidates: List[StockData], target_date: date = None) -> None:
        """
        Toss 증권 데이터 동기화 (Hybrid 모드)

        Toss API를 통해 실시간 가격 데이터를 후보 종목에 동기화합니다.
        """
        if not self.config.USE_TOSS_DATA or not candidates:
            return

        # [Fix] 과거 날짜 분석 시 실시간 데이터 덮어쓰기 방지
        if target_date and target_date != date.today():
             # logger.debug(f"  [Skip] Toss Realtime Sync skipped for past date: {target_date}")
             return

        try:
            print(f"  [Hybrid] Toss 증권 데이터 동기화 중... ({len(candidates)}개)")
            codes = [stock.code for stock in candidates]
            toss_data_map = self.scorer.collector_toss.get_prices_batch(codes) if hasattr(self.scorer, 'collector_toss') else {}

            if not toss_data_map:
                from engine.toss_collector import TossCollector
                toss_collector = TossCollector(self.config)
                toss_data_map = toss_collector.get_prices_batch(codes)

            updated_count = 0
            for stock in candidates:
                if stock.code in toss_data_map:
                    t_data = toss_data_map[stock.code]

                    new_close = t_data.get('current')
                    new_val = t_data.get('trading_value')
                    new_vol = t_data.get('volume')
                    new_rate = t_data.get('change_pct')

                    if new_close and new_val:
                        stock.close = int(new_close)
                        stock.trading_value = float(new_val)
                        stock.volume = int(new_vol)
                        stock.change_pct = float(new_rate)
                        stock.open = int(t_data.get('open', 0))
                        stock.high = int(t_data.get('high', 0))
                        stock.low = int(t_data.get('low', 0))
                        updated_count += 1

                        if stock.trading_value >= 300_000_000_000:
                            logger.info(f"  [Toss Update] {stock.name}({stock.code}): {int(stock.trading_value)//100000000}억 (Rate: {stock.change_pct}%)")

            print(f"  [Hybrid] {updated_count}개 종목 데이터 업데이트 완료 (Toss 기준)")

        except Exception as e:
            logger.error(f"Toss 데이터 동기화 중 오류: {e}")
            print(f"  [Warning] Toss 동기화 실패. KRX 데이터 사용. ({e})")

    async def _get_market_status(self, target_date: date) -> Dict:
        """
        Market Gate 상태 조회

        Returns market status dict for use in pipeline phases.
        """
        try:
            market_gate = MarketGate(self.config.DATA_DIR)
            return market_gate.analyze(target_date.strftime('%Y-%m-%d'))
        except Exception as e:
            logger.warning(f"Market Gate analysis failed: {e}")
            return {}

    def _update_pipeline_stats(self) -> None:
        """
        파이프라인 통계 업데이트

        Updates drop_stats from pipeline phases.
        """
        if hasattr(self._pipeline, 'phase1') and self._pipeline.phase1:
            phase1_drops = self._pipeline.phase1.get_drop_stats()
            for key, value in phase1_drops.items():
                if key in self.drop_stats:
                    self.drop_stats[key] += value
    async def _analyze_base(self, stock: StockData) -> Optional[Dict]:
        """1단계: 기본 분석 (차트, 수급, Pre-Score)"""
        try:
            # 상세 정보
            detail = await self._collector.get_stock_detail(stock.code)
            if detail:
                stock.high_52w = detail.get('high_52w', stock.high_52w)
                stock.low_52w = detail.get('low_52w', stock.low_52w)

            # 차트
            charts = await self._collector.get_chart_data(stock.code, 60)
            
            # [Hybrid] 차트 데이터 싱크 (KRX -> Toss)
            if self.config.USE_TOSS_DATA and charts and getattr(stock, 'trading_value', 0) > 0 and charts.closes:
                try:
                    # Top Gainers는 오늘 데이터가 갱신된 상태이므로 마지막 캔들 덮어쓰기
                    charts.closes[-1] = stock.close
                    # stock.volume은 이미 Toss 데이터로 업데이트된 상태
                    charts.volumes[-1] = stock.volume
                    if hasattr(stock, 'open') and stock.open: charts.opens[-1] = stock.open
                    if hasattr(stock, 'high') and stock.high: charts.highs[-1] = stock.high
                    if hasattr(stock, 'low') and stock.low: charts.lows[-1] = stock.low
                except Exception as e:
                    pass

            # 수급
            supply = await self._collector.get_supply_data(stock.code)
            
            # Pre-Score 계산 (뉴스/LLM 없음)
            pre_score, _, score_details = self.scorer.calculate(stock, charts, [], supply, None)
            
            return {
                'stock': stock,
                'charts': charts,
                'supply': supply,
                'pre_score': pre_score,
                'score_details': score_details
            }
        except Exception as e:
            print(f"    ⚠️ 기본 분석 오류 {stock.name}: {e}")
            return None

    def _create_final_signal(
        self, stock, target_date, news_list, llm_result, charts, supply, themes: List[str] = None
    ) -> Optional[Signal]:
        """최종 시그널 생성 헬퍼"""
        try:
            # 점수 계산
            score, checklist, score_details = self.scorer.calculate(stock, charts, news_list, supply, llm_result)
            
            # [Fix] AI 분석 결과 보존
            if llm_result:
                score_details['ai_evaluation'] = llm_result
                score.ai_evaluation = llm_result
            
            # 등급 미달 제외 (None)
            grade = self.scorer.determine_grade(stock, score, score_details, supply, charts)
            
            if not grade:
                print(f"    [DEBUG] 등급탈락 {stock.name}: Score={score.total}, Value={stock.trading_value//100_000_000}억, Rise={stock.change_pct}%, VolRatio={score_details.get('volume_ratio', 0)}")
                return None

            # 포지션 계산
            position = self.position_sizer.calculate(stock.close, grade)

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
                } for n in news_list[:5]],
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
                ai_evaluation=llm_result,
                themes=themes or []
            )
        except Exception as e:
            print(f"    ⚠️ 시그널 생성 오류 {stock.name}: {e}")
            return None

    async def _analyze_stock(self, stock: StockData, target_date: date) -> Optional[Signal]:
        """단일 종목 분석 (기존 호환용 - Batch 미사용)"""
        # 1. Base Analysis
        base_data = await self._analyze_base(stock)
        if not base_data: return None
        
        # 2. News
        news_list = await self._news.get_stock_news(stock.code, 3, stock.name)
        
        # 3. LLM (Single)
        llm_result = None
        if news_list and self.llm_analyzer.client:
            print(f"    [LLM] Analyzing {stock.name} news...")
            news_dicts = [{"title": n.title, "summary": n.summary} for n in news_list]
            llm_result = await self.llm_analyzer.analyze_news_sentiment(stock.name, news_dicts)

        # 4. Finalize
        return self._create_final_signal(
            stock, target_date, news_list, llm_result, base_data['charts'], base_data['supply']
        )


    def get_summary(self, signals: List[Signal]) -> Dict:
        """시그널 요약 정보"""
        summary = {
            "total": len(signals),
            "by_grade": {g: 0 for g in ['S', 'A', 'B', 'C', 'D']},
            "by_market": {},
            "total_position": 0,
            "total_risk": 0,
        }

        for s in signals:
            if hasattr(s, 'grade'):
                grade_val = getattr(s.grade, 'value', s.grade)
                if grade_val in summary["by_grade"]:
                    summary["by_grade"][grade_val] += 1
            
            if hasattr(s, 'market'):
                summary["by_market"][s.market] = summary["by_market"].get(s.market, 0) + 1
            
            if hasattr(s, 'position_size'):
                summary["total_position"] += s.position_size
            
            if hasattr(s, 'r_value') and hasattr(s, 'r_multiplier'):
                summary["total_risk"] += s.r_value * s.r_multiplier

        return summary


async def run_screener(
    capital: float = 50_000_000,
    markets: List[str] = None,
    target_date: str = None,  # YYYY-MM-DD 형식 (테스트용)
    top_n: int = 300,
) -> ScreenerResult:
    """
    스크리너 실행 (간편 함수)
    """
    start_time = time.time()
    
    # target_date 문자열을 date 객체로 변환
    parsed_date = None
    if target_date:
        try:
            parsed_date = datetime.strptime(target_date, '%Y-%m-%d').date()
            print(f"[테스트 모드] 지정 날짜 기준 분석: {target_date}")
        except ValueError:
            print(f"[경고] 날짜 형식 오류: {target_date} (YYYY-MM-DD 필요)")
            parsed_date = None

    async with SignalGenerator(capital=capital) as generator:
        signals = await generator.generate(target_date=parsed_date, markets=markets, top_n=top_n)
        summary = generator.get_summary(signals)
        
        # 2. Market Gate 실행
        print(f"\n[Market Gate] 시장 상태 분석 중...")
        market_status = {}
        try:
            market_gate = MarketGate()
            market_status = market_gate.analyze()
            market_gate.save_analysis(market_status)
            print(f"  -> 상태: {market_status.get('status')} (Score: {market_status.get('total_score')})")
        except Exception as e:
            logger.error(f"Market Gate Error: {e}")
        
        # 3. Final Market Summary (LLM)
        print(f"\n[Final Summary] 시장 요약 리포트 생성 중...")
        market_summary = ""
        try:
            market_summary = await generator.llm_analyzer.generate_market_summary(
                [s.to_dict() for s in signals]
            )
            print(f"  -> 요약 완료 ({len(market_summary)}자)")
        except Exception as e:
            logger.error(f"Market Summary Error: {e}")

        # 4. Trending Themes 집계
        trending_themes = []
        try:
            from collections import Counter
            all_themes = []
            for s in signals:
                if s.themes:
                    all_themes.extend(s.themes)
            
            theme_counts = Counter(all_themes)
            trending_themes = [theme for theme, count in theme_counts.most_common(20)]
            print(f"  -> Trending Themes: {trending_themes[:5]}...")
        except Exception as e:
            logger.error(f"Themes Error: {e}")

        processing_time = (time.time() - start_time) * 1000

        # [Sort] Grade (S>A>B>C>D) -> Score Descending
        def sort_key_gen(s):
            # Grade handling (Enum or String)
            g_val = getattr(s.grade, 'value', s.grade)
            grade_map = {'S': 5, 'A': 4, 'B': 3, 'C': 2, 'D': 1}
            grade_score = grade_map.get(str(g_val).strip().upper(), 0)
            
            # Score handling
            total_score = s.score.total if s.score else 0
            return (grade_score, total_score)
            
        signals.sort(key=sort_key_gen, reverse=True)

        # Phase 1 통과 수 집계
        phase1_passed = 0
        if hasattr(generator, 'pipeline_stats'):
            phase1_stats = generator.pipeline_stats.get('phase1', {}).get('stats', {})
            phase1_passed = phase1_stats.get('passed', 0)

        result = ScreenerResult(
            date=parsed_date if parsed_date else date.today(),
            total_candidates=phase1_passed,  # 1차 필터 통과 수 (CANDIDATES)
            filtered_count=len(signals),     # 최종 선정 수 (FILTERED)
            scanned_count=generator.scan_stats.get("scanned", 0),
            signals=signals,
            by_grade=summary["by_grade"],
            by_market=summary["by_market"],
            processing_time_ms=processing_time,
            market_status=market_status,
            market_summary=market_summary,
            trending_themes=trending_themes
        )

        # 결과 저장
        save_result_to_json(result)

        # 메신저 알림 발송 - [REMOVED] Scheduler handles this now (Double Send Fix)
        # try:
        #     from engine.messenger import Messenger
        #     messenger = Messenger()
        #     messenger.send_screener_result(result)
        # except Exception as e:
        #     print(f"[오류] 메신저 발송 실패: {e}")

        return result


async def analyze_single_stock_by_code(
    code: str,
    capital: float = 50_000_000,
) -> Optional[Signal]:
    """단일 종목 재분석 (Toss Data Priority)"""
    async with SignalGenerator(capital=capital) as generator:
        # 1. Toss 데이터 우선 조회
        stock = None
        try:
            toss_detail = generator._toss_collector.get_full_stock_detail(code)
            if toss_detail and toss_detail.get('name'):
                price_info = toss_detail.get('price', {})
                market_segment = toss_detail.get('market', 'KOSPI')
                
                # Market Correction (Toss might return 'KOSPI' or 'KOSDAQ' string)
                if 'KOSDAQ' in market_segment.upper():
                    market = 'KOSDAQ'
                else:
                    market = 'KOSPI'

                stock = StockData(
                    code=code,
                    name=toss_detail['name'],
                    market=market,
                    sector=toss_detail.get('sector', '기타'),
                    close=int(price_info.get('current', 0)),
                    change_pct=float(price_info.get('change_pct', 0)),
                    trading_value=float(price_info.get('trading_value', 0)),
                    volume=int(price_info.get('volume', 0)),
                    marcap=int(price_info.get('market_cap', 0)),
                    high_52w=int(price_info.get('high_52w', 0)),
                    low_52w=int(price_info.get('low_52w', 0))
                )
                logger.info(f"[SingleAnalysis] Toss Data Loaded for {code}: {stock.name} ({stock.close})")
        except Exception as e:
            logger.warning(f"[SingleAnalysis] Toss Data Failed: {e}")

        # 2. Fallback to KRX if Toss failed
        if not stock:
            detail = await generator._collector.get_stock_detail(code)
            if not detail:
                logger.error(f"[SingleAnalysis] Failed to fetch stock detail for {code}")
                return None

            # StockData 복원 (KRX Fallback)
            # 시장 정보가 KOSDAQ일 수 있으므로 pykrx 등에서 확인 필요하나 
            # KRXCollector._get_stock_name이 업데이트되었으므로 이름은 확보됨
            stock = StockData(
                code=code,
                name=detail.get('name', '알 수 없는 종목'),
                market='KOSDAQ' if detail.get('market') == 'KOSDAQ' else 'KOSPI', # KRXCollector need update to return market
                sector='기타',
                close=detail.get('close', 50000), # Fallback dummy
                change_pct=0,
                trading_value=100_000_000,
                volume=0,
                marcap=0
            )

        # 재분석 실행
        # (단일 분석 시점엔 장중일 수도 있으니 today 사용, 하지만 종가베팅은 보통 장 마감 후)
        new_signal = await generator._analyze_stock(stock, date.today())

        if new_signal:
            # JSON 업데이트
            update_single_signal_json(code, new_signal)

        return new_signal


def save_result_to_json(result: ScreenerResult):
    """결과 JSON 저장"""
    data_dir = "data"
    os.makedirs(data_dir, exist_ok=True)

    data = {
        "date": result.date.isoformat(),
        "total_candidates": result.total_candidates,
        "filtered_count": result.filtered_count,
        "signals": [s.to_dict() for s in result.signals],
        "by_grade": result.by_grade,
        "by_market": result.by_market,
        "processing_time_ms": result.processing_time_ms,
        "market_status": result.market_status,
        "market_summary": result.market_summary,
        "trending_themes": result.trending_themes,
        "scanned_count": getattr(result, "scanned_count", 0),
        "updated_at": datetime.now().isoformat()
    }

    # Daily 파일
    date_str = result.date.strftime("%Y%m%d")
    daily_path = os.path.join(data_dir, f"jongga_v2_results_{date_str}.json")

    with open(daily_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False, cls=NumpyEncoder)

    # Latest 파일
    latest_path = os.path.join(data_dir, "jongga_v2_latest.json")
    with open(latest_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False, cls=NumpyEncoder)

    print(f"\n[저장 완료] Daily: {daily_path}")
    print(f"[저장 완료] Latest: {latest_path}")


def update_single_signal_json(code: str, signal: Signal):
    """단일 종목 시그널 업데이트"""
    import glob

    data_dir = "data"
    latest_path = os.path.join(data_dir, "jongga_v2_latest.json")

    if not os.path.exists(latest_path):
        return

    with open(latest_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # 해당 종목 교체
    updated_signals = [
        signal.to_dict() if s["stock_code"] == code else s
        for s in data["signals"]
    ]

    data["signals"] = updated_signals
    
    # [Sort] Grade (S>A>B>C>D) -> Score Descending
    def sort_key_dict(s):
        grade_map = {'S': 5, 'A': 4, 'B': 3, 'C': 2, 'D': 1}
        grade_val = grade_map.get(str(s.get('grade', '')).strip().upper(), 0)
        
        score_obj = s.get('score', 0)
        if isinstance(score_obj, dict):
            total_score = score_obj.get('total', 0)
        else:
            try:
                total_score = float(score_obj)
            except (ValueError, TypeError):
                total_score = 0
                
        return (grade_val, total_score)

    data["signals"].sort(key=sort_key_dict, reverse=True)

    data["updated_at"] = datetime.now().isoformat()

    # 저장
    with open(latest_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False, cls=NumpyEncoder)

    # Daily 파일도 업데이트
    date_str = date.today().strftime("%Y%m%d")
    daily_path = os.path.join(data_dir, f"jongga_v2_results_{date_str}.json")
    if os.path.exists(daily_path):
        with open(daily_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False, cls=NumpyEncoder)


# 테스트용 메인
async def main():
    """테스트 실행"""
    print("=" * 60)
    print("종가베팅 시그널 생성기 v2")
    print("=" * 60)

    capital = 50_000_000
    print(f"\n자본금: {capital:,}원")
    print(f"R값: {capital * 0.005:,.0f}원 (0.5%)")

    result = await run_screener(capital=capital)

    print(f"\n처리 시간: {result.processing_time_ms:.0f}ms")
    print(f"생성된 시그널: {len(result.signals)}개")
    print(f"등급별: {result.by_grade}")

    print("\n" + "=" * 60)
    print("시그널 상세")
    print("=" * 60)

    for i, signal in enumerate(result.signals, 1):
        print(f"\n[{i}] {signal.stock_name} ({signal.stock_code})")
        print(f"    등급: {getattr(signal.grade, 'value', signal.grade)}")
        print(f"    점수: {signal.score.total}/12")
        print(f"    등락률: {signal.change_pct:+.2f}%")
        print(f"    진입가: {signal.entry_price:,}원")
        print(f"    손절가: {signal.stop_price:,}원")
        print(f"    목표가: {signal.target_price:,}원")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n중단됨")
