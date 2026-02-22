#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
run_screener 런타임 보조 유틸.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime
from typing import Dict, List, Optional

from engine.market_gate import MarketGate


def parse_target_date(target_date: Optional[str]) -> Optional[datetime.date]:
    """YYYY-MM-DD 문자열을 date로 파싱."""
    if not target_date:
        return None
    try:
        parsed_date = datetime.strptime(target_date, "%Y-%m-%d").date()
        print(f"[테스트 모드] 지정 날짜 기준 분석: {target_date}")
        return parsed_date
    except ValueError:
        print(f"[경고] 날짜 형식 오류: {target_date} (YYYY-MM-DD 필요)")
        return None


def run_market_gate_analysis(*, logger) -> Dict:
    """Market Gate 분석 실행."""
    print("\n[Market Gate] 시장 상태 분석 중...")
    market_status = {}
    try:
        market_gate = MarketGate()
        market_status = market_gate.analyze()
        market_gate.save_analysis(market_status)
        print(f"  -> 상태: {market_status.get('status')} (Score: {market_status.get('total_score')})")
    except Exception as error:
        logger.error(f"Market Gate Error: {error}")
    return market_status


async def generate_market_summary(*, llm_analyzer, signals: List, logger) -> str:
    """LLM 시장 요약 생성."""
    print("\n[Final Summary] 시장 요약 리포트 생성 중...")
    market_summary = ""
    try:
        market_summary = await llm_analyzer.generate_market_summary([signal.to_dict() for signal in signals])
        print(f"  -> 요약 완료 ({len(market_summary)}자)")
    except Exception as error:
        logger.error(f"Market Summary Error: {error}")
    return market_summary


def collect_trending_themes(*, signals: List, logger) -> List[str]:
    """시그널에서 트렌딩 테마 상위 20개를 집계."""
    trending_themes: List[str] = []
    try:
        all_themes: List[str] = []
        for signal in signals:
            if signal.themes:
                all_themes.extend(signal.themes)

        theme_counts = Counter(all_themes)
        trending_themes = [theme for theme, _ in theme_counts.most_common(20)]
        print(f"  -> Trending Themes: {trending_themes[:5]}...")
    except Exception as error:
        logger.error(f"Themes Error: {error}")
    return trending_themes


def sort_signals_by_grade_and_score(signals: List) -> None:
    """Grade(S>A>B) 우선, 동일 등급 내 점수 내림차순 정렬."""

    def sort_key(signal):
        grade_val = getattr(signal.grade, "value", signal.grade)
        grade_map = {"S": 3, "A": 2, "B": 1}
        grade_score = grade_map.get(str(grade_val).strip().upper(), 0)
        total_score = signal.score.total if signal.score else 0
        return grade_score, total_score

    signals.sort(key=sort_key, reverse=True)

