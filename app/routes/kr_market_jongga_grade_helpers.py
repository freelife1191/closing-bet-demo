#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KR Market 종가베팅 시그널 등급/정렬 헬퍼
"""

from typing import List

from app.routes.kr_market_signal_common import (
    _is_meaningful_ai_reason,
    _normalize_text,
    _VALID_AI_ACTIONS,
)

_JONGGA_GRADE_PRIORITY = {"S": 3, "A": 2, "B": 1}


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


def _jongga_sort_key(signal: dict) -> tuple[int, float]:
    """종가베팅 시그널 정렬 키: Grade(S>A>B) 우선, 이후 점수 내림차순."""
    grade_value = _JONGGA_GRADE_PRIORITY.get(
        str(signal.get("grade", "")).strip().upper(),
        0,
    )
    raw_score = signal.get("score", 0)
    if isinstance(raw_score, dict):
        score_value = raw_score.get("total", 0)
    else:
        score_value = raw_score
    try:
        numeric_score = float(score_value or 0)
    except Exception:
        numeric_score = 0
    return grade_value, numeric_score


def _sort_jongga_signals(signals: List[dict]) -> None:
    """종가베팅 시그널 리스트를 규칙에 맞춰 정렬한다."""
    if not isinstance(signals, list):
        return
    signals.sort(key=_jongga_sort_key, reverse=True)


__all__ = [
    "_JONGGA_GRADE_PRIORITY",
    "_is_jongga_ai_analysis_completed",
    "_recalculate_jongga_grade",
    "_recalculate_jongga_grades",
    "_jongga_sort_key",
    "_sort_jongga_signals",
]
