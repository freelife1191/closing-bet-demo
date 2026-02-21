#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KR Market 라우트 헬퍼 모듈

판별/등급 재산정 로직을 분리해 라우트 파일 결합도를 낮춘다.
"""

from typing import Any


_VALID_AI_ACTIONS = {"BUY", "SELL", "HOLD"}
_INVALID_AI_REASONS = {
    "",
    "-",
    "n/a",
    "na",
    "none",
    "null",
    "분석 실패",
    "분석 대기중",
    "분석 대기 중",
    "분석중",
    "분석 중",
    "no analysis available.",
    "no analysis available",
    "analysis failed",
    "failed",
}


def _normalize_text(value: Any) -> str:
    """문자열 정규화 (None-safe)."""
    if value is None:
        return ""
    return str(value).strip()


def _is_meaningful_ai_reason(reason: Any) -> bool:
    """AI 분석 사유 텍스트가 실질적인 내용인지 판별."""
    reason_text = _normalize_text(reason)
    if not reason_text:
        return False
    return reason_text.lower() not in _INVALID_AI_REASONS


def _is_jongga_ai_analysis_completed(signal: dict) -> bool:
    """
    종가베팅 시그널의 AI 분석 완료 여부 판별.
    - 의미 있는 reason이 있어야 완료로 간주
    - action이 존재하면 BUY/SELL/HOLD 중 하나여야 완료로 간주
    """
    if not isinstance(signal, dict):
        return False

    ai_evaluation = signal.get("ai_evaluation")
    score = signal.get("score") if isinstance(signal.get("score"), dict) else {}

    ai_reason = ai_evaluation.get("reason") if isinstance(ai_evaluation, dict) else None
    llm_reason = score.get("llm_reason")

    if _is_meaningful_ai_reason(ai_reason):
        candidate_reason = ai_reason
    else:
        candidate_reason = llm_reason

    if not _is_meaningful_ai_reason(candidate_reason):
        return False

    if isinstance(ai_evaluation, dict):
        action = _normalize_text(ai_evaluation.get("action")).upper()
        if action and action not in _VALID_AI_ACTIONS:
            return False

    return True


def _is_vcp_ai_analysis_failed(row: dict) -> bool:
    """
    VCP 시그널의 AI 분석 실패 여부 판별.
    - action이 BUY/SELL/HOLD가 아니면 실패
    - reason이 비어있거나 실패/placeholder 문구면 실패
    """
    if not isinstance(row, dict):
        return True

    action = _normalize_text(row.get("ai_action")).upper()
    reason = row.get("ai_reason")

    if action not in _VALID_AI_ACTIONS:
        return True

    if not _is_meaningful_ai_reason(reason):
        return True

    return False


def _recalculate_jongga_grade(signal: dict) -> tuple[str, bool]:
    """종가베팅 단일 시그널 등급을 현재 기준으로 재산정."""
    try:
        tv = float(signal.get("trading_value", 0) or 0)
        change_pct = float(signal.get("change_pct", 0) or 0)
        score = signal.get("score") or {}
        score_total = int((score.get("total") if isinstance(score, dict) else score) or 0)
        score_details = signal.get("score_details") or {}
        foreign_net_buy = float(score_details.get("foreign_net_buy", 0) or 0)
        inst_net_buy = float(score_details.get("inst_net_buy", 0) or 0)
        has_dual_buy = foreign_net_buy > 0 and inst_net_buy > 0
    except Exception:
        return "D", False

    prev_grade = str(signal.get("grade", "")).strip().upper()
    new_grade = "D"
    if (
        tv >= 1_000_000_000_000
        and score_total >= 10
        and change_pct >= 3.0
        and has_dual_buy
    ):
        new_grade = "S"
    elif (
        tv >= 500_000_000_000
        and score_total >= 8
        and change_pct >= 3.0
        and has_dual_buy
    ):
        new_grade = "A"
    elif (
        tv >= 100_000_000_000
        and score_total >= 6
        and change_pct >= 3.0
        and has_dual_buy
    ):
        new_grade = "B"

    if prev_grade != new_grade:
        signal["grade"] = new_grade
        return new_grade, True

    return new_grade, False


def _recalculate_jongga_grades(data: dict) -> bool:
    """종가베팅 signals grade + by_grade 동기화."""
    if not data or "signals" not in data:
        return False

    signals = data.get("signals", [])
    if not isinstance(signals, list):
        return False

    changed = False
    grade_count = {"S": 0, "A": 0, "B": 0, "C": 0, "D": 0}

    for sig in signals:
        if not isinstance(sig, dict):
            continue
        _, did_change = _recalculate_jongga_grade(sig)
        changed = changed or did_change
        grade = str(sig.get("grade", "D")).strip().upper()
        if grade not in grade_count:
            grade_count[grade] = 0
        grade_count[grade] += 1

    prev_by_grade = data.get("by_grade")
    new_by_grade = {"S": 0, "A": 0, "B": 0, "C": 0, "D": 0}
    if isinstance(prev_by_grade, dict):
        for grade_key in new_by_grade:
            if grade_key in prev_by_grade:
                value = prev_by_grade[grade_key]
                if isinstance(value, (int, float)):
                    new_by_grade[grade_key] = int(value)
                else:
                    new_by_grade[grade_key] = 0

    for grade_key, count in grade_count.items():
        if grade_key in new_by_grade:
            new_by_grade[grade_key] = count
        elif count > 0:
            new_by_grade[grade_key] = count

    if data.get("by_grade") != new_by_grade:
        data["by_grade"] = new_by_grade
        changed = True

    return changed
