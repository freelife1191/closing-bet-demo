#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Engine - Scorer (12점 점수 시스템)
"""
import logging
from typing import Optional, List, Dict
from dataclasses import dataclass
from engine.models import (
    StockData, ScoreDetail, ChecklistDetail, ChartData, SupplyData, Grade, NewsItem
)
from engine.config import config, SignalConfig

logger = logging.getLogger(__name__)


class Scorer:
    """12점 점수 시스템"""

    def __init__(self, config: SignalConfig = None):
        self.config = config or SignalConfig()
        self.max_score = 12

    def calculate(
        self,
        stock: StockData,
        charts: Optional[ChartData] = None,
        news: Optional[List[NewsItem]] = None,
        supply: Optional[SupplyData] = None,
        llm_result: Optional[Dict] = None
    ) -> tuple[ScoreDetail, ChecklistDetail, Dict]:
        """점수 계산"""
        score = ScoreDetail()
        checklist = ChecklistDetail()

        # 1. 뉴스/재료 (0-3점)
        score.news, checklist.has_news, checklist.news_sources, score.llm_reason = self._score_news(news, llm_result)

        # 2. 거래대금 (0-3점)
        score.volume = self._score_volume(stock)

        # 3. 차트패턴 (0-2점)
        score.chart, checklist.is_new_high, checklist.is_breakout, checklist.ma_aligned = self._score_chart(stock, charts)

        # 4. 캔들형태 (0-1점)
        score.candle = self._score_candle(charts)

        # 5. 기간조정 (0-1점)
        score.timing = self._score_timing(stock, charts)

        # 6. 수급 (0-2점)
        score.supply, checklist.supply_positive = self._score_supply(supply)
        
        # 상세 내역 (프론트엔드 필터용)
        # 거래량 배수 = 오늘 거래량 / 최근 20일 평균 거래량 (네이버/토스 기준)
        volume_ratio = 0.0
        if charts and len(charts.volumes) >= 2:  # 최소 2일치 데이터
            today_vol = charts.volumes[-1]
            # 최근 20일 평균 (데이터가 부족하면 있는 만큼 사용, 최소 1일)
            lookback = min(20, len(charts.volumes) - 1)
            if lookback > 0:
                avg_vol = sum(charts.volumes[-lookback-1:-1]) / lookback
                if avg_vol > 0:
                    volume_ratio = round(today_vol / avg_vol, 2)
        
        # 외인/기관 수급 데이터 추출
        foreign_net_buy = 0
        inst_net_buy = 0
        if supply:
            foreign_net_buy = supply.foreign_buy_5d
            inst_net_buy = supply.inst_buy_5d
        
        details = {
            'news': score.news,
            'volume': score.volume,
            'chart': score.chart,
            'candle': score.candle,
            'consolidation': score.timing,
            'supply': score.supply,
            'rise_pct': stock.change_pct,
            'volume_ratio': volume_ratio,
            'foreign_net_buy': foreign_net_buy,
            'inst_net_buy': inst_net_buy
        }

        return score, checklist, details

    def _score_news(self, news: Optional[List[NewsItem]], llm_result: Optional[Dict]) -> tuple[int, bool, List[str], str]:
        """뉴스 점수 (0-3점)"""
        if not llm_result:
            return 0, False, [], ""

        # LLM 호재 점수 (0-3점)
        llm_score = llm_result.get('score', 0)
        llm_reason = llm_result.get('reason', '') # 분석 사유

        # 뉴스 출처 수집
        sources = []
        if news:
            sources = [n.source for n in news]

        # 뉴스가 있으면 +1점 (최소)
        has_news = len(news) > 0

        final_score = llm_score
        if has_news and final_score == 0:
            final_score = 1

        return min(3, final_score), has_news, sources, llm_reason

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

        # 장대양봉 확인
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
        """기간조정 점수 (0-1점)"""
        if not charts:
            return 0

        if len(charts.closes) < 20:
            return 0

        # 볼린저 밴드 수축 확인 (Band Width)
        # Band Width = (Upper - Lower) / Middle
        # 수축 기준: 최근 5일 평균 Band Width가 과거 20일 평균보다 작음 (변동성 축소)
        
        import math
        
        closes = charts.closes
        band_widths = []
        
        # 최근 20일간의 Band Width 계산
        for i in range(20):
            # i일 전 기준 20일 데이터 (window)
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
        
        if len(band_widths) < 10:
            return 0
            
        # 최근 3일 평균 Band Width
        recent_bw = sum(band_widths[:3]) / 3
        # 과거 (3일 이후) 평균 Band Width
        past_bw = sum(band_widths[3:]) / len(band_widths[3:])
        
        # 변동성이 과거 대비 70% 수준으로 수축되었거나, 절대값이 0.1(10%) 미만인 경우 점수 부여
        if recent_bw < past_bw * 0.7 or recent_bw < 0.1:
            return 1

        return 0

    def _score_chart(self, stock: StockData, charts: Optional[ChartData]) -> tuple[int, bool, bool, bool]:
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

    def determine_grade(self, stock: StockData, score: ScoreDetail, score_details: Dict = None, supply: SupplyData = None, charts: ChartData = None) -> Grade:
        """등급 결정 (2026-02-01 Simplified V3)
        
        [공통 필터]
        - 거래대금 300억 미만 제외
        - 거래량 배수 2.0배 미만 제외 (필수)
        
        [단순화된 등급 기준]
        S급: 1조원+, 10%+, 점수 10+, 거래량배수 5.0+
        A급: 5,000억+, 5%+, 점수 8+, 거래량배수 3.0+
        B급: 1,000억+, 4%+, 점수 6+, 거래량배수 2.0+
        C급: 500억+, 5%+, 점수 8+, 거래량배수 3.0+
        D급: 500억+, 4%+, 점수 6+, 거래량배수 2.0+
        """
        trading_value = stock.trading_value
        change_pct = stock.change_pct
        
        # 거래량 배수 (score_details에서)
        volume_ratio = 0.0
        if score_details and 'volume_ratio' in score_details:
            volume_ratio = score_details.get('volume_ratio', 0.0)
        
        # 1. 공통 필터 (Common Exclusion)
        # 1. 공통 필터 (Common Exclusion)
        if trading_value < 50_000_000_000:
            return None
            
        if volume_ratio < 2.0:
            return None

        # 2. 등급 판별 (Strict logic first)
        
        # [S급] 초대형 수급 폭발
        # 조건: 거래대금 1조원 이상 AND 등락률 10% 이상 AND 점수 10점 이상
        if (trading_value >= 1_000_000_000_000 and 
            change_pct >= 10.0 and 
            score.total >= 10):
            return Grade.S
            
        # [A급] 대형 우량주
        # 조건: 거래대금 5,000억 이상 AND 등락률 3% 이상 AND 점수 8점 이상
        if (trading_value >= 500_000_000_000 and 
            change_pct >= 3.0 and
            score.total >= 8):
            return Grade.A
            
        # [B급] 중형 주도주
        # 조건: 거래대금 1,000억 이상 AND 등락률 4% 이상 AND 점수 6점 이상
        if (trading_value >= 100_000_000_000 and 
            change_pct >= 4.0 and
            score.total >= 6):
            return Grade.B
            
        # [C급] 강소 주도주 (소형)
        # 조건: 거래대금 500억 이상 AND 등락률 5% 이상 AND 점수 8점 이상
        if (trading_value >= 50_000_000_000 and 
            change_pct >= 5.0 and
            score.total >= 8):
            return Grade.C
            
        # [D급] 조건부 관망 (소형)
        # 조건: 거래대금 500억 이상 AND 등락률 4% 이상 AND 점수 6점 이상 AND 거래량 배수 2배 이상 (위 점수 조건 미달 시)
        if (trading_value >= 50_000_000_000 and 
            change_pct >= 4.0 and
            score.total >= 6 and
            volume_ratio >= 2.0):
            return Grade.D
        
        # 조건 미충족 시 등급 없음
        return None

