#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KR Market 종가베팅 AI 페이로드 변환 헬퍼
"""

from typing import Any, List, Optional

from app.routes.kr_market_jongga_grade_helpers import _sort_jongga_signals
from app.routes.kr_market_signal_common import _parse_datetime_safe, _safe_float


def _extract_jongga_ai_evaluation(signal: dict) -> Optional[dict]:
    """
    종가베팅 시그널에서 AI 평가 객체를 추출한다.
    우선순위: score_details.ai_evaluation -> score.ai_evaluation -> ai_evaluation -> score.llm_reason
    """
    if not isinstance(signal, dict):
        return None

    ai_eval: Any = None
    score_details = signal.get("score_details")
    if isinstance(score_details, dict):
        ai_eval = score_details.get("ai_evaluation")

    score = signal.get("score")
    if not ai_eval and isinstance(score, dict):
        ai_eval = score.get("ai_evaluation")

    if not ai_eval:
        ai_eval = signal.get("ai_evaluation")

    if not ai_eval and isinstance(score, dict):
        ai_eval = score.get("llm_reason")

    if isinstance(ai_eval, str):
        return {"reason": ai_eval, "action": "HOLD", "confidence": 0}

    return ai_eval if isinstance(ai_eval, dict) else None


def _extract_jongga_score_value(signal: dict, allow_numeric_fallback: bool) -> float:
    """종가 시그널에서 정렬/표시용 점수 값을 추출한다."""
    raw_score = signal.get("score")
    if isinstance(raw_score, dict):
        return _safe_float(raw_score.get("total", 0), default=0.0)
    if allow_numeric_fallback:
        return _safe_float(raw_score, default=0.0)
    return 0.0


def _build_ai_signal_from_jongga_signal(
    signal: dict,
    include_without_ai: bool,
    allow_numeric_score_fallback: bool,
) -> Optional[dict]:
    """종가 시그널 1개를 AI 분석 응답 스키마로 변환한다."""
    if not isinstance(signal, dict):
        return None

    ai_eval = _extract_jongga_ai_evaluation(signal)
    if not include_without_ai and not ai_eval:
        return None

    return {
        "ticker": str(signal.get("stock_code", "")).zfill(6),
        "name": signal.get("stock_name", ""),
        "grade": signal.get("grade"),
        "score": _extract_jongga_score_value(signal, allow_numeric_score_fallback),
        "current_price": signal.get("current_price", 0),
        "entry_price": signal.get("entry_price", 0),
        "vcp_score": 0,
        "contraction_ratio": signal.get("contraction_ratio", 0),
        "foreign_5d": signal.get("foreign_5d", 0),
        "inst_5d": signal.get("inst_5d", 0),
        "gemini_recommendation": ai_eval,
        "news": signal.get("news_items", []),
    }


def _build_ai_signals_from_jongga_results(
    signals: Any,
    include_without_ai: bool,
    allow_numeric_score_fallback: bool,
) -> List[dict]:
    """종가베팅 결과(signals)를 AI 응답용 리스트로 변환한다."""
    if not isinstance(signals, list):
        return []

    ai_signals: List[dict] = []
    for signal in signals:
        converted = _build_ai_signal_from_jongga_signal(
            signal,
            include_without_ai=include_without_ai,
            allow_numeric_score_fallback=allow_numeric_score_fallback,
        )
        if converted:
            ai_signals.append(converted)

    _sort_jongga_signals(ai_signals)
    return ai_signals


def _should_use_jongga_ai_payload(jongga_data: Any, vcp_data: Any) -> bool:
    """jongga_v2 데이터 우선 사용 여부를 판정한다."""
    if not isinstance(jongga_data, dict):
        return False
    signals = jongga_data.get("signals")
    if not isinstance(signals, list) or not signals:
        return False

    if not isinstance(vcp_data, dict) or not vcp_data.get("signals"):
        return True

    jongga_time = _parse_datetime_safe(
        jongga_data.get("updated_at") or jongga_data.get("date")
    )
    vcp_time = _parse_datetime_safe(vcp_data.get("generated_at"))

    if jongga_time and vcp_time:
        return jongga_time >= vcp_time

    # 시간 비교가 불가능하면 jongga를 우선 사용한다(기존 우선순위 유지).
    return True


__all__ = [
    "_extract_jongga_ai_evaluation",
    "_extract_jongga_score_value",
    "_build_ai_signal_from_jongga_signal",
    "_build_ai_signals_from_jongga_results",
    "_should_use_jongga_ai_payload",
]
