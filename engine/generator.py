#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
시그널 생성기 (Main Engine)
- Collector로부터 데이터 수집
- Scorer로 점수 계산
- PositionSizer로 자금 관리
- 최종 Signal 생성 (Batch LLM 지원)

REFACTORED: SignalGenerator 런타임 메서드는 generator_runtime_mixin.py로 분리됨.
"""

import asyncio
from datetime import date, datetime
from typing import Dict, List, Optional
import time
import sys
import os
import logging

# 모듈 경로 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.config import config as default_config
from engine.generator_result_storage import (
    save_result_to_json as _save_result_to_json_impl,
    update_single_signal_json as _update_single_signal_json_impl,
)
from engine.generator_runtime_helpers import (
    collect_trending_themes as _collect_trending_themes_impl,
    generate_market_summary as _generate_market_summary_impl,
    parse_target_date as _parse_target_date_impl,
    run_market_gate_analysis as _run_market_gate_analysis_impl,
    sort_signals_by_grade_and_score as _sort_signals_by_grade_and_score_impl,
)
from engine.generator_runtime_mixin import SignalGeneratorRuntimeMixin
from engine.llm_analyzer import LLMAnalyzer
from engine.models import ScreenerResult, Signal, StockData
from engine.position_sizer import PositionSizer
from engine.scorer import Scorer

logger = logging.getLogger(__name__)


def _normalize_total_candidates(total_candidates: Optional[int], filtered_count: int) -> int:
    """후보/최종 개수 불변식(total_candidates >= filtered_count) 보장."""
    base = int(total_candidates or 0)
    final_count = int(filtered_count or 0)

    if base < final_count:
        logger.warning(
            "[Counts] total_candidates(%s) < filtered_count(%s). "
            "total_candidates를 filtered_count로 보정합니다.",
            base,
            final_count,
        )
        return final_count
    return base


class SignalGenerator(SignalGeneratorRuntimeMixin):
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

        self._collector = None
        self._news = None
        self._naver = None
        self._toss_collector = None

        # 스캔 통계
        self.scan_stats = {
            "scanned": 0,
            "phase1": 0,
            "phase2": 0,
            "final": 0,
        }

        # 탈락 통계 (진단용)
        self.drop_stats = {
            "low_trading_value": 0,
            "low_pre_score": 0,
            "no_news": 0,
            "grade_fail": 0,
            "other": 0,
        }


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
    parsed_date = _parse_target_date_impl(target_date)

    async with SignalGenerator(capital=capital) as generator:
        signals = await generator.generate(target_date=parsed_date, markets=markets, top_n=top_n)
        summary = generator.get_summary(signals)

        # 2. Market Gate 실행
        market_status = _run_market_gate_analysis_impl(logger=logger)

        # 3. Final Market Summary (LLM)
        market_summary = await _generate_market_summary_impl(
            llm_analyzer=generator.llm_analyzer,
            signals=signals,
            logger=logger,
        )

        # 4. Trending Themes 집계
        trending_themes = _collect_trending_themes_impl(
            signals=signals,
            logger=logger,
        )

        processing_time = (time.time() - start_time) * 1000

        # [Sort] Grade (S>A>B>C>D) -> Score Descending
        _sort_signals_by_grade_and_score_impl(signals)

        # Phase 1 통과 수 집계
        phase1_passed = generator.scan_stats.get("phase1", 0)
        if phase1_passed == 0 and hasattr(generator, 'pipeline_stats'):
            # fallback for backward compatibility
            phase1_stats = generator.pipeline_stats.get('phase1', {}).get('stats', {})
            phase1_passed = int(phase1_stats.get('passed', 0))

        filtered_count = len(signals)
        total_candidates = _normalize_total_candidates(phase1_passed, filtered_count)

        result = ScreenerResult(
            date=parsed_date if parsed_date else date.today(),
            total_candidates=total_candidates,  # 1차 필터 통과 수 (CANDIDATES)
            filtered_count=filtered_count,      # 최종 선정 수 (FILTERED)
            scanned_count=generator.scan_stats.get("scanned", 0),
            signals=signals,
            by_grade=summary["by_grade"],
            by_market=summary["by_market"],
            processing_time_ms=processing_time,
            market_status=market_status,
            market_summary=market_summary,
            trending_themes=trending_themes,
        )

        # 결과 저장
        save_result_to_json(result)

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
                    low_52w=int(price_info.get('low_52w', 0)),
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
            stock = StockData(
                code=code,
                name=detail.get('name', '알 수 없는 종목'),
                market='KOSDAQ' if detail.get('market') == 'KOSDAQ' else 'KOSPI',
                sector='기타',
                close=detail.get('close', 50000),
                change_pct=0,
                trading_value=100_000_000,
                volume=0,
                marcap=0,
            )

        # 재분석 실행
        new_signal = await generator._analyze_stock(stock, date.today())

        if new_signal:
            # JSON 업데이트
            update_single_signal_json(code, new_signal)

        return new_signal


def save_result_to_json(result: ScreenerResult):
    """결과 JSON 저장"""
    _save_result_to_json_impl(result, data_dir="data")


def update_single_signal_json(code: str, signal: Signal):
    """단일 종목 시그널 업데이트"""
    _update_single_signal_json_impl(
        code=code,
        signal=signal,
        data_dir="data",
        as_of_date=date.today(),
    )


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
