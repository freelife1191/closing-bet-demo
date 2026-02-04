#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
시그널 생성기 (Main Engine)
- Collector로부터 데이터 수집
- Scorer로 점수 계산
- PositionSizer로 자금 관리
- 최종 Signal 생성 (Batch LLM 지원)
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

from engine.config import config, app_config
import engine.shared as shared_state
from engine.models import (
    StockData, Signal, SignalStatus, ScoreDetail, ChecklistDetail, ScreenerResult, ChartData, Grade
)
from engine.collectors import KRXCollector, EnhancedNewsCollector, NaverFinanceCollector
from engine.scorer import Scorer
from engine.position_sizer import PositionSizer

from engine.llm_analyzer import LLMAnalyzer
from engine.market_gate import MarketGate

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
        self.config = config
        self.capital = capital

        self.scorer = Scorer(self.config)
        self.position_sizer = PositionSizer(capital, self.config)
        self.llm_analyzer = LLMAnalyzer()

        self._collector: Optional[KRXCollector] = None
        self._news: Optional[EnhancedNewsCollector] = None
        self._naver: Optional[NaverFinanceCollector] = None
        
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
        return self

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
        """시그널 생성 (Batch Processing 적용)"""
        start_time = time.time()  # [Fix] 시작 시간 초기화

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
            logger.info(f"[종가베팅] {market} 스크리닝 시작 (v2.2 Batch)")
            logger.info(f"="*60)
            print(f"\n[{market}] 상승률 상위 종목 스크리닝... (v2.2 Batch)")

            # 1. 상승률 상위 종목 조회 (테스트 모드 시 지정 날짜 사용)
            target_date_str = target_date.strftime('%Y%m%d') if target_date else None
            candidates = await self._collector.get_top_gainers(market, top_n, target_date_str)
            logger.info(f"[{market}] 상승률 상위 데이터 수집 완료: {len(candidates)}개")
            print(f"  - 1차 필터 통과: {len(candidates)}개")
            
            # 통계 업데이트
            self.scan_stats["scanned"] += len(candidates)

            # --- Phase 1: Base Analysis & Pre-Screening ---
            pending_items = []  # {'stock':, 'charts':, 'supply':, 'news':}
            
            print(f"  [Phase 1] 기본 분석 및 선별 진행 중...")
            for i, stock in enumerate(candidates):
                if shared_state.STOP_REQUESTED:
                    print(f"\n[STOP] 사용자 중단 요청 감지")
                    raise Exception("사용자 중단 요청")
                base_data = await self._analyze_base(stock)
                
                # 1차 필터 조건 강화 (2026-02-05):
                # - Pre-Score 방식 대신 Determine Grade(D급 이상) 조건을 선행 적용
                # - LLM 비용 절감을 위해 최종 후보군 수준만 분석
                # PRE_SCORE_THRESHOLD = 2 (Deprecated)

                
                if base_data:
                    stock_obj = base_data['stock']
                    pre_score = base_data['pre_score']
                    score_details = base_data.get('score_details', {})
                    trading_value = getattr(stock_obj, 'trading_value', 0)
                    volume_ratio = score_details.get('volume_ratio', 0)
                    
                    # 1. 1차 필터: 기본 조건 (거래대금, 거래량 등)
                    # - 거래대금 300억 이상 (Config Min)
                    # - 거래량 배수 2배 이상
                    MIN_TRADING_VALUE = self.scorer.config.trading_value_min
                    
                    if trading_value < MIN_TRADING_VALUE:
                        self.drop_stats["low_trading_value"] += 1
                        print(f"    [Drop] 거래대금 부족: {stock.name} ({trading_value//100_000_000}억 < {MIN_TRADING_VALUE//100_000_000}억)")
                        continue
                        
                    if volume_ratio < 2.0:
                        self.drop_stats["low_volume_ratio"] += 1
                        print(f"    [Drop] 거래량배수 부족: {stock.name} ({volume_ratio:.1f} < 2.0)")
                        continue

                    # 2. 최종 필터 (Pre-LLM): 등급 미달 사전 차단
                    # LLM 없이도 최소 D등급 기준(6점)은 넘어야 함
                    # (scorer.determine_grade는 거래대금, 등락률, 점수 등을 종합 평가)
                    temp_grade = self.scorer.determine_grade(
                        stock_obj, pre_score, score_details, base_data['supply'], base_data['charts']
                    )
                    
                    if temp_grade:
                        # 통과
                        pending_items.append(base_data)
                        grade_val = getattr(temp_grade, 'value', temp_grade)
                        logger.debug(f"[Phase1 Pass] {stock.name}: Grade={grade_val}, Score={pre_score.total}")
                    else:
                        # 등급 미달 탈락
                        self.drop_stats["grade_fail"] += 1
                        # 1차 필터는 통과했으나 등급 요건 불충족
                        print(f"    [Drop] 등급 미달: {stock.name} (Score={pre_score.total}, Pre-Grade=None)")
                
                if (i+1) % 10 == 0:
                    print(f"    Processing {i+1}/{len(candidates)}...", end='\r')
            
            logger.info(f"[Phase1 완료] {market}: {len(pending_items)}개 통과 (탈락: 거래대금부족={self.drop_stats['low_trading_value']}, 거래량부족={self.drop_stats['low_volume_ratio']}, 등급미달={self.drop_stats['grade_fail']})")
            print(f"\n    -> 1차 선별 완료: {len(pending_items)}개 (사전 등급 D급 이상, 대금/거래량 충족)")
            self.scan_stats["phase1"] += len(pending_items)

            # --- Phase 2: News Fetching & Batch LLM ---
            print(f"  [Phase 2] 뉴스 수집 및 Batch LLM 분석...")
            
            # 뉴스 수집
            stocks_to_analyze = []
            news_fail_count = 0
            for item in pending_items:
                if shared_state.STOP_REQUESTED:
                    print(f"\n[STOP] 사용자 중단 요청 감지")
                    raise Exception("사용자 요청 중단")
                stock = item['stock']
                news_list = await self._news.get_stock_news(stock.code, 3, stock.name)
                if news_list:
                    item['news'] = news_list
                    stocks_to_analyze.append(item)
                    logger.debug(f"[뉴스] {stock.name}: {len(news_list)}개 수집")
                else:
                    news_fail_count += 1
                    self.drop_stats["no_news"] += 1
                    logger.debug(f"[뉴스 없음] {stock.name}")
            
            logger.info(f"[Phase2 뉴스수집] {market}: {len(stocks_to_analyze)}개 성공, {news_fail_count}개 뉴스 없음")
            print(f"    -> 뉴스 수집 완료: {len(stocks_to_analyze)}개 종목 (뉴스 없음: {news_fail_count}개)")

            # Market Gate 상태 조회
            market_status = None
            try:
                from engine.market_gate import MarketGate
                mg = MarketGate()
                market_status = mg.analyze()
            except Exception as e:
                print(f"    ⚠️ Market Gate 조회 실패: {e}")

            # Batch LLM Analysis
            llm_results_map = {}
            if self.llm_analyzer.client and stocks_to_analyze:
                # Provider check (Analysis LLM)
                is_analysis_llm = app_config.LLM_PROVIDER == 'gemini' # or other analysis providers
                
                # 5개씩 Chunking
                chunk_size = app_config.ANALYSIS_LLM_CHUNK_SIZE if is_analysis_llm else app_config.LLM_CHUNK_SIZE
                chunks = [stocks_to_analyze[i:i + chunk_size] for i in range(0, len(stocks_to_analyze), chunk_size)]
                
                total_chunks = len(chunks)
                # 5. Parallel Batch Processing
                concurrency = app_config.ANALYSIS_LLM_CONCURRENCY if is_analysis_llm else app_config.LLM_CONCURRENCY
                semaphore = asyncio.Semaphore(concurrency)
                
                async def _process_chunk(chunk_idx, chunk_data):
                    async with semaphore:
                        try:
                            start = time.time()
                            print(f"    [LLM Batch] Processing Chunk {chunk_idx}/{total_chunks} ({len(chunk_data)} stocks)...")
                            # chunk_data는 이미 full context dict 리스트임
                            result = await self.llm_analyzer.analyze_news_batch(chunk_data, market_status)
                            elapsed = time.time() - start
                            print(f"    ✅ Chunk {chunk_idx} Done in {elapsed:.2f}s")
                            return result
                        except Exception as e:
                            print(f"    ⚠️ Chunk {chunk_idx} Error: {e}")
                            return {}

                tasks = [
                    _process_chunk(i, chunk) 
                    for i, chunk in enumerate(chunks, 1)
                ]
                
                print(f"    🚀 Starting {len(tasks)} batch requests (Concurrency: {concurrency})...")
                results_list = await asyncio.gather(*tasks)
                
                for res in results_list:
                    if res:
                        llm_results_map.update(res)

            # --- Phase 3: Final Scoring ---
            print(f"  [Phase 3] 최종 점수 계산...")
            for item in stocks_to_analyze:
                stock = item['stock']
                llm_result = llm_results_map.get(stock.name)
                
                # 테마 수집
                themes = await self._naver.get_themes(stock.code) if self._naver else []
                
                # 최종 시그널 생성
                signal = self._create_final_signal(
                    stock, target_date, item['news'], llm_result, item['charts'], item['supply'], themes
                )

                if signal:
                    grade_val = getattr(signal.grade, 'value', signal.grade)
                    if grade_val != 'C':
                        all_signals.append(signal)
                        logger.info(f"[시그널 생성] {stock.name}: {grade_val}급 (점수: {signal.score.total}, 거래대금: {stock.trading_value//100_000_000}억, 등락률: {stock.change_pct:.1f}%)")
                        print(f"    ✅ {stock.name}: {grade_val}급 (점수: {signal.score.total})")
                else:
                    self.drop_stats["grade_fail"] += 1

            # 중간 결과 저장 (KOSPI 분석 완료 후 즉시 반영을 위해)
            if market == markets[0] and len(markets) > 1:
                mid_processing_time = (time.time() - start_time) * 1000
                mid_result = ScreenerResult(
                    date=target_date, # [Fix] parsed_date -> target_date
                    total_candidates=len(all_signals),
                    filtered_count=self.scan_stats.get("phase1", 0), # [Fix] generator -> self
                    scanned_count=self.scan_stats.get("scanned", 0),  # [Fix] generator -> self
                    signals=all_signals,
                    by_grade=self.get_summary(all_signals)["by_grade"], # [Fix] generator -> self
                    by_market=self.get_summary(all_signals)["by_market"], # [Fix] generator -> self
                    processing_time_ms=mid_processing_time,
                    market_status=market_status,
                    market_summary="", # 중간 단계에서는 요약 생략
                    trending_themes=[] # 중간 단계에서는 테마 생략
                )
                save_result_to_json(mid_result)
                logger.info(f"[{market}] 분석 완료 - 중간 결과 저장됨 ({len(all_signals)}개 시그널)")

        return all_signals

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
                volume_ratio=score_details.get('volume_ratio', 0.0),
                status=SignalStatus.PENDING,
                created_at=datetime.now(),
                score_details=score_details,
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

        result = ScreenerResult(
            date=parsed_date if parsed_date else date.today(),
            total_candidates=len(signals),
            filtered_count=generator.scan_stats.get("phase1", 0),
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

        # 메신저 알림 발송
        try:
            from engine.messenger import Messenger
            messenger = Messenger()
            messenger.send_screener_result(result)
        except Exception as e:
            print(f"[오류] 메신저 발송 실패: {e}")

        return result


async def analyze_single_stock_by_code(
    code: str,
    capital: float = 50_000_000,
) -> Optional[Signal]:
    """단일 종목 재분석"""
    async with SignalGenerator(capital=capital) as generator:
        # 기본 상세 정보 조회
        detail = await generator._collector.get_stock_detail(code)
        if not detail:
            return None

        # StockData 복원
        stock = StockData(
            code=code,
            name=detail.get('name', '알 수 없는 종목'),
            market='KOSPI',
            sector='기타',
            close=50000,
            change_pct=0,
            trading_value=100_000_000,
            volume=0,
            marcap=0
        )

        # 재분석 실행
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
        json.dump(data, f, indent=2, ensure_ascii=False)

    # Latest 파일
    latest_path = os.path.join(data_dir, "jongga_v2_latest.json")
    with open(latest_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

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
    data["updated_at"] = datetime.now().isoformat()

    # 저장
    with open(latest_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    # Daily 파일도 업데이트
    date_str = date.today().strftime("%Y%m%d")
    daily_path = os.path.join(data_dir, f"jongga_v2_results_{date_str}.json")
    if os.path.exists(daily_path):
        with open(daily_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)


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
