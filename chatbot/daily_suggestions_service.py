#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
일일 추천 질문 생성 서비스
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional


logger = logging.getLogger(__name__)


def generate_daily_suggestions(
    bot: Any,
    watchlist: Optional[list] = None,
    persona: Optional[str] = None,
) -> List[Dict[str, str]]:
    """
    현재 시장 상황과 데이터, 페르소나를 기반으로 AI 추천 질문 5가지를 생성
    (1시간 캐싱 적용 - 페르소나별 분리)
    """
    now = datetime.now()
    cache_key = bot._build_daily_suggestions_cache_key(watchlist, persona)
    cached = bot._get_cached_daily_suggestions(cache_key, now)
    if cached:
        return cached

    try:
        market_gate = bot._fetch_market_gate()
        vcp_text = bot._fetch_vcp_ai_analysis()
        news_text = bot._fetch_latest_news()
        market_summary = (
            f"Status: {market_gate.get('status', 'N/A')}, Score: {market_gate.get('total_score', 0)}"
        )
        watchlist_text = bot._build_watchlist_suggestions_text(watchlist)
        prompt = bot._build_daily_suggestions_prompt(
            persona=persona,
            market_summary=market_summary,
            vcp_text=vcp_text,
            news_text=news_text,
            watchlist_text=watchlist_text,
        )

        if not bot.client:
            return []

        response = bot.client.models.generate_content(
            model=bot.current_model_name,
            contents=prompt,
            config={"response_mime_type": "application/json"},
        )

        suggestions = json.loads(response.text)
        bot.memory.add(cache_key, suggestions)
        return suggestions

    except Exception as e:
        error_text = str(e)
        if "429" in error_text or "RESOURCE_EXHAUSTED" in error_text:
            logger.warning(
                "Gemini API 할당량 초과 (429 RESOURCE_EXHAUSTED). 기본 추천 질문으로 대체합니다."
            )
        else:
            logger.error("Failed to generate suggestions: %s", e)
        return bot._default_daily_suggestions()
