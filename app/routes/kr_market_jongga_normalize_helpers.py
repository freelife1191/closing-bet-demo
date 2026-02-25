#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KR Market 종가베팅 시그널 정규화/가격 반영 헬퍼
"""

from typing import Dict, List


def _normalize_ticker(value: object) -> str:
    text = str(value or "").strip()
    digits = "".join(ch for ch in text if ch.isdigit())
    if not digits:
        return ""
    return digits.zfill(6)


def _safe_float(value, default: float = 0.0) -> float:
    if isinstance(value, str):
        value = value.replace(",", "").replace("₩", "").replace("$", "").strip()
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return default


def _safe_int(value, default: int = 0) -> int:
    if isinstance(value, str):
        value = value.replace(",", "").replace("₩", "").replace("$", "").strip()
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return default


def _apply_latest_prices_to_jongga_signals(
    signals: List[dict],
    latest_price_map: Dict[str, float],
) -> int:
    """
    종가베팅 시그널에 최신가를 반영하고 수익률(return_pct)을 재계산한다.
    반환값은 가격 반영된 시그널 수.
    """
    if not isinstance(signals, list) or not isinstance(latest_price_map, dict):
        return 0

    updated_count = 0
    for signal in signals:
        if not isinstance(signal, dict):
            continue

        raw_code = signal.get("code") or signal.get("ticker") or signal.get("stock_code")
        ticker = _normalize_ticker(raw_code)
        if not ticker or ticker == "000000":
            continue
        if ticker not in latest_price_map:
            continue

        real_price = latest_price_map[ticker]
        signal["current_price"] = real_price

        entry_price = _safe_float(signal.get("entry_price") or signal.get("close"))

        if entry_price > 0:
            return_pct = ((real_price - entry_price) / entry_price) * 100
            signal["return_pct"] = round(return_pct, 2)

        updated_count += 1

    return updated_count


def _normalize_jongga_signal_for_frontend(signal: dict) -> None:
    """
    종가베팅 시그널을 프론트엔드 기대 스키마로 정규화한다.
    (in-place)
    """
    if not isinstance(signal, dict):
        return

    stock_code = _normalize_ticker(
        signal.get("stock_code") or signal.get("ticker") or signal.get("code")
    )
    if stock_code:
        signal["stock_code"] = stock_code
        if not signal.get("ticker"):
            signal["ticker"] = stock_code

    stock_name = str(signal.get("stock_name") or signal.get("name") or "").strip()
    if stock_name:
        signal["stock_name"] = stock_name
        if not signal.get("name"):
            signal["name"] = stock_name

    if "change_pct" not in signal and "return_pct" in signal:
        signal["change_pct"] = signal["return_pct"]
    elif "change_pct" not in signal:
        entry_float = _safe_float(signal.get("entry_price", 0))
        current_float = _safe_float(signal.get("current_price", 0))
        if entry_float > 0 and current_float:
            signal["change_pct"] = round(((current_float - entry_float) / entry_float) * 100, 2)
        else:
            signal["change_pct"] = 0

    raw_score = signal.get("score", 0)
    if not isinstance(raw_score, dict):
        score_int = _safe_int(raw_score)
        signal["score"] = {
            "total": score_int,
            "base_score": score_int,
            "bonus_score": 0,
        }

    if "checklist" not in signal:
        signal["checklist"] = {
            "has_news": False,
            "volume_surge": False,
            "supply_demand": _safe_float(signal.get("foreign_5d", 0)) > 0
            or _safe_float(signal.get("inst_5d", 0)) > 0,
        }

    entry_float = _safe_float(signal.get("entry_price", 0))
    if not signal.get("target_price") and entry_float > 0:
        signal["target_price"] = round(entry_float * 1.09)
    if not signal.get("stop_price") and entry_float > 0:
        signal["stop_price"] = round(entry_float * 0.95)

    if "ai_evaluation" not in signal and signal.get("ai_action"):
        signal["ai_evaluation"] = {
            "action": signal.get("ai_action", "HOLD"),
            "confidence": signal.get("ai_confidence", 0),
            "reason": signal.get("ai_reason", ""),
            "model": "gemini",
        }


def _normalize_jongga_signals_for_frontend(signals: List[dict]) -> None:
    """종가베팅 시그널 리스트를 프론트엔드 스키마로 정규화한다."""
    if not isinstance(signals, list):
        return
    for signal in signals:
        _normalize_jongga_signal_for_frontend(signal)


__all__ = [
    "_apply_latest_prices_to_jongga_signals",
    "_normalize_jongga_signal_for_frontend",
    "_normalize_jongga_signals_for_frontend",
]
