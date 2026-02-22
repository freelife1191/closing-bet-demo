#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KR Market AI payload 구성 서비스
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Callable
import logging


def _has_non_empty_signals(payload: dict[str, Any] | None) -> bool:
    if not isinstance(payload, dict):
        return False
    signals = payload.get("signals", [])
    return isinstance(signals, list) and len(signals) > 0


def build_ai_analysis_payload_for_target_date(
    target_date: str | None,
    load_json_file: Callable[[str], dict[str, Any]],
    build_ai_signals_from_jongga_results: Callable[..., list[dict[str, Any]]],
    normalize_ai_payload_tickers: Callable[[dict[str, Any]], dict[str, Any]],
    logger: logging.Logger,
    now: datetime | None = None,
) -> dict[str, Any] | None:
    """요청 날짜 기준 AI 분석 payload를 구성한다."""
    if not target_date:
        return None

    current_time = now or datetime.now()

    try:
        date_str = str(target_date).replace("-", "")
        v2_result = load_json_file(f"jongga_v2_results_{date_str}.json")
        v2_signals = build_ai_signals_from_jongga_results(
            v2_result.get("signals", []),
            include_without_ai=False,
            allow_numeric_score_fallback=True,
        )
        if v2_signals:
            return {
                "signals": v2_signals,
                "generated_at": v2_result.get("updated_at", current_time.isoformat()),
                "signal_date": target_date,
                "source": "jongga_v2_integrated_history",
            }

        analysis = load_json_file(f"kr_ai_analysis_{date_str}.json")
        if not analysis:
            analysis = load_json_file(f"ai_analysis_results_{date_str}.json")
        if analysis:
            return normalize_ai_payload_tickers(analysis)

        return {
            "signals": [],
            "generated_at": current_time.isoformat(),
            "signal_date": target_date,
            "message": "해당 날짜의 AI 분석 데이터가 없습니다.",
        }
    except Exception as e:
        logger.warning(f"과거 AI 분석 데이터 로드 실패: {e}")
        return None


def build_latest_ai_analysis_payload(
    load_json_file: Callable[[str], dict[str, Any]],
    should_use_jongga_ai_payload: Callable[[dict[str, Any], dict[str, Any]], bool],
    build_ai_signals_from_jongga_results: Callable[..., list[dict[str, Any]]],
    normalize_ai_payload_tickers: Callable[[dict[str, Any]], dict[str, Any]],
    format_signal_date: Callable[[str], str],
    now: datetime | None = None,
) -> dict[str, Any]:
    """최신 AI 분석 payload를 우선순위에 따라 구성한다."""
    current_time = now or datetime.now()
    jongga_data = load_json_file("jongga_v2_latest.json")
    vcp_data = load_json_file("ai_analysis_results.json")

    if should_use_jongga_ai_payload(jongga_data, vcp_data):
        ai_signals = build_ai_signals_from_jongga_results(
            jongga_data.get("signals", []),
            include_without_ai=True,
            allow_numeric_score_fallback=False,
        )
        if ai_signals:
            return {
                "signals": ai_signals,
                "generated_at": jongga_data.get("updated_at", current_time.isoformat()),
                "signal_date": format_signal_date(jongga_data.get("date", "")),
                "source": "jongga_v2_integrated_history",
            }

    kr_ai_data = load_json_file("kr_ai_analysis.json")
    if _has_non_empty_signals(kr_ai_data):
        return normalize_ai_payload_tickers(kr_ai_data)

    # 성능: 이미 로드한 vcp_data(ai_analysis_results.json)를 재사용한다.
    if _has_non_empty_signals(vcp_data):
        return normalize_ai_payload_tickers(vcp_data)

    return {"signals": [], "message": "AI 분석 데이터가 없습니다."}
