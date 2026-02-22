#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Screener 계산 보조 유틸
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import pandas as pd


def _get_ticker_padded_series(df: pd.DataFrame) -> pd.Series:
    if "_ticker_padded" in df.columns:
        return df["_ticker_padded"]

    padded = df["ticker"].astype(str).str.zfill(6)
    try:
        df["_ticker_padded"] = padded
        return df["_ticker_padded"]
    except Exception:
        return padded


def build_ticker_index(df: pd.DataFrame | None) -> dict[str, pd.DataFrame]:
    """ticker별 시계열 인덱스를 생성한다."""
    if df is None or df.empty or "ticker" not in df.columns:
        return {}

    working = df.copy()
    working["ticker"] = _get_ticker_padded_series(working)
    if "date" in working.columns:
        working = working.sort_values(["ticker", "date"])
    else:
        working = working.sort_values("ticker")

    return {
        str(ticker): group
        for ticker, group in working.groupby("ticker", sort=False)
    }


def calculate_volume_score(volume: pd.Series) -> tuple[int, float]:
    """거래량 점수와 비율을 계산한다."""
    current_vol = volume.iloc[-1] if not volume.empty else 0
    avg_vol = volume.tail(20).mean()
    vol_ratio = current_vol / avg_vol if avg_vol > 0 else 1.0

    vol_score = 0
    if vol_ratio > 3.0:
        vol_score = 20
    elif vol_ratio > 2.0:
        vol_score = 15
    elif vol_ratio > 1.0:
        vol_score = 10

    return vol_score, float(vol_ratio)


def _score_supply_core(
    foreign_5d: float,
    inst_5d: float,
    details: list[dict[str, Any]] | None,
) -> dict[str, int]:
    score = 0

    if foreign_5d > 50_000_000_000:
        score += 25
    elif foreign_5d > 20_000_000_000:
        score += 15
    elif foreign_5d > 0:
        score += 10

    if inst_5d > 50_000_000_000:
        score += 20
    elif inst_5d > 20_000_000_000:
        score += 10
    elif inst_5d > 0:
        score += 5

    consecutive_f = 0
    if details:
        for d in details:
            if d.get("netForeignerBuyVolume", 0) > 0:
                consecutive_f += 1
            else:
                break
    score += min(consecutive_f * 3, 15)

    consecutive_i = 0
    if details:
        for d in details:
            if d.get("netInstitutionBuyVolume", 0) > 0:
                consecutive_i += 1
            else:
                break
    score += min(consecutive_i * 2, 10)

    foreign_1d = 0
    inst_1d = 0
    if details and len(details) > 0:
        latest = details[0]
        foreign_1d = int(latest.get("netForeignerBuyVolume", 0))
        inst_1d = int(latest.get("netInstitutionBuyVolume", 0))

    return {
        "score": int(score),
        "foreign_5d": int(foreign_5d),
        "inst_5d": int(inst_5d),
        "foreign_1d": int(foreign_1d),
        "inst_1d": int(inst_1d),
    }


def score_supply_from_toss_trend(trend_data: dict[str, Any] | None) -> dict[str, int]:
    """Toss 수급 데이터에서 수급 점수를 계산한다."""
    if not trend_data:
        return {"score": 0, "foreign_1d": 0, "inst_1d": 0}

    foreign_5d = trend_data.get("foreign", 0)
    inst_5d = trend_data.get("institution", 0)
    details = trend_data.get("details", [])
    return _score_supply_core(foreign_5d=foreign_5d, inst_5d=inst_5d, details=details)


def score_supply_from_csv(
    ticker_inst: pd.DataFrame | None,
    target_datetime: datetime | None,
) -> dict[str, int]:
    """CSV 기반 수급 점수 계산."""
    if ticker_inst is None or ticker_inst.empty or len(ticker_inst) < 5:
        return {"score": 0, "foreign_1d": 0, "inst_1d": 0}

    working = ticker_inst
    if target_datetime is not None:
        working = working[working["date"] <= target_datetime]

    if len(working) < 5:
        return {"score": 0, "foreign_1d": 0, "inst_1d": 0}

    recent = working.tail(5)
    f_col = "foreign_net_buy" if "foreign_net_buy" in recent.columns else "foreign_buy"
    i_col = "inst_net_buy" if "inst_net_buy" in recent.columns else "inst_buy"

    if f_col not in recent.columns:
        f_col = "foreign"
    if i_col not in recent.columns:
        i_col = "institutional"

    foreign_5d = recent[f_col].sum() if f_col in recent.columns else 0
    inst_5d = recent[i_col].sum() if i_col in recent.columns else 0

    latest_row = working.iloc[-1]
    foreign_1d = int(latest_row[f_col]) if f_col in latest_row.index else 0
    inst_1d = int(latest_row[i_col]) if i_col in latest_row.index else 0

    details = []
    if f_col in recent.columns and i_col in recent.columns:
        for row in recent.iloc[::-1].itertuples(index=False):
            details.append(
                {
                    "netForeignerBuyVolume": float(getattr(row, f_col)),
                    "netInstitutionBuyVolume": float(getattr(row, i_col)),
                }
            )

    scored = _score_supply_core(foreign_5d=foreign_5d, inst_5d=inst_5d, details=details)
    scored["foreign_1d"] = foreign_1d
    scored["inst_1d"] = inst_1d
    return scored


def scale_vcp_score(vcp_score: float) -> int:
    """VCP 점수(0~100)를 최종 점수(0~10)로 변환한다."""
    return min(round(vcp_score / 10), 10)


__all__ = [
    "build_ticker_index",
    "calculate_volume_score",
    "score_supply_from_toss_trend",
    "score_supply_from_csv",
    "scale_vcp_score",
]
