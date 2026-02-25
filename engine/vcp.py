#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Engine - VCP Pattern Detector
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from engine.constants import VCP_THRESHOLDS


@dataclass(frozen=True)
class VCPResult:
    """VCP 패턴 감지 결과."""

    ticker: str
    name: str
    vcp_score: int
    contraction_ratio: float
    is_vcp: bool
    date: str
    entry_price: float
    pattern_desc: str = ""


def _safe_float(value, default: float = 0.0) -> float:
    try:
        number = float(value)
        if pd.isna(number):
            return default
        return number
    except Exception:
        return default


def _normalize_price_frame(df: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(df, pd.DataFrame):
        return pd.DataFrame()
    if df.empty:
        return pd.DataFrame()

    required_columns = {"high", "low", "close", "volume"}
    if not required_columns.issubset(set(df.columns)):
        return pd.DataFrame()

    frame = df.copy()
    for column in required_columns:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")

    if "date" in frame.columns:
        frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
        frame = frame.sort_values("date")
    else:
        frame = frame.sort_index()

    frame = frame.dropna(subset=list(required_columns))
    return frame


def _extract_date_text(frame: pd.DataFrame) -> str:
    if frame.empty or "date" not in frame.columns:
        return ""

    raw = frame.iloc[-1].get("date")
    timestamp = pd.to_datetime(raw, errors="coerce")
    if pd.isna(timestamp):
        return ""
    return timestamp.strftime("%Y-%m-%d")


def _build_fail_result(
    *,
    ticker: str,
    name: str,
    frame: pd.DataFrame,
    current_price: float,
    reason: str,
    contraction_ratio: float = 1.0,
    score: int = 0,
) -> VCPResult:
    return VCPResult(
        ticker=ticker,
        name=name,
        vcp_score=int(score),
        contraction_ratio=round(_safe_float(contraction_ratio, 1.0), 4),
        is_vcp=False,
        date=_extract_date_text(frame),
        entry_price=round(_safe_float(current_price, 0.0), 2),
        pattern_desc=reason,
    )


def detect_vcp_pattern(df: pd.DataFrame, ticker: str, name: str) -> VCPResult:
    """
    VCP 패턴을 감지하고 0~100 점수를 반환한다.

    점수 구성:
    - 변동성 수축: 최대 40점
    - 거래량 감소: 최대 30점
    - 추세 정렬: 최대 30점
    """
    frame = _normalize_price_frame(df)
    if frame.empty:
        return _build_fail_result(
            ticker=ticker,
            name=name,
            frame=frame,
            current_price=0.0,
            reason="Invalid or empty price frame",
        )

    min_points = int(VCP_THRESHOLDS.MIN_DATA_POINTS)
    if len(frame) < min_points:
        return _build_fail_result(
            ticker=ticker,
            name=name,
            frame=frame,
            current_price=_safe_float(frame["close"].iloc[-1], 0.0),
            reason=f"Insufficient data: {len(frame)} < {min_points}",
        )

    lookback = min(int(VCP_THRESHOLDS.MAX_LOOKBACK_DAYS), len(frame))
    recent = frame.tail(lookback).copy()

    current_close = _safe_float(recent["close"].iloc[-1], 0.0)
    recent_high = _safe_float(recent["high"].max(), 0.0)
    if recent_high <= 0:
        return _build_fail_result(
            ticker=ticker,
            name=name,
            frame=recent,
            current_price=current_close,
            reason="Invalid recent high",
        )

    near_high_min = recent_high * float(VCP_THRESHOLDS.PRICE_NEAR_HIGH_RATIO)
    if current_close < near_high_min:
        return _build_fail_result(
            ticker=ticker,
            name=name,
            frame=recent,
            current_price=current_close,
            reason=f"Price too low: {current_close:.2f} < {near_high_min:.2f}",
        )

    score = 0
    reasons: list[str] = []

    # 변동성 수축: 최근 5일 평균 변동폭 vs 이전 15일 평균 변동폭
    range_window = recent.tail(20)
    recent_range = (range_window["high"].tail(5) - range_window["low"].tail(5)).mean()
    prev_ranges = range_window["high"].iloc[:-5] - range_window["low"].iloc[:-5]
    baseline_range = prev_ranges.mean() if len(prev_ranges) > 0 else recent_range
    contraction_ratio = (
        _safe_float(recent_range, 0.0) / _safe_float(baseline_range, 0.0)
        if _safe_float(baseline_range, 0.0) > 0
        else 1.0
    )

    if contraction_ratio <= 0.5:
        score += 40
        reasons.append("Strong volatility contraction")
    elif contraction_ratio <= 0.7:
        score += 30
        reasons.append("Healthy volatility contraction")
    elif contraction_ratio <= 0.9:
        score += 15
        reasons.append("Mild volatility contraction")

    # 거래량 드라이업: 최근 5일 평균 거래량 vs 이전 15일 평균 거래량
    recent_vol = range_window["volume"].tail(5).mean()
    prev_vol = range_window["volume"].iloc[:-5].mean()
    volume_ratio = (
        _safe_float(recent_vol, 0.0) / _safe_float(prev_vol, 0.0)
        if _safe_float(prev_vol, 0.0) > 0
        else 1.0
    )

    if volume_ratio <= 0.5:
        score += 30
        reasons.append("Volume dry-up")
    elif volume_ratio <= 0.7:
        score += 20
        reasons.append("Volume contraction")
    elif volume_ratio <= 0.9:
        score += 10
        reasons.append("Volume slightly lower")

    closes = recent["close"]
    ma5 = closes.tail(5).mean()
    ma20 = closes.tail(20).mean()
    if current_close > ma5 > ma20:
        score += 30
        reasons.append("MA alignment")
    elif current_close > ma20:
        score += 15
        reasons.append("Price above MA20")

    min_score = int(VCP_THRESHOLDS.MIN_SCORE)
    contraction_max = float(VCP_THRESHOLDS.CONTRACTION_RATIO)
    is_vcp = contraction_ratio <= contraction_max and score >= min_score

    pattern_desc = (
        ", ".join(reasons)
        if reasons
        else "No meaningful VCP features"
    )
    pattern_desc = (
        f"{pattern_desc} | CR={contraction_ratio:.3f}, VR={volume_ratio:.3f}, Score={score}"
    )

    return VCPResult(
        ticker=ticker,
        name=name,
        vcp_score=int(score),
        contraction_ratio=round(_safe_float(contraction_ratio, 1.0), 4),
        is_vcp=bool(is_vcp),
        date=_extract_date_text(recent),
        entry_price=round(recent_high, 2),
        pattern_desc=pattern_desc,
    )


__all__ = ["VCPResult", "detect_vcp_pattern"]
