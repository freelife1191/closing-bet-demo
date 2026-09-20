#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KR Market VCP cache update service.
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any, Callable

from engine.ticker_utils import normalize_ticker
from engine.vcp_ai_orchestration_helpers import VCP_AI_RECOMMENDATION_FIELDS
from services.kr_market_data_cache_service import atomic_write_text


_normalize_ticker = normalize_ticker


def _normalize_ai_payload(ai_payload: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(ai_payload, dict):
        return {}

    normalized: dict[str, dict[str, Any]] = {}
    for key in VCP_AI_RECOMMENDATION_FIELDS:
        value = ai_payload.get(key)
        if isinstance(value, dict) and value:
            normalized[key] = value
    return normalized


def update_vcp_ai_cache_files(
    target_date: str | None,
    updated_recommendations: dict[str, Any],
    get_data_path: Callable[[str], str],
    load_json_file: Callable[[str], dict[str, Any]],
    logger: Any,
    ai_results: dict[str, Any] | None = None,
) -> int:
    """VCP AI 캐시 파일(ai_analysis_results/kr_ai_analysis)에 재분석 결과를 반영한다."""
    if not updated_recommendations and not ai_results:
        return 0

    normalized_gemini_updates: dict[str, dict[str, Any]] = {}
    if isinstance(updated_recommendations, dict):
        for ticker, recommendation in updated_recommendations.items():
            if not isinstance(recommendation, dict) or not recommendation:
                continue
            ticker_key = _normalize_ticker(ticker)
            if ticker_key:
                normalized_gemini_updates[ticker_key] = recommendation

    normalized_ai_results: dict[str, dict[str, dict[str, Any]]] = {}
    if isinstance(ai_results, dict):
        for ticker, ai_payload in ai_results.items():
            normalized_payload = _normalize_ai_payload(ai_payload)
            if normalized_payload:
                ticker_key = _normalize_ticker(ticker)
                if ticker_key:
                    normalized_ai_results[ticker_key] = normalized_payload

    target_tickers = set(normalized_gemini_updates) | set(normalized_ai_results)
    if not target_tickers:
        return 0

    date_str = str(target_date or "").replace("-", "")
    candidate_files = [
        f"ai_analysis_results_{date_str}.json" if date_str else "",
        "ai_analysis_results.json",
        f"kr_ai_analysis_{date_str}.json" if date_str else "",
        "kr_ai_analysis.json",
    ]

    updated_files = 0
    now_iso = datetime.now().isoformat()

    for filename in candidate_files:
        if not filename:
            continue

        filepath = get_data_path(filename)
        if not os.path.exists(filepath):
            continue

        try:
            data = load_json_file(filename)
            signals = data.get("signals", []) if isinstance(data, dict) else []
            if not isinstance(signals, list) or not signals:
                continue

            changed = False
            for item in signals:
                if not isinstance(item, dict):
                    continue
                ticker = _normalize_ticker(item.get("ticker") or item.get("stock_code"))
                if not ticker or ticker not in target_tickers:
                    continue

                gemini_rec = normalized_gemini_updates.get(ticker)
                if isinstance(gemini_rec, dict) and item.get("gemini_recommendation") != gemini_rec:
                    item["gemini_recommendation"] = gemini_rec
                    changed = True

                ai_payload = normalized_ai_results.get(ticker)
                if not isinstance(ai_payload, dict):
                    continue
                for key, recommendation in ai_payload.items():
                    if item.get(key) != recommendation:
                        item[key] = recommendation
                        changed = True

            if not changed:
                continue

            data["generated_at"] = now_iso
            atomic_write_text(
                filepath,
                json.dumps(data, ensure_ascii=False, indent=2),
            )
            updated_files += 1
        except Exception as error:
            logger.warning(f"VCP AI cache update failed ({filename}): {error}")

    return updated_files
