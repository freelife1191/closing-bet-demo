#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Engine - Market Gate Logic Scoring

Market Gate 지표 계산/점수/상태 빌더 함수를 분리한다.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Tuple

import pandas as pd


def calculate_indicators(
    *,
    df: pd.DataFrame,
    bench_df: pd.DataFrame | None,
    config: Any,
    logger: logging.Logger,
) -> pd.DataFrame:
    """기술적 지표 계산 (RS 포함)."""
    close = df["close"]

    df["ma20"] = close.ewm(span=config.kospi_ma_short, adjust=False).mean()
    df["ma60"] = close.ewm(span=config.kospi_ma_long, adjust=False).mean()

    delta = close.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df["rsi"] = 100 - (100 / (1 + rs))

    exp1 = close.ewm(span=12, adjust=False).mean()
    exp2 = close.ewm(span=26, adjust=False).mean()
    df["macd"] = exp1 - exp2
    df["signal"] = df["macd"].ewm(span=9, adjust=False).mean()

    df["vol_ma20"] = df["volume"].rolling(window=20).mean()

    if "change_pct" not in df.columns:
        df["change_pct"] = close.pct_change() * 100

    try:
        df["ret_20d"] = df["close"].pct_change(periods=20) * 100
        if bench_df is not None and not bench_df.empty:
            df["date_dt"] = pd.to_datetime(df["date"])
            bench_df["date_dt"] = pd.to_datetime(bench_df["date"])
            merged = pd.merge(df, bench_df[["date_dt", "bench_close"]], on="date_dt", how="left")
            merged["bench_ret_20d"] = merged["bench_close"].pct_change(periods=20) * 100
            merged["rs_diff"] = merged["ret_20d"] - merged["bench_ret_20d"]
            df["rs_diff"] = merged["rs_diff"]
        else:
            df["rs_diff"] = 0.0
    except Exception as error:
        logger.warning(f"RS calculation failed: {error}")
        df["rs_diff"] = 0.0

    return df.fillna(0)


def score_trend(row: Any) -> int:
    return 25 if row["ma20"] > row["ma60"] else 0


def score_rsi(row: Any) -> int:
    rsi = row["rsi"]
    if 50 <= rsi <= 70:
        return 25
    if rsi > 70:
        return 10
    if rsi < 30:
        return 15
    return 5


def score_macd(row: Any) -> int:
    return 20 if row["macd"] > row["signal"] else 0


def score_volume(row: Any) -> int:
    if row["vol_ma20"] > 0 and row["volume"] > row["vol_ma20"]:
        return 15
    return 0


def score_rs(row: Any) -> int:
    rs_value = row.get("rs_diff", 0.0)
    if rs_value > 2.0:
        return 15
    if 0 <= rs_value <= 2.0:
        return 10
    if -2.0 <= rs_value < 0:
        return 5
    return 0


def score_macro(usd_krw: float, config: Any) -> Tuple[int, str]:
    status = "SAFE"
    score = 15
    if usd_krw >= config.usd_krw_danger:
        status = "DANGER"
        score = -20
    elif usd_krw >= config.usd_krw_warning:
        status = "WARNING"
        score = 0
    return score, status


def score_supply(data: Dict, config: Any) -> int:
    if not data:
        return 0

    f_buy = data.get("foreign_buy", 0)
    score = 0
    if f_buy > 0:
        score += 10
    if f_buy > config.foreign_net_buy_threshold:
        score += 5
    return min(score, 15)


def build_market_status(total_score: int) -> Tuple[str, str, str]:
    if total_score >= 70:
        return "강세장 (Bullish)", "Bullish", "GREEN"
    if total_score >= 40:
        return "중립 (Neutral)", "Neutral", "YELLOW"
    return "약세장 (Bearish)", "Bearish", "RED"


def build_gate_reason(total_score: int, macro_status: str) -> str:
    if total_score < 40:
        gate_reason = f"기술적 점수 미달 ({total_score}/40)"
    else:
        gate_reason = "시장 양호 (Technical)"
    if macro_status == "DANGER":
        gate_reason += " [환율 위험]"
    return gate_reason


def build_sector_signals(sector_data: Dict[str, float]) -> list[dict]:
    return [
        {
            "name": name,
            "change_pct": change_pct,
            "signal": "Bullish" if change_pct > 0.5 else "Bearish" if change_pct < -0.5 else "Neutral",
        }
        for name, change_pct in sector_data.items()
    ]


__all__ = [
    "calculate_indicators",
    "score_trend",
    "score_rsi",
    "score_macd",
    "score_volume",
    "score_rs",
    "score_macro",
    "score_supply",
    "build_market_status",
    "build_gate_reason",
    "build_sector_signals",
]
