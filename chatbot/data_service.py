#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
챗봇 데이터 조회/캐시 및 일일 추천 헬퍼 서비스
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from .signal_context import (
    load_jongga_signals,
    build_latest_news_text,
    build_jongga_candidates_text,
    load_vcp_ai_signals,
    build_vcp_buy_recommendations_text,
)
from .suggestions_prompt import (
    build_daily_suggestions_prompt as build_daily_suggestions_prompt_template,
)


logger = logging.getLogger(__name__)


def get_cached_data(bot: Any) -> Dict[str, Any]:
    """시장 데이터 캐시를 조회하고 필요 시 갱신한다."""
    now = datetime.now()
    if (
        bot._data_cache is None
        or bot._cache_timestamp is None
        or (now - bot._cache_timestamp).seconds > bot._cache_ttl
    ):
        try:
            if bot.data_fetcher:
                bot._data_cache = bot.data_fetcher()
            else:
                bot._data_cache = fetch_mock_data()
            bot._cache_timestamp = now
        except Exception as e:
            logger.error("Data fetch error: %s", e)
            if bot._data_cache is None:
                bot._data_cache = {"market": {}, "vcp_stocks": [], "sector_scores": {}}

    return bot._data_cache


def fetch_mock_data() -> Dict[str, Any]:
    """폴백용 Mock 데이터."""
    return {
        "market": {
            "kospi": "2600.00",
            "kosdaq": "850.00",
            "usd_krw": 1350,
            "market_gate": "YELLOW",
        },
        "vcp_stocks": [],
        "sector_scores": {},
    }


def fetch_market_gate(data_dir: Path) -> Dict[str, Any]:
    """market_gate.json에서 최신 시장 상태 조회."""
    try:
        json_path = data_dir / "market_gate.json"
        if not json_path.exists():
            return {}

        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        return data if isinstance(data, dict) else {}
    except Exception as e:
        logger.error("Market Gate fetch error: %s", e)
        return {}


def fetch_vcp_ai_analysis(data_dir: Path) -> str:
    """kr_ai_analysis.json에서 VCP AI 분석 결과 조회 (상위 5개)."""
    try:
        signals = load_vcp_ai_signals(data_dir, logger)
        return build_vcp_buy_recommendations_text(signals, limit=5)
    except Exception as e:
        logger.error("VCP AI analysis fetch error: %s", e)
        return ""


def fetch_latest_news(data_dir: Path) -> str:
    """jongga_v2_latest.json 내 뉴스 데이터 조회 (최근 5개)."""
    try:
        signals = load_jongga_signals(data_dir, logger)
        return build_latest_news_text(signals, limit=5)
    except Exception as e:
        logger.error("News fetch error: %s", e)
        return ""


def fetch_jongga_data(data_dir: Path) -> str:
    """jongga_v2_latest.json에서 최신 S/A급 종목 조회."""
    try:
        signals = load_jongga_signals(data_dir, logger)
        return build_jongga_candidates_text(signals, limit=3)
    except Exception as e:
        logger.error("Jongga data fetch error: %s", e)
        return ""


def build_daily_suggestions_cache_key(
    watchlist: Optional[list],
    persona: Optional[str],
) -> str:
    """일일 추천 캐시 키 생성."""
    watchlist_suffix = "_".join(sorted(watchlist)) if watchlist else "empty"
    persona_key = persona if persona else "default"
    return f"daily_suggestions_{persona_key}_{watchlist_suffix}"


def get_cached_daily_suggestions(
    memory: Any,
    cache_key: str,
    now: datetime,
) -> Optional[List[Dict[str, str]]]:
    """유효한(1시간 이내) 일일 추천 캐시 조회."""
    cached = memory.get(cache_key)
    if not cached:
        return None

    updated_at = datetime.fromisoformat(cached["updated_at"])
    if (now - updated_at).total_seconds() >= 3600:
        return None
    return cached["value"]


def build_watchlist_suggestions_text(
    watchlist: Optional[list],
    stock_map: Dict[str, str],
    format_stock_context_fn: Any,
) -> str:
    """일일 추천 생성용 관심종목 상세 텍스트 구성."""
    if not watchlist:
        return ""

    watchlist_details = []
    for item in watchlist[:5]:
        ticker = stock_map.get(item)
        if not ticker:
            ticker = item if item.isdigit() else None
        if not ticker:
            continue

        context = format_stock_context_fn(item, ticker)
        watchlist_details.append(context)

    if watchlist_details:
        return "\n## 사용자 관심종목 상세 데이터:\n" + "\n".join(watchlist_details)
    return f"\n사용자 관심종목: {', '.join(watchlist)} (데이터 없음)"


def build_daily_suggestions_prompt(
    persona: Optional[str],
    market_summary: str,
    vcp_text: str,
    news_text: str,
    watchlist_text: str,
    fetch_jongga_data_fn: Any,
) -> str:
    """페르소나별 추천 질문 생성 프롬프트 구성."""
    jongga_text = ""
    if persona != "vcp":
        fetched_jongga = fetch_jongga_data_fn()
        if fetched_jongga:
            jongga_text = f"\n## 종가베팅 데이터:\n{fetched_jongga[:1000]}..."

    return build_daily_suggestions_prompt_template(
        persona=persona,
        market_summary=market_summary,
        vcp_text=vcp_text,
        news_text=news_text,
        watchlist_text=watchlist_text,
        jongga_text=jongga_text,
    )


def default_daily_suggestions() -> List[Dict[str, str]]:
    """일일 추천 생성 실패 시 기본 질문 세트."""
    return [
        {
            "title": "시장 현황",
            "prompt": "오늘 마켓게이트 상태와 투자 전략 알려줘",
            "desc": "마켓게이트 상태와 투자 전략",
            "icon": "fas fa-chart-pie",
        },
        {
            "title": "VCP 추천",
            "prompt": "VCP AI 분석 결과 매수 추천 종목 알려줘",
            "desc": "AI 분석 기반 매수 추천 종목",
            "icon": "fas fa-search-dollar",
        },
        {
            "title": "종가 베팅",
            "prompt": "오늘의 종가베팅 S급, A급 추천해줘",
            "desc": "오늘의 S/A급 종가베팅 추천",
            "icon": "fas fa-chess-knight",
        },
        {
            "title": "뉴스 분석",
            "prompt": "최근 주요 뉴스와 시장 영향 분석해줘",
            "desc": "최근 주요 뉴스와 시장 영향",
            "icon": "fas fa-newspaper",
        },
        {
            "title": "내 관심종목",
            "prompt": "내 관심종목 리스트 기반으로 현재 상태 진단해줘",
            "desc": "관심종목 진단 및 리스크 점검",
            "icon": "fas fa-heart",
        },
    ]
