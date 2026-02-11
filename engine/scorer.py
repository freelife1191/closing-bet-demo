#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Engine - Scorer (12점 점수 시스템)

Refactored to use GradeClassifier module for grade determination logic.

Created: 2024-12-01
Refactored: 2025-02-11 (Phase 4)
"""
import logging
from typing import Optional, List, Dict

from engine.models import (
    StockData, ScoreDetail, ChecklistDetail, ChartData, SupplyData, Grade, NewsItem
)
from engine.config import config, SignalConfig
from engine.constants import VOLUME, PRICE_CHANGE, TRADING_VALUES
from engine.grade_classifier import FilterValidator, GradeClassifier

logger = logging.getLogger(__name__)


class Scorer:
    """
    12점 점수 시스템 (Refactored)

    Changes (Phase 4):
    - Grade determination logic extracted to GradeClassifier
    - Filter validation extracted to FilterValidator
    - determine_grade() method simplified from 111 to ~30 lines
    """

    def __init__(self, config: SignalConfig = None):
        """
        초기화

        Args:
            config: (Optional) SignalConfig 인스턴스
        """
        self.config = config or SignalConfig()
        self.max_score = 12

        # Helper 클래스 초기화
        self.filter_validator = FilterValidator(self.config)
        self.grade_classifier = GradeClassifier(self.config)

    def calculate(
        self,
        stock: StockData,
        charts: Optional[ChartData] = None,
        news: Optional[List[NewsItem]] = None,
        supply: Optional[SupplyData] = None,
        llm_result: Optional[Dict] = None
    ) -> tuple[ScoreDetail, ChecklistDetail, Dict]:
        """
        점수 계산

        Args:
            stock: 종목 데이터
            charts: 차트 데이터
            news: 뉴스 리스트
            supply: 수급 데이터
            llm_result: LLM 분석 결과

        Returns:
            (ScoreDetail, ChecklistDetail, Dict) 튜플
        """
        score = ScoreDetail()
        checklist = ChecklistDetail()

        # 1. 뉴스/재료 (0-3점)
        score.news, checklist.has_news, checklist.news_sources, score.llm_reason = \
            self._score_news(news, llm_result, stock)

        # 2. 거래대금 (0-3점)
        score.volume = self._score_volume(stock)

        # 3. 차트패턴 (0-2점)
        score.chart, checklist.is_new_high, checklist.is_breakout, checklist.ma_aligned = \
            self._score_chart(stock, charts)

        # 4. 캔들형태 (0-1점)
        score.candle = self._score_candle(charts)

        # 5. 기간조정 (0-1점)
        score.timing = self._score_timing(stock, charts)

        # 6. 수급 (0-2점)
        score.supply, checklist.supply_positive = self._score_supply(supply)

        # 기본 점수 계산
        base_score = (
            score.news + score.volume + score.chart +
            score.candle + score.timing + score.supply
        )

        # 거래량 배수 계산
        volume_ratio = self._calculate_volume_ratio(stock, charts)

        # 가산점 계산 (V2 Logic)
        bonus_score = self._calculate_bonus(stock.change_pct, volume_ratio)

        # 총점 계산
        score.total = base_score + bonus_score

        # 상세 내역
        details = self._build_score_details(
            stock, supply, score, base_score, bonus_score, volume_ratio
        )

        return score, checklist, details

    def determine_grade(
        self,
        stock: StockData,
        score: ScoreDetail,
        score_details: Dict,
        supply: SupplyData,
        charts: ChartData,
        allow_no_news: bool = False
    ) -> Optional[Grade]:
        """
        최종 등급 판정 (S/A/B/C)

        Refactored (Phase 4):
        - Filter validation delegated to FilterValidator
        - Grade classification delegated to GradeClassifier
        - Simplified from 111 lines to ~30 lines

        Args:
            stock: 종목 데이터
            score: 점수 상세
            score_details: 점수 상세 딕셔너리
            supply: 수급 데이터
            charts: 차트 데이터
            allow_no_news: 뉴스 없음 허용 여부

        Returns:
            Grade 객체 또는 None
        """
        # 1. 필터링 검증
        filter_result = self.filter_validator.validate(
            stock=stock,
            score=score,
            score_details=score_details,
            supply=supply,
            charts=charts,
            allow_no_news=allow_no_news
        )

        if not filter_result.passed:
            logger.debug(f"  -> [Drop] {filter_result.reason}")
            return None

        # 2. 등급 판정
        return self.grade_classifier.classify(
            stock=stock,
            score=score,
            score_details=score_details,
            supply=supply
        )

    # ========================================================================
    # Private Methods - Scoring
    # ========================================================================

    def _score_news(
        self,
        news: Optional[List[NewsItem]],
        llm_result: Optional[Dict],
        stock: StockData = None
    ) -> tuple[int, bool, List[str], str]:
        """뉴스 점수 (0-3점) - 거래대금 Fallback 추가"""
        # 1. LLM/News 기반 점수
        llm_score = llm_result.get('score', 0) if llm_result else 0
        llm_reason = llm_result.get('reason', '') if llm_result else ""

        has_news = news is not None and len(news) > 0
        sources = [n.source for n in news] if news else []

        news_score = llm_score
        if has_news and news_score == 0:
            news_score = 1

        # 2. Fallback: 뉴스가 없어도 거래대금이 크면 점수 부여
        if news_score == 0 and stock:
            if stock.trading_value >= TRADING_VALUES.NEWS_FALLBACK_S:  # 5000억
                news_score = 3
            elif stock.trading_value >= TRADING_VALUES.NEWS_FALLBACK_A:  # 1000억
                news_score = 2
            elif stock.trading_value >= TRADING_VALUES.NEWS_FALLBACK_B:  # 500억
                news_score = 1

        return min(3, news_score), has_news, sources, llm_reason

    def _score_volume(self, stock: StockData) -> int:
        """거래대금 점수 (0-3점)"""
        if stock.trading_value >= self.config.trading_value_s:
            return 3
        elif stock.trading_value >= self.config.trading_value_a:
            return 2
        elif stock.trading_value >= self.config.trading_value_b:
            return 1
        else:
            return 0

    def _score_candle(self, charts: Optional[ChartData]) -> int:
        """캔들형태 점수 (0-1점)"""
        if not charts:
            return 0

        recent_candles = 5
        if len(charts.lows) < recent_candles or len(charts.closes) < recent_candles:
            return 0

        last_lows = charts.lows[-recent_candles:]
        last_highs = charts.highs[-recent_candles:]
        last_closes = charts.closes[-recent_candles:]
        last_opens = charts.opens[-recent_candles:]

        # 장대양봉: 상승폭이 하락폭보다 2배 이상
        for i in range(1, recent_candles):
            body_size = last_closes[i] - last_opens[i]
            if body_size > 0 and abs(body_size) > abs(last_lows[i] - last_highs[i]) * 2:
                # 윗꼬리 짧음 확인
                upper_shadow = last_highs[i] - max(last_opens[i], last_closes[i])
                if upper_shadow < body_size * 0.3:
                    return 1

        return 0

    def _score_timing(self, stock: StockData, charts: Optional[ChartData]) -> int:
        """기간조정 점수 (0-1점): 볼린저밴드 수축 및 횡보 후 돌파"""
        if not charts or len(charts.closes) < 20:
            return 0

        import math

        closes = charts.closes
        band_widths = []
        is_breakout = False

        # 최근 20일간의 Band Width 계산
        for i in range(20):
            end_idx = len(closes) - i
            start_idx = end_idx - 20

            if start_idx < 0:
                break

            window = closes[start_idx:end_idx]
            avg = sum(window) / 20
            variance = sum([(x - avg) ** 2 for x in window]) / 20
            std_dev = math.sqrt(variance)

            upper = avg + (std_dev * 2)
            lower = avg - (std_dev * 2)

            if avg > 0:
                bw = (upper - lower) / avg
                band_widths.append(bw)

            # 오늘(i=0) 기준 상단 돌파 여부 확인
            if i == 0:
                if closes[-1] > upper:
                    is_breakout = True

        if len(band_widths) < 10:
            return 0

        # 수축 (Contraction)
        recent_bw_avg = sum(band_widths[1:6]) / 5  # 어제부터 5일간
        past_bw_avg = sum(band_widths[6:]) / len(band_widths[6:])  # 그 이전

        is_contracted = (recent_bw_avg < past_bw_avg * 0.8) or (recent_bw_avg < 0.15)

        # 횡보 후 돌파
        if is_contracted and is_breakout:
            return 1

        return 0

    def _score_chart(
        self,
        stock: StockData,
        charts: Optional[ChartData]
    ) -> tuple[int, bool, bool, bool]:
        """차트패턴 점수 (0-2점)"""
        if not charts:
            return 0, False, False, False

        score = 0
        is_new_high = False
        is_breakout = False
        ma_aligned = False

        # 52주 고가 돌파
        if stock.high_52w > 0 and stock.close > stock.high_52w:
            is_new_high = True
            score += 1

        # 이평선 정배열
        if len(charts.closes) >= 20:
            closes = charts.closes
            ma20 = sum(closes[-20:]) / 20
            ma60 = sum(closes[-60:]) / 60

            if ma20 > ma60 and stock.close > ma20:
                ma_aligned = True
                score += 1

        # 돌파 확인 (최근 5일 고가 돌파)
        if len(charts.highs) >= 10:
            recent_high = max(charts.highs[-10:-5])
            recent_5_high = max(charts.highs[-5:])
            if recent_5_high > recent_high:
                is_breakout = True

        return min(2, score), is_new_high, is_breakout, ma_aligned

    def _score_supply(self, supply: Optional[SupplyData]) -> tuple[int, bool]:
        """수급 점수 (0-2점)"""
        if not supply:
            return 0, False

        # 외인+기관 동시 순매수
        foreign_positive = supply.foreign_buy_5d > 0
        inst_positive = supply.inst_buy_5d > 0

        score = 0
        if foreign_positive:
            score += 1
        if inst_positive:
            score += 1

        return score, score > 0

    def _calculate_volume_ratio(self, stock: StockData, charts: Optional[ChartData]) -> float:
        """거래량 배수 계산"""
        volume_ratio = 0.0

        if charts and len(charts.volumes) >= 2:
            # Toss 데이터 등으로 stock.volume이 업데이트되었을 수 있으므로
            # charts.volumes[-1] 대신 stock.volume을 우선 사용
            today_vol = stock.volume if stock.volume > 0 else charts.volumes[-1]

            lookback = min(20, len(charts.volumes) - 1)
            if lookback > 0:
                # 평균은 과거 데이터(어제까지)로 계산
                avg_vol = sum(charts.volumes[-lookback-1:-1]) / lookback
                if avg_vol > 0:
                    volume_ratio = round(today_vol / avg_vol, 2)

        return volume_ratio

    def _calculate_bonus(self, change_pct: float, volume_ratio: float) -> int:
        """가산점 계산 (최대 9점)"""
        bonus = 0

        # 1. 거래량 급증 (최대 4점)
        if volume_ratio >= 10: bonus += 4
        elif volume_ratio >= 5: bonus += 3
        elif volume_ratio >= 3: bonus += 2
        elif volume_ratio >= 2: bonus += 1

        # 2. 장대양봉 (최대 5점)
        if change_pct >= 25: bonus += 5
        elif change_pct >= 20: bonus += 4
        elif change_pct >= 15: bonus += 3
        elif change_pct >= 10: bonus += 2
        elif change_pct >= 5: bonus += 1

        return bonus

    def _build_score_details(
        self,
        stock: StockData,
        supply: SupplyData,
        score: ScoreDetail,
        base_score: int,
        bonus_score: int,
        volume_ratio: float
    ) -> Dict:
        """점수 상세 딕셔너리 빌드"""
        # 외인/기관 수급 데이터 추출
        foreign_net_buy = 0
        inst_net_buy = 0
        if supply:
            foreign_net_buy = supply.foreign_buy_5d
            inst_net_buy = supply.inst_buy_5d

        return {
            'news': score.news,
            'volume': score.volume,
            'chart': score.chart,
            'candle': score.candle,
            'consolidation': score.timing,
            'supply': score.supply,
            'rise_pct': stock.change_pct,
            'volume_ratio': volume_ratio,
            'foreign_net_buy': foreign_net_buy,
            'inst_net_buy': inst_net_buy,
            'base_score': base_score,
            'bonus_score': bonus_score
        }
