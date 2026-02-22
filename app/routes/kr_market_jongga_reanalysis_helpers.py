#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KR Market 종가베팅 Gemini 재분석 헬퍼
"""

import re
from typing import Dict, List

from app.routes.kr_market_jongga_grade_helpers import _is_jongga_ai_analysis_completed


def _select_signals_for_gemini_reanalysis(
    all_signals: List[dict],
    target_tickers: List[str],
    force_update: bool,
) -> List[dict]:
    """Gemini 재분석 대상 시그널을 선택한다."""
    if not isinstance(all_signals, list):
        return []

    if target_tickers:
        target_set = {str(t).strip() for t in target_tickers}
        selected = []
        for signal in all_signals:
            if not isinstance(signal, dict):
                continue
            code = str(signal.get("stock_code", "")).strip()
            name = str(signal.get("stock_name", "")).strip()
            if code in target_set or name in target_set:
                selected.append(signal)
        return selected

    if force_update:
        return [sig for sig in all_signals if isinstance(sig, dict)]

    selected = []
    for signal in all_signals:
        if isinstance(signal, dict) and not _is_jongga_ai_analysis_completed(signal):
            selected.append(signal)
    return selected


def _build_jongga_news_analysis_items(signals: List[dict]) -> List[dict]:
    """LLM 뉴스 배치 분석용 입력 아이템을 생성한다."""
    if not isinstance(signals, list):
        return []

    items: List[dict] = []
    for signal in signals:
        if not isinstance(signal, dict):
            continue
        stock_name = signal.get("stock_name")
        news_items = signal.get("news_items", [])
        if stock_name and news_items:
            items.append({"stock": signal, "news": news_items, "supply": None})
    return items


def _build_normalized_gemini_result_map(results_map: Dict[str, dict]) -> Dict[str, dict]:
    """Gemini 결과 키를 종목명/코드 기준으로 정규화한 맵을 생성한다."""
    normalized_results: Dict[str, dict] = {}
    if not isinstance(results_map, dict):
        return normalized_results

    for key, value in results_map.items():
        clean_name = re.sub(r"\s*\([0-9A-Za-z]+\)\s*$", "", str(key)).strip()
        normalized_results[clean_name] = value
        normalized_results[str(key)] = value
    return normalized_results


def _apply_gemini_reanalysis_results(
    all_signals: List[dict],
    results_map: Dict[str, dict],
) -> int:
    """
    Gemini 재분석 결과를 전체 시그널에 반영한다.
    반환값은 업데이트된 종목 수.
    """
    if not isinstance(all_signals, list) or not isinstance(results_map, dict):
        return 0

    normalized_results = _build_normalized_gemini_result_map(results_map)
    updated_count = 0

    for signal in all_signals:
        if not isinstance(signal, dict):
            continue
        name = signal.get("stock_name")
        stock_code = signal.get("stock_code", "")

        matched_result = None
        if name in normalized_results:
            matched_result = normalized_results[name]
        elif f"{name} ({stock_code})" in results_map:
            matched_result = results_map[f"{name} ({stock_code})"]
        elif stock_code in normalized_results:
            matched_result = normalized_results[stock_code]

        if not isinstance(matched_result, dict):
            continue

        if "score" not in signal or not isinstance(signal.get("score"), dict):
            signal["score"] = {}

        signal["score"]["llm_reason"] = matched_result.get("reason", "")
        signal["score"]["news"] = matched_result.get("score", 0)
        signal["ai_evaluation"] = {
            "action": matched_result.get("action", "HOLD"),
            "confidence": matched_result.get("confidence", 0),
            "model": matched_result.get("model", "gemini-2.0-flash"),
        }
        updated_count += 1

    return updated_count


__all__ = [
    "_select_signals_for_gemini_reanalysis",
    "_build_jongga_news_analysis_items",
    "_build_normalized_gemini_result_map",
    "_apply_gemini_reanalysis_results",
]
