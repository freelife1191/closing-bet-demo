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
        
        # 기본 점수 (Base Score)
        base_score = score.news + score.volume + score.chart + score.candle + score.timing + score.supply
        
        # 상세 내역 (프론트엔드 필터용)
        # 거래량 배수 = 오늘 거래량 / 최근 20일 평균 거래량 (네이버/토스 기준)
        volume_ratio = 0.0
        if charts and len(charts.volumes) >= 2:
            today_vol = charts.volumes[-1]
            lookback = min(20, len(charts.volumes) - 1)
            if lookback > 0:
                avg_vol = sum(charts.volumes[-lookback-1:-1]) / lookback
                if avg_vol > 0:
                    volume_ratio = round(today_vol / avg_vol, 2)
        
        # [New] 가산점 (Bonus Score) - V2 Logic
        bonus_score = self._calculate_bonus(stock.change_pct, volume_ratio)
        
        # 총점 계산 (기본 + 보너스)
        score.total = base_score + bonus_score
        
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
            'inst_net_buy': inst_net_buy,
            'base_score': base_score,
            'bonus_score': bonus_score
        }

        return score, checklist, details

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

    def _score_news(self, news: Optional[List[NewsItem]], llm_result: Optional[Dict], stock: StockData = None) -> tuple[int, bool, List[str], str]:
        """뉴스 점수 (0-3점) - 거래대금 Fallback 추가"""
        
        # 1. LLM/News 기반 점수
        llm_score = llm_result.get('score', 0) if llm_result else 0
        llm_reason = llm_result.get('reason', '') if llm_result else ""
        
        has_news = news is not None and len(news) > 0
        sources = [n.source for n in news] if news else []

        news_score = llm_score
        if has_news and news_score == 0:
            news_score = 1
            
        # 2. Fallback: 뉴스가 없어도 거래대금이 크면 점수 부여 (V2 Logic)
        # (대형주는 뉴스 없이도 수급만으로 상승하는 경우가 많음)
        if news_score == 0 and stock:
            if stock.trading_value >= 500_000_000_000: # 5000억
                news_score = 3
            elif stock.trading_value >= 100_000_000_000: # 1000억
                news_score = 2
            elif stock.trading_value >= 50_000_000_000: # 500억
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
        """기간조정 점수 (0-1점): 볼린저밴드 수축 및 횡보 후 돌파"""
        if not charts or len(charts.closes) < 20:
            return 0

        # 볼린저 밴드 계산 및 돌파 확인
        import math
        
        closes = charts.closes
        band_widths = []
        is_breakout = False
        
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
            
            # 오늘(i=0) 기준 상단 돌파 여부 확인
            if i == 0:
                if closes[-1] > upper:
                    is_breakout = True

        if len(band_widths) < 10:
            return 0
            
        # 1. 수축 (Contraction): 최근 5일(오늘 제외) 평균 Band Width가 과거 대비 낮거나 절대값이 작음
        # band_widths 리스트는 [오늘, 1일전, 2일전, ...] 순서임 (range(20) 역순 아님, i가 0부터 커짐)
        # i=0: 오늘, i=1: 1일전...
        
        recent_bw_avg = sum(band_widths[1:6]) / 5  # 어제부터 5일간
        past_bw_avg = sum(band_widths[6:]) / len(band_widths[6:]) # 그 이전
        
        is_contracted = (recent_bw_avg < past_bw_avg * 0.8) or (recent_bw_avg < 0.15)
        
        # 2. 횡보 후 돌파: 수축 상태에서 오늘 상단 밴드 돌파
        if is_contracted and is_breakout:
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

    def determine_grade(
        self, 
        stock: StockData, 
        score: ScoreDetail, 
        score_details: Dict, 
        supply: SupplyData, 
        charts: ChartData,
        allow_no_news: bool = False  # [Fix] Phase 1 선별용 플래그
    ) -> Optional[Grade]:
        """
        최종 등급 판정 (S/A/B/C)
        - 필수 조건(거래대금, 등락률, 윗꼬리 등) 검증
        - 점수 및 거래대금 기준 등급 부여
        """
        trading_value = stock.trading_value
        change_pct = stock.change_pct
        
        # 거래량 배수 (score_details에서)
        volume_ratio = 0.0
        if score_details and 'volume_ratio' in score_details:
            volume_ratio = score_details.get('volume_ratio', 0.0)
        
        # 디버그용 로그 (등급 판정 과정 추적)
        # logger.debug(f"[등급판정] {stock.name}: Value={trading_value//100_000_000}억, Rise={change_pct:.1f}%, Score={score.total}, VolRatio={volume_ratio:.1f}")
        
        # --- 1. 회피 조건 (Don'ts) & 필수 조건 Check ---

        # 1) 거래대금 500억 미만 제외 (Config.min이 500억으로 상향됨)
        if trading_value < self.config.trading_value_min:
            logger.debug(f"  -> [Drop] 거래대금 부족: {trading_value//100_000_000}억 < 500억")
            return None
            
        # 2) 등락률 5~29.9% 이외 제외 (상한가 제외, 너무 낮은 등락률 제외)
        if not (5.0 <= change_pct <= 29.9):
            logger.debug(f"  -> [Drop] 등락률 조건 위배: {change_pct:.1f}% (Target: 5~29.9%)")
            return None

        # 3) 상한가 제외 (30% 이상)
        if change_pct >= 30.0:
             logger.debug(f"  -> [Drop] 상한가 도달 종목")
             return None

        # 4) 뉴스 없음 (단순 급등 작전주 회피)
        if not allow_no_news and score.news == 0:
            logger.debug(f"  -> [Drop] 뉴스/재료 없음")
            return None

        # 5) 윗꼬리가 긴 캔들 (매도세)
        # _score_candle 함수가 1점을 주면 '양호(윗꼬리 짧음)', 0점이면 '나쁨(윗꼬리 긺 or 음봉)')
        # 다만 _score_candle은 장대양봉 조건도 포함하므로, 여기서는 윗꼬리만 별도로 엄격히 볼 수도 있음
        # 일단 Score 기반으로 차단하거나, Chart Data로 직접 확인
        if charts:
             # 직접 확인: 윗꼬리가 몸통의 50%를 넘으면 탈락
             try:
                 open_p = charts.opens[-1]
                 close_p = charts.closes[-1]
                 high_p = charts.highs[-1]
                 
                 body = abs(close_p - open_p)
                 upper_shadow = high_p - max(open_p, close_p)
                 
                 if body > 0 and upper_shadow > body * 0.5:
                     logger.debug(f"  -> [Drop] 윗꼬리 과다: Shadow({upper_shadow}) > Body({body}*0.5)")
                     return None
             except:
                 pass

        # 6) 거래량 배수 확인 (최소 2배)
        if volume_ratio < 2.0:
            logger.debug(f"  -> [Drop] 거래량배수 부족: {volume_ratio:.1f} < 2.0")
            return None

        # --- 2. 등급 판별 (18점 만점 기준) ---
        # Config 기준: S(15), A(12), B(10)
        
        # [S급]
        if (trading_value >= self.config.trading_value_s and # 1조
            score.total >= self.config.min_s_grade): # 15점
            logger.debug(f"  -> [S급] 조건 충족!")
            return Grade.S
            
        # [A급]
        if (trading_value >= self.config.trading_value_a and # 5000억
            score.total >= self.config.min_a_grade): # 12점
            logger.debug(f"  -> [A급] 조건 충족!")
            return Grade.A
            
        # [B급]
        if (trading_value >= self.config.trading_value_b and # 1000억
            score.total >= self.config.min_b_grade): # 10점
            logger.debug(f"  -> [B급] 조건 충족!")
            return Grade.B
            
        # [C급] (강소 주도주)
        # 500억 이상, 10% 이상 상승, 거래량 5배, 외인+기관 양매수, 8점 이상
        if (score.total >= 8 and
            change_pct >= 10.0 and
            volume_ratio >= 5.0 and
            supply.foreign_buy_5d > 0 and
            supply.inst_buy_5d > 0):
            logger.debug(f"  -> [C급] 조건 충족!")
            return Grade.C
        
        # [점수 미달] - 검출 제외
        # 8점 미만은 시그널 생성 대상에서 제외 (D등급 개념 삭제)
        logger.debug(f"  -> [Drop] 점수 미달 (Score={score.total} < 8)")
        return None

