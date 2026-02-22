#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KR AI Analyzer 전략 모듈
"""

import logging
from typing import Dict, List, Optional

from engine.constants import AI_ANALYSIS
from engine.kr_ai_templates import MockAnalysisTemplates
from engine.models import NewsItem


logger = logging.getLogger(__name__)


class AIStrategy:
    """AI 분석 전략 기본 클래스"""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.is_available = bool(api_key)

    def analyze(self, stock_info: Dict, news_items: List[NewsItem]) -> Optional[Dict]:
        """분석 수행 (서브클래스에서 구현)"""
        raise NotImplementedError


class GeminiStrategy(AIStrategy):
    """Gemini 기반 분석 전략"""

    def analyze(self, stock_info: Dict, news_items: List[NewsItem]) -> Optional[Dict]:
        """
        Gemini로 종목 분석

        TODO: 실제 API 키가 있으면 google.generativeai 호출
        현재는 Mock 데이터 반환 (풍부한 샘플)
        """
        _ = news_items
        if not self.is_available:
            return None

        try:
            import random

            templates = MockAnalysisTemplates()
            driver = random.choice(templates.INVESTMENT_DRIVERS)
            risk = random.choice(templates.RISK_FACTORS)
            hypothesis_template = random.choice(templates.HYPOTHESIS_TEMPLATES)

            hypothesis = hypothesis_template.format(
                name=stock_info.get("name", "동사"),
                driver=driver,
                risk=risk,
            )

            rich_reason = f"""
[핵심 투자 포인트]
• {driver}
• {random.choice(templates.INVESTMENT_DRIVERS)}

[리스크 요인]
• {risk}

[종합 의견]
{hypothesis}
"""

            return {
                "action": "BUY",
                "confidence": random.randint(
                    AI_ANALYSIS.CONFIDENCE_BUY_MIN,
                    AI_ANALYSIS.CONFIDENCE_MAX,
                ),
                "reason": rich_reason.strip(),
                "news_sentiment": random.choice(["positive", "positive", "neutral"]),
            }

        except Exception as e:
            logger.error(f"Gemini 분석 실패: {e}")
            return None


class GPTStrategy(AIStrategy):
    """GPT 기반 분석 전략"""

    def analyze(self, stock_info: Dict, news_items: List[NewsItem]) -> Optional[Dict]:
        """
        GPT로 종목 분석

        TODO: 실제 OpenAI API 호출 구현
        현재는 Mock 데이터 반환
        """
        _ = news_items
        if not self.is_available:
            return None

        try:
            import random

            return {
                "action": "BUY",
                "confidence": random.randint(
                    AI_ANALYSIS.CONFIDENCE_MIN,
                    AI_ANALYSIS.CONFIDENCE_MAX,
                ),
                "reason": "VCP 패턴 및 외인 매집 추이 확인",
                "target_price": stock_info["price"] * AI_ANALYSIS.TARGET_PRICE_RATIO,
                "stop_loss": stock_info["price"] * AI_ANALYSIS.STOP_LOSS_RATIO,
            }

        except Exception as e:
            logger.error(f"GPT 분석 실패: {e}")
            return None


class RecommendationCombiner:
    """여러 AI의 추천을 통합하는 클래스"""

    @staticmethod
    def combine(gemini_result: Optional[Dict], gpt_result: Optional[Dict]) -> Dict:
        """
        두 AI의 추천 통합

        Strategy:
        1. 둘 다 없음 -> HOLD with 0 confidence
        2. 하나만 있음 -> 해당 결과 반환
        3. 둘 다 있음:
           - 액션이 일치하면 -> 평균 confidence
           - 액션이 다르면 -> 높은 confidence 선택
        """
        if not gemini_result and not gpt_result:
            return {
                "action": "HOLD",
                "confidence": 0,
                "reason": "AI 분석 불가",
            }

        if gemini_result and not gpt_result:
            return gemini_result

        if gpt_result and not gemini_result:
            return gpt_result

        if gemini_result["action"] == gpt_result["action"]:
            return {
                "action": gemini_result["action"],
                "confidence": (gemini_result["confidence"] + gpt_result["confidence"]) / 2,
                "reason": f"{gemini_result['reason']} / {gpt_result['reason']}",
            }

        if gemini_result["confidence"] > gpt_result["confidence"]:
            return {
                "action": gemini_result["action"],
                "confidence": gemini_result["confidence"],
                "reason": gemini_result["reason"] + " (우선권)",
            }

        return {
            "action": gpt_result["action"],
            "confidence": gpt_result["confidence"],
            "reason": gpt_result["reason"] + " (우선권)",
        }


__all__ = [
    "AIStrategy",
    "GeminiStrategy",
    "GPTStrategy",
    "RecommendationCombiner",
]
