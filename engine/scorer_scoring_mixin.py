#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Scorer 점수 계산 믹스인.
"""

from __future__ import annotations

import math
from typing import Dict, List, Optional

from engine.constants import TRADING_VALUES
from engine.models import ChartData, NewsItem, ScoreDetail, StockData, SupplyData
from engine.scorer_news_helpers import (
    build_stock_aliases,
    normalize_news_text,
)


class ScorerScoringMixin:
    """Scorer의 세부 점수 계산 메서드를 제공한다."""

    def _score_news(
        self,
        news: Optional[List[NewsItem]],
        llm_result: Optional[Dict],
        stock: StockData = None,
    ) -> tuple[int, bool, List[str], str]:
        """뉴스 점수 (0-3점) - 거래대금 Fallback 추가."""
        llm_score = llm_result.get("score", 0) if llm_result else 0
        llm_reason = llm_result.get("reason", "") if llm_result else ""

        has_news = news is not None and len(news) > 0
        sources = [item.source for item in news] if news else []
        has_relevant_news = self._has_relevant_news(news, stock)
        fallback_score = self._fallback_news_score_by_trading_value(
            stock.trading_value if stock else 0
        )

        news_score = llm_score
        if has_news and news_score == 0:
            news_score = 1

        if has_news and stock and not has_relevant_news:
            news_score = max(news_score, fallback_score)

        if news_score == 0 and stock:
            news_score = fallback_score

        return min(3, news_score), has_news, sources, llm_reason

    @staticmethod
    def _normalize_news_text(text: str) -> str:
        """종목명/제목 매칭용 텍스트 정규화."""
        return normalize_news_text(text)

    def _build_stock_aliases(self, stock_name: str) -> List[str]:
        """우선주 접미사 등을 제거한 종목명 별칭 집합 생성."""
        return list(build_stock_aliases(stock_name))

    def _has_relevant_news(
        self,
        news: Optional[List[NewsItem]],
        stock: Optional[StockData],
    ) -> bool:
        """뉴스 제목에 종목명(또는 우선주 제거 별칭) 포함 여부 판정."""
        if not news:
            return False

        if not stock or not stock.name:
            return True

        aliases = self._build_stock_aliases(stock.name)
        if not aliases:
            return True

        for item in news:
            title = self._normalize_news_text(item.title if item else "")
            if title and any(alias in title for alias in aliases):
                return True

        return False

    @staticmethod
    def _fallback_news_score_by_trading_value(trading_value: float) -> int:
        """거래대금 기반 뉴스 점수 보정."""
        if trading_value >= TRADING_VALUES.NEWS_FALLBACK_S:
            return 3
        if trading_value >= TRADING_VALUES.NEWS_FALLBACK_A:
            return 2
        if trading_value >= TRADING_VALUES.NEWS_FALLBACK_B:
            return 1
        return 0

    def _score_volume(self, stock: StockData) -> int:
        """거래대금 점수 (0-3점)."""
        if stock.trading_value >= self.config.trading_value_s:
            return 3
        if stock.trading_value >= self.config.trading_value_a:
            return 2
        if stock.trading_value >= self.config.trading_value_b:
            return 1
        return 0

    def _score_candle(self, charts: Optional[ChartData]) -> int:
        """캔들형태 점수 (0-1점)."""
        if not charts:
            return 0

        recent_candles = 5
        if len(charts.lows) < recent_candles or len(charts.closes) < recent_candles:
            return 0

        last_lows = charts.lows[-recent_candles:]
        last_highs = charts.highs[-recent_candles:]
        last_closes = charts.closes[-recent_candles:]
        last_opens = charts.opens[-recent_candles:]

        for i in range(1, recent_candles):
            body_size = last_closes[i] - last_opens[i]
            if body_size > 0 and abs(body_size) > abs(last_lows[i] - last_highs[i]) * 2:
                upper_shadow = last_highs[i] - max(last_opens[i], last_closes[i])
                if upper_shadow < body_size * 0.3:
                    return 1

        return 0

    def _score_timing(self, stock: StockData, charts: Optional[ChartData]) -> int:
        """기간조정 점수 (0-1점): 볼린저밴드 수축 및 횡보 후 돌파."""
        if not charts or len(charts.closes) < 20:
            return 0

        closes = charts.closes
        band_widths = []
        is_breakout = False

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
                band_widths.append((upper - lower) / avg)

            if i == 0 and closes[-1] > upper:
                is_breakout = True

        if len(band_widths) < 10:
            return 0

        recent_bw_avg = sum(band_widths[1:6]) / 5
        past_bw_avg = sum(band_widths[6:]) / len(band_widths[6:])
        is_contracted = (recent_bw_avg < past_bw_avg * 0.8) or (recent_bw_avg < 0.15)
        return 1 if is_contracted and is_breakout else 0

    def _score_chart(
        self,
        stock: StockData,
        charts: Optional[ChartData],
    ) -> tuple[int, bool, bool, bool]:
        """차트패턴 점수 (0-2점)."""
        if not charts:
            return 0, False, False, False

        score = 0
        is_new_high = False
        is_breakout = False
        ma_aligned = False

        if stock.high_52w > 0 and stock.close > stock.high_52w:
            is_new_high = True
            score += 1

        if len(charts.closes) >= 20:
            closes = charts.closes
            ma20 = sum(closes[-20:]) / 20
            ma60 = sum(closes[-60:]) / 60
            if ma20 > ma60 and stock.close > ma20:
                ma_aligned = True
                score += 1

        if len(charts.highs) >= 10:
            recent_high = max(charts.highs[-10:-5])
            recent_5_high = max(charts.highs[-5:])
            if recent_5_high > recent_high:
                is_breakout = True

        return min(2, score), is_new_high, is_breakout, ma_aligned

    def _score_supply(self, trading_value: float, supply: Optional[SupplyData]) -> tuple[int, bool]:
        """수급 점수 (0-2점)."""
        if not supply or trading_value <= 0:
            return 0, False

        total_buy_5d = max(0, supply.foreign_buy_5d) + max(0, supply.inst_buy_5d)
        supply_ratio = (total_buy_5d / trading_value) * 100

        if supply_ratio >= 10:
            return 2, True
        if supply_ratio >= 5:
            return 1, True
        return 0, False

    def _calculate_volume_ratio(self, stock: StockData, charts: Optional[ChartData]) -> float:
        """거래량 배수 계산."""
        volume_ratio = 0.0
        if charts and len(charts.volumes) >= 2:
            today_vol = stock.volume if stock.volume > 0 else charts.volumes[-1]
            lookback = min(20, len(charts.volumes) - 1)
            if lookback > 0:
                avg_vol = sum(charts.volumes[-lookback - 1 : -1]) / lookback
                if avg_vol > 0:
                    volume_ratio = round(today_vol / avg_vol, 2)
        return volume_ratio

    def _calculate_bonus(
        self,
        volume_ratio: float,
        chart_score: int,
        is_limit_up: bool = False,
    ) -> tuple[int, Dict[str, int]]:
        """가산점 계산 (최대 7점)."""
        bonus = 0

        volume_bonus = 0
        if volume_ratio >= 6:
            volume_bonus = 5
        elif volume_ratio >= 5:
            volume_bonus = 4
        elif volume_ratio >= 4:
            volume_bonus = 3
        elif volume_ratio >= 3:
            volume_bonus = 2
        elif volume_ratio >= 2:
            volume_bonus = 1
        bonus += volume_bonus

        candle_bonus = 1 if chart_score >= 1 else 0
        bonus += candle_bonus

        limit_up_bonus = 1 if is_limit_up else 0
        bonus += limit_up_bonus

        bonus_breakdown = {
            "volume": volume_bonus,
            "candle": candle_bonus,
            "limit_up": limit_up_bonus,
        }
        return min(7, bonus), bonus_breakdown

    def _build_score_details(
        self,
        stock: StockData,
        supply: SupplyData,
        score: ScoreDetail,
        base_score: int,
        bonus_score: int,
        volume_ratio: float,
        bonus_breakdown: Dict[str, int] = None,
        is_new_high: bool = False,
        is_limit_up: bool = False,
    ) -> Dict:
        """점수 상세 딕셔너리 빌드."""
        foreign_net_buy = 0
        inst_net_buy = 0
        if supply:
            foreign_net_buy = supply.foreign_buy_5d
            inst_net_buy = supply.inst_buy_5d

        return {
            "news": score.news,
            "volume": score.volume,
            "chart": score.chart,
            "candle": score.candle,
            "consolidation": score.timing,
            "supply": score.supply,
            "rise_pct": stock.change_pct,
            "volume_ratio": volume_ratio,
            "foreign_net_buy": foreign_net_buy,
            "inst_net_buy": inst_net_buy,
            "base_score": base_score,
            "bonus_score": bonus_score,
            "bonus_breakdown": bonus_breakdown or {},
            "is_new_high": is_new_high,
            "is_limit_up": is_limit_up,
        }
