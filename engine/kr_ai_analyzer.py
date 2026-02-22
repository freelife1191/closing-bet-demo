#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KR Market - AI Analyzer (Gemini + GPT)

Refactored to split strategies/data services while preserving public API.
"""

import logging
import os
from datetime import datetime
from types import SimpleNamespace
from typing import Dict, List, Optional

from dotenv import load_dotenv

from engine.kr_ai_data_service import KrAiDataService
from engine.kr_ai_strategies import (
    AIStrategy,
    GPTStrategy,
    GeminiStrategy,
    RecommendationCombiner,
)
from engine.models import NewsItem


load_dotenv()
logger = logging.getLogger(__name__)

try:
    import engine.shared as shared_state
except ImportError:
    shared_state = SimpleNamespace(STOP_REQUESTED=False)


class KrAiAnalyzer:
    """
    AI 기반 종목 분석기

    Notes:
    - 기존 메서드명/반환 스키마를 유지한다.
    - `api_key` 인자를 추가로 허용해 레거시 호출과 호환한다.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        openai_api_key: Optional[str] = None,
        data_service: Optional[KrAiDataService] = None,
    ):
        google_api_key = api_key if api_key is not None else os.getenv("GOOGLE_API_KEY", "")
        openai_key = (
            openai_api_key
            if openai_api_key is not None
            else os.getenv("OPENAI_API_KEY", "")
        )

        self.gemini_strategy = GeminiStrategy(google_api_key)
        self.gpt_strategy = GPTStrategy(openai_key)
        self.data_service = data_service or KrAiDataService()

        if not self.gemini_strategy.is_available and not self.gpt_strategy.is_available:
            logger.warning("AI API 키가 설정되지 않았습니다.")

    def analyze_stock(
        self,
        ticker: str,
        news_items: Optional[List[Dict]] = None,
    ) -> Dict:
        """
        종목 AI 분석

        Args:
            ticker: 종목 코드
            news_items: (Optional) 사전 수집된 뉴스 리스트

        Returns:
            분석 결과 딕셔너리
        """
        try:
            stock_info = self._get_stock_info(ticker)
            if not stock_info:
                return {"error": "종목 정보를 찾을 수 없습니다"}

            if news_items is None:
                news_list = self._collect_news(ticker, stock_info["name"])
            else:
                news_list = self._convert_to_news_items(news_items)

            gemini_result = self.gemini_strategy.analyze(stock_info, news_list)
            gpt_result = self.gpt_strategy.analyze(stock_info, news_list)

            result = {
                "ticker": ticker,
                "name": stock_info["name"],
                "price": stock_info["price"],
                "change_pct": stock_info["change_pct"],
                "news": [self._news_item_to_dict(n) for n in news_list],
                "gemini_recommendation": gemini_result,
                "gpt_recommendation": gpt_result,
                "final_recommendation": RecommendationCombiner.combine(
                    gemini_result,
                    gpt_result,
                ),
                "analyzed_at": datetime.now().isoformat(),
            }

            return result

        except Exception as e:
            logger.error(f"종목 분석 실패 ({ticker}): {e}")
            return {"error": str(e)}

    def _get_stock_info(self, ticker: str) -> Optional[Dict]:
        """종목 기본 정보 조회 (호환 래퍼)."""
        return self.data_service.get_stock_info(ticker)

    def _get_stock_name(self, ticker: str) -> str:
        """종목명 조회 (호환 래퍼)."""
        return self.data_service.get_stock_name(ticker)

    def _collect_news(self, ticker: str, name: str) -> List[NewsItem]:
        """뉴스 수집 (호환 래퍼)."""
        return self.data_service.collect_news(ticker, name)

    def _convert_to_news_items(self, news_dicts: List[Dict]) -> List[NewsItem]:
        """딕셔너리 뉴스를 NewsItem으로 변환 (호환 래퍼)."""
        return self.data_service.convert_to_news_items(news_dicts)

    def _news_item_to_dict(self, news_item: NewsItem) -> Dict:
        """NewsItem을 딕셔너리로 변환 (호환 래퍼)."""
        return self.data_service.news_item_to_dict(news_item)

    def analyze_multiple_stocks(
        self,
        tickers: List[str],
        news_map: Optional[Dict] = None,
    ) -> Dict:
        """
        여러 종목 분석 (배치)

        Args:
            tickers: 종목 코드 리스트
            news_map: (Optional) 종목별 뉴스 맵 {ticker: news_items}

        Returns:
            분석 결과 딕셔너리
        """
        try:
            results = {
                "signals": [],
                "generated_at": datetime.now().isoformat(),
                "total": len(tickers),
            }

            for ticker in tickers:
                if getattr(shared_state, "STOP_REQUESTED", False):
                    logger.warning("[STOP] 사용자 중단 요청으로 AI 분석 중단")
                    raise Exception("사용자 요청 중단")

                news = news_map.get(ticker) if news_map else None
                result = self.analyze_stock(ticker, news_items=news)

                if result and "error" not in result:
                    results["signals"].append(result)
                else:
                    logger.warning(f"분석 결과 제외됨 ({ticker}): {result}")

            return results

        except Exception as e:
            logger.error(f"배치 분석 실패: {e}")
            return {"error": str(e), "signals": []}


def create_analyzer() -> KrAiAnalyzer:
    """분석기 인스턴스 생성 (Convenience Factory)."""
    return KrAiAnalyzer()


__all__ = [
    "AIStrategy",
    "GeminiStrategy",
    "GPTStrategy",
    "RecommendationCombiner",
    "KrAiAnalyzer",
    "create_analyzer",
]
