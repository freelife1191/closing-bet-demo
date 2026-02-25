#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KR AI Analyzer 전략 모듈
"""

import logging
from typing import Any, Dict, List, Optional

from engine.constants import AI_ANALYSIS
from engine.kr_ai_templates import MockAnalysisTemplates
from engine.models import NewsItem


logger = logging.getLogger(__name__)
_VALID_ACTIONS = {"BUY", "SELL", "HOLD"}


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return int(default)


def _normalize_action(value: Any, default: str = "HOLD") -> str:
    action = str(value or default).strip().upper()
    return action if action in _VALID_ACTIONS else default


def _normalize_recommendation_payload(payload: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not isinstance(payload, dict):
        return None

    normalized = dict(payload)
    normalized["action"] = _normalize_action(normalized.get("action"), default="HOLD")
    normalized["confidence"] = _safe_float(normalized.get("confidence"), 0.0)
    normalized["reason"] = str(normalized.get("reason") or "근거 부족")
    return normalized


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
        Gemini 전략 분석.
        현재는 안정성을 위해 Mock 기반 분석 결과를 반환한다.
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
                "confidence": _safe_int(random.randint(
                    AI_ANALYSIS.CONFIDENCE_BUY_MIN,
                    AI_ANALYSIS.CONFIDENCE_MAX,
                )),
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
        GPT 전략 분석.
        현재는 안정성을 위해 Mock 기반 분석 결과를 반환한다.
        """
        _ = news_items
        if not self.is_available:
            return None

        try:
            import random
            price = _safe_float(stock_info.get("price"), 0.0)

            return {
                "action": "BUY",
                "confidence": _safe_int(random.randint(
                    AI_ANALYSIS.CONFIDENCE_MIN,
                    AI_ANALYSIS.CONFIDENCE_MAX,
                )),
                "reason": "VCP 패턴 및 외인 매집 추이 확인",
                "target_price": price * AI_ANALYSIS.TARGET_PRICE_RATIO,
                "stop_loss": price * AI_ANALYSIS.STOP_LOSS_RATIO,
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
        normalized_gemini = _normalize_recommendation_payload(gemini_result)
        normalized_gpt = _normalize_recommendation_payload(gpt_result)

        if not normalized_gemini and not normalized_gpt:
            return {
                "action": "HOLD",
                "confidence": 0,
                "reason": "AI 분석 불가",
            }

        if normalized_gemini and not normalized_gpt:
            return normalized_gemini

        if normalized_gpt and not normalized_gemini:
            return normalized_gpt

        assert normalized_gemini is not None
        assert normalized_gpt is not None

        if normalized_gemini["action"] == normalized_gpt["action"]:
            return {
                "action": normalized_gemini["action"],
                "confidence": (
                    _safe_float(normalized_gemini.get("confidence"), 0.0)
                    + _safe_float(normalized_gpt.get("confidence"), 0.0)
                ) / 2,
                "reason": f"{normalized_gemini['reason']} / {normalized_gpt['reason']}",
            }

        if _safe_float(normalized_gemini.get("confidence"), 0.0) > _safe_float(normalized_gpt.get("confidence"), 0.0):
            return {
                "action": normalized_gemini["action"],
                "confidence": _safe_float(normalized_gemini.get("confidence"), 0.0),
                "reason": str(normalized_gemini["reason"]) + " (우선권)",
            }

        return {
            "action": normalized_gpt["action"],
            "confidence": _safe_float(normalized_gpt.get("confidence"), 0.0),
            "reason": str(normalized_gpt["reason"]) + " (우선권)",
        }


__all__ = [
    "AIStrategy",
    "GeminiStrategy",
    "GPTStrategy",
    "RecommendationCombiner",
]
