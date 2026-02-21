#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
시그널/뉴스 컨텍스트 로딩 및 텍스트 포맷 유틸
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List


def _read_json(path: Path, logger: logging.Logger) -> Dict[str, Any]:
    """JSON 파일을 읽어 dict를 반환한다. 실패 시 빈 dict."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception as e:
        logger.error("Failed to read json %s: %s", path, e)
        return {}


def load_jongga_signals(data_dir: Path, logger: logging.Logger) -> List[Dict[str, Any]]:
    """jongga_v2_latest.json의 signals 리스트를 반환한다."""
    path = data_dir / "jongga_v2_latest.json"
    if not path.exists():
        return []
    data = _read_json(path, logger)
    signals = data.get("signals", [])
    return signals if isinstance(signals, list) else []


def build_latest_news_text(signals: List[Dict[str, Any]], limit: int = 5) -> str:
    """signals 내 news_items를 합쳐 최근 뉴스 텍스트를 만든다."""
    all_news: List[str] = []
    for signal in signals:
        news_items = signal.get("news_items", [])
        if not isinstance(news_items, list):
            continue
        for news in news_items:
            title = news.get("title", "") if isinstance(news, dict) else ""
            source = news.get("source", "") if isinstance(news, dict) else ""
            if title:
                all_news.append(f"- [{source}] {title}")

    if not all_news:
        return ""
    return "\n".join(all_news[:limit])


def build_jongga_candidates_text(signals: List[Dict[str, Any]], limit: int = 3) -> str:
    """signals에서 S/A급 종가베팅 후보 텍스트를 만든다."""
    candidates = []
    for signal in signals:
        grade = signal.get("grade", "D")
        if grade in ["S", "A"]:
            candidates.append(signal)

    candidates.sort(key=lambda item: item.get("score", {}).get("total", 0), reverse=True)
    if not candidates:
        return ""

    result_text = ""
    for signal in candidates[:limit]:
        name = signal.get("stock_name", "N/A")
        code = signal.get("stock_code", "")
        grade = signal.get("grade", "")
        score_val = signal.get("score", {}).get("total", 0)
        date = signal.get("signal_date", "")

        reason = "정보 없음"
        score_details = signal.get("score_details", {})
        if isinstance(score_details, dict):
            ai_eval = score_details.get("ai_evaluation", {})
            if isinstance(ai_eval, dict):
                reason = ai_eval.get("reason", "정보 없음")

        result_text += (
            f"- **{name}** ({code}): {grade}급, 점수 {score_val}점 ({date})\n"
            f"  - AI 분석: {reason[:100]}...\n"
        )

    return result_text


def load_vcp_ai_signals(data_dir: Path, logger: logging.Logger) -> List[Dict[str, Any]]:
    """VCP AI 분석 파일(kr_ai_analysis/ai_analysis_results)의 signals 리스트 반환."""
    primary = data_dir / "kr_ai_analysis.json"
    fallback = data_dir / "ai_analysis_results.json"

    if primary.exists():
        data = _read_json(primary, logger)
    elif fallback.exists():
        data = _read_json(fallback, logger)
    else:
        return []

    signals = data.get("signals", [])
    return signals if isinstance(signals, list) else []


def build_vcp_buy_recommendations_text(signals: List[Dict[str, Any]], limit: int = 5) -> str:
    """signals에서 BUY 추천 종목 텍스트를 만든다."""
    result_text = ""
    count = 0

    for signal in signals:
        gemini_rec = signal.get("gemini_recommendation", {})
        perplexity_rec = signal.get("perplexity_recommendation", {})

        action = gemini_rec.get("action") if isinstance(gemini_rec, dict) else None
        if not action and isinstance(perplexity_rec, dict):
            action = perplexity_rec.get("action")

        if action != "BUY":
            continue

        name = signal.get("name", signal.get("stock_name", "N/A"))
        score = signal.get("score", signal.get("vcp_score", 0))

        reason = gemini_rec.get("reason", "") if isinstance(gemini_rec, dict) else ""
        if not reason and isinstance(perplexity_rec, dict):
            reason = perplexity_rec.get("reason", "")

        result_text += f"- **{name}**: {score}점 (매수 추천)\n  - AI 분석: {reason[:120]}...\n"
        count += 1
        if count >= limit:
            break

    return result_text

