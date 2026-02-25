#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KR Market 종가베팅 시그널 등급/정렬 헬퍼
"""

from functools import lru_cache
from typing import Any, List

from engine.config import SignalConfig
from engine.grade_classifier import create_grade_classifier
from engine.models import Grade, ScoreDetail, StockData, SupplyData

from app.routes.kr_market_signal_common import (
    _is_meaningful_ai_reason,
    _normalize_text,
    _VALID_AI_ACTIONS,
)

_JONGGA_GRADE_PRIORITY = {"S": 3, "A": 2, "B": 1}


def _normalize_numeric_text(value: str) -> str:
    return (
        str(value)
        .replace(",", "")
        .replace("₩", "")
        .replace("$", "")
        .replace("%", "")
        .replace("원", "")
        .strip()
    )


def _to_float(value: object, default: float) -> float:
    if isinstance(value, str):
        value = _normalize_numeric_text(value)
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _to_int(value: object, default: int) -> int:
    if isinstance(value, str):
        value = _normalize_numeric_text(value)
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _to_optional_float(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, str):
        normalized = _normalize_numeric_text(value)
        if not normalized:
            return None
        value = normalized
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _normalize_stock_code(signal: dict[str, Any]) -> str:
    raw_code = signal.get("stock_code") or signal.get("ticker") or signal.get("code") or ""
    digits = "".join(ch for ch in str(raw_code) if ch.isdigit())
    return digits.zfill(6) if digits else "000000"


def _resolve_supply_value(
    signal: dict[str, Any],
    score_details: dict[str, Any],
    *keys: str,
) -> float:
    for key in keys:
        value = _to_optional_float(score_details.get(key))
        if value is not None:
            return value
    for key in keys:
        value = _to_optional_float(signal.get(key))
        if value is not None:
            return value
    return 0.0


@lru_cache(maxsize=1)
def _get_grade_classifier():
    return create_grade_classifier(SignalConfig())


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
        score = signal.get("score") or {}
        score_total = _to_int(score.get("total") if isinstance(score, dict) else score, 0)
        score_details = signal.get("score_details")
        if not isinstance(score_details, dict):
            score_details = {}

        stock = StockData(
            code=_normalize_stock_code(signal),
            name=str(signal.get("stock_name") or signal.get("name") or "").strip(),
            market=str(signal.get("market") or "KOSPI").strip() or "KOSPI",
            close=_to_float(
                signal.get("current_price", signal.get("entry_price", signal.get("close", 0))),
                0.0,
            ),
            change_pct=_to_float(signal.get("change_pct", 0), 0.0),
            trading_value=_to_float(signal.get("trading_value", 0), 0.0),
            volume=_to_int(signal.get("volume", 0), 0),
            high_52w=_to_float(signal.get("high_52w", 0), 0.0),
            low_52w=_to_float(signal.get("low_52w", 0), 0.0),
        )

        supply = SupplyData(
            foreign_buy_5d=_to_int(
                _resolve_supply_value(
                    signal,
                    score_details,
                    "foreign_net_buy",
                    "foreign_5d",
                    "foreign_buy_5d",
                ),
                0,
            ),
            inst_buy_5d=_to_int(
                _resolve_supply_value(
                    signal,
                    score_details,
                    "inst_net_buy",
                    "inst_5d",
                    "institutional_net_buy_5d",
                    "inst_buy_5d",
                ),
                0,
            ),
        )

        grade = _get_grade_classifier().classify(
            stock=stock,
            score=ScoreDetail(total=score_total),
            score_details=score_details,
            supply=supply,
        )
    except Exception:
        return "D", False

    prev_grade = str(signal.get("grade", "")).strip().upper()
    new_grade = grade.value if isinstance(grade, Grade) else "D"

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
    grade_count = {"S": 0, "A": 0, "B": 0, "D": 0}

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
    new_by_grade = {"S": 0, "A": 0, "B": 0, "D": 0}
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
