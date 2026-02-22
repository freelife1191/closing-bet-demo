#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
일일 추천 질문 생성용 프롬프트 템플릿
"""

from __future__ import annotations

from typing import Optional


def build_daily_suggestions_prompt(
    persona: Optional[str],
    market_summary: str,
    vcp_text: str,
    news_text: str,
    watchlist_text: str,
    jongga_text: str = "",
) -> str:
    """시장 컨텍스트를 합성해 JSON 출력 유도 프롬프트를 만든다."""
    persona_label = persona or "default"
    return "\n".join(
        [
            "당신은 한국 주식 분석 비서입니다.",
            "아래 데이터를 참고해 사용자에게 유용한 후속 질문 5개를 JSON 배열로 생성하세요.",
            '반드시 `[{"title":"", "prompt":"", "desc":"", "icon":""}, ...]` 형식을 지키세요.',
            "",
            f"[페르소나] {persona_label}",
            f"[시장 요약] {market_summary}",
            f"[VCP 데이터] {vcp_text}",
            f"[뉴스 데이터] {news_text}",
            f"[관심종목 데이터] {watchlist_text}",
            f"{jongga_text}",
            "",
            "규칙:",
            "- 각 질문은 구체적이고 실행 가능해야 합니다.",
            "- title/prompt/desc/icon 필드를 모두 포함하세요.",
            "- 한국어로 작성하세요.",
        ]
    )


__all__ = ["build_daily_suggestions_prompt"]

