#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
챗봇 데이터 조회/캐시 및 일일 추천 헬퍼 서비스
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from services.kr_market_data_cache_service import load_json_payload_from_path

from .signal_context import (
    load_jongga_signals,
    build_latest_news_text,
    build_jongga_candidates_text,
    build_vcp_analysis_summary_text,
    load_vcp_ai_payload,
)
from .suggestions_prompt import (
    build_daily_suggestions_prompt as build_daily_suggestions_prompt_template,
)


logger = logging.getLogger(__name__)


def fetch_market_gate(data_dir: Path) -> Dict[str, Any]:
    """market_gate.json에서 최신 시장 상태 조회."""
    try:
        json_path = data_dir / "market_gate.json"
        if not json_path.exists():
            return {}

        data = load_json_payload_from_path(str(json_path))

        return data if isinstance(data, dict) else {}
    except Exception as e:
        logger.error("Market Gate fetch error: %s", e)
        return {}


def fetch_vcp_ai_analysis(data_dir: Path) -> str:
    """kr_ai_analysis.json에서 VCP AI 분석 결과 조회 (건수·기준일 머리글 + 매수 추천 상위 5개)."""
    try:
        return build_vcp_analysis_summary_text(load_vcp_ai_payload(data_dir, logger), limit=5)
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
    # 호출자는 기존 호환을 위해 now를 넘길 수 있지만, get()이 SQLite를 재적재한 뒤의
    # 실제 관측 시각으로 판정해야 새 캐시를 future로 오인하지 않는다.
    del now
    cached = memory.get(cache_key)
    if not isinstance(cached, dict):
        return None

    try:
        updated_at = datetime.fromisoformat(str(cached["updated_at"]))
    except (KeyError, TypeError, ValueError):
        logger.debug("Invalid daily suggestion cache timestamp")
        return None
    evaluated_at = datetime.now()
    if updated_at.tzinfo is not None or updated_at > evaluated_at:
        return None
    if (evaluated_at - updated_at).total_seconds() >= 3600:
        return None
    value = cached.get("value")
    return value if isinstance(value, list) else None


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
    fetch_jongga_data_fn: Any = None,
    jongga_text: Optional[str] = None,
) -> str:
    """페르소나별 추천 질문 생성 프롬프트 구성."""
    resolved_jongga_text = ""
    if persona != "vcp":
        fetched_jongga = jongga_text
        if fetched_jongga is None and callable(fetch_jongga_data_fn):
            fetched_jongga = fetch_jongga_data_fn()
        if fetched_jongga:
            resolved_jongga_text = f"\n## 종가베팅 데이터:\n{fetched_jongga[:1000]}..."

    return build_daily_suggestions_prompt_template(
        persona=persona,
        market_summary=market_summary,
        vcp_text=vcp_text,
        news_text=news_text,
        watchlist_text=watchlist_text,
        jongga_text=resolved_jongga_text,
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
