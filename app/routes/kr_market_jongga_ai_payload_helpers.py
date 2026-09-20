#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KR Market 종가베팅 AI 페이로드 변환 헬퍼
"""

import math
import sys
from typing import Any, List, Optional

from app.routes.kr_market_jongga_grade_helpers import _sort_jongga_signals
from app.routes.kr_market_signal_common import (
    _VALID_AI_ACTIONS,
    _normalize_text,
    _parse_datetime_safe,
    _safe_float,
)


def _extract_jongga_ai_evaluation(signal: dict) -> Optional[dict]:
    """
    종가베팅 시그널에서 AI 평가 객체를 추출한다.
    우선순위: ai_evaluation -> score.ai_evaluation -> score_details.ai_evaluation -> score.llm_reason
    """
    if not isinstance(signal, dict):
        return None

    score = signal.get("score")
    score_details = signal.get("score_details")
    candidates = [
        signal.get("ai_evaluation"),
        score.get("ai_evaluation") if isinstance(score, dict) else None,
        score_details.get("ai_evaluation") if isinstance(score_details, dict) else None,
    ]
    for candidate in candidates:
        if isinstance(candidate, str):
            reason = _normalize_text(candidate)
            if reason:
                return {"reason": reason, "action": "HOLD", "confidence": None}
            continue
        if not isinstance(candidate, dict):
            continue
        action = candidate.get("action").strip().upper() if isinstance(candidate.get("action"), str) else ""
        reason = candidate.get("reason").strip() if isinstance(candidate.get("reason"), str) else ""
        if action in _VALID_AI_ACTIONS:
            evaluation = _build_jongga_ai_evaluation(candidate, action, reason)
        elif reason:
            evaluation = _build_jongga_ai_evaluation(candidate, "HOLD", reason)
        else:
            continue

        if reason:
            return {**evaluation, "reason": reason}

        llm_reason = score.get("llm_reason") if isinstance(score, dict) else None
        legacy_reason = llm_reason.strip() if isinstance(llm_reason, str) else ""
        return {**evaluation, "reason": legacy_reason} if legacy_reason else evaluation

    llm_reason = score.get("llm_reason") if isinstance(score, dict) else None
    reason = llm_reason.strip() if isinstance(llm_reason, str) else ""
    if reason:
        # 사유 문자열만 남은 기록은 매매 판단을 지어내지 않고 관망으로 표시한다.
        return {"reason": reason, "action": "HOLD", "confidence": None}

    return None


def _build_jongga_ai_evaluation(candidate: dict, action: str, reason: str) -> dict:
    """AI 응답에서 화면과 VCP가 소비하는 네 필드만 안전하게 전달한다."""
    evaluation = {"action": action}
    if reason:
        evaluation["reason"] = reason

    confidence = candidate.get("confidence")
    if confidence is None:
        if "confidence" in candidate:
            evaluation["confidence"] = None
    elif isinstance(confidence, str):
        evaluation["confidence"] = confidence
    elif (
        not isinstance(confidence, bool)
        and isinstance(confidence, (int, float))
        and -sys.float_info.max <= confidence <= sys.float_info.max
        and math.isfinite(confidence)
    ):
        evaluation["confidence"] = confidence

    model = candidate.get("model")
    if isinstance(model, str):
        evaluation["model"] = model
    return evaluation


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
