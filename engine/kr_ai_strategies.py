#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KR AI Analyzer 전략 모듈
"""

import logging
from typing import Any, Dict, List, Optional

from engine.models import NewsItem


logger = logging.getLogger(__name__)
_VALID_ACTIONS = {"BUY", "SELL", "HOLD"}


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


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
    """종료된 구형 모의 분석의 호환 진입점."""

    def __init__(self, api_key: str):
        super().__init__(api_key)
        self.is_available = False

    def analyze(self, stock_info: Dict, news_items: List[NewsItem]) -> Optional[Dict]:
        logger.warning("구형 모의 분석은 종료되었습니다. VCP 분석기를 사용하세요.")
        return None


class GPTStrategy(GeminiStrategy):
    """종료된 구형 GPT 모의 분석의 호환 진입점."""


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
