#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Signal Tracker 수급 점수 계산 헬퍼.
"""

from __future__ import annotations

import logging
from typing import Callable

import numpy as np
import pandas as pd


REQUIRED_SUPPLY_COLUMNS = {"ticker", "date", "foreign_buy", "inst_buy"}


def _get_ticker_padded_series(df: pd.DataFrame) -> pd.Series:
    if "_ticker_padded" in df.columns:
        return df["_ticker_padded"]

    padded = df["ticker"].astype(str).str.zfill(6)
    try:
        df["_ticker_padded"] = padded
        return df["_ticker_padded"]
    except Exception:
        return padded


def build_supply_score_frame(
    raw_df: pd.DataFrame,
    *,
    foreign_min: float,
    count_consecutive_positive: Callable[[np.ndarray], int],
    logger: logging.Logger,
) -> pd.DataFrame:
    """최근 5일 수급 집계 및 점수 프레임 생성."""
    if not REQUIRED_SUPPLY_COLUMNS.issubset(raw_df.columns):
        missing = REQUIRED_SUPPLY_COLUMNS - set(raw_df.columns)
        logger.error(f"❌ 수급 데이터 필수 컬럼 누락: {sorted(missing)}")
        return pd.DataFrame()

    working = raw_df.copy()
    working["ticker"] = _get_ticker_padded_series(working)
    working["date"] = pd.to_datetime(working["date"], errors="coerce")
    working = working[working["date"].notna()]
    if working.empty:
        return pd.DataFrame()

    working = working.sort_values(["ticker", "date"])
    recent = working.groupby("ticker", sort=False).tail(5)
    scored = recent.groupby("ticker", sort=False).agg(
        window_count=("ticker", "size"),
        foreign_net_buy_5d=("foreign_buy", "sum"),
        institutional_net_buy_5d=("inst_buy", "sum"),
        consecutive=("foreign_buy", lambda series: count_consecutive_positive(series.to_numpy())),
    )
    scored = scored.reset_index()

    scored = scored[scored["window_count"] >= 5].copy()
    if scored.empty:
        return scored

    foreign_5d = scored["foreign_net_buy_5d"]
    inst_5d = scored["institutional_net_buy_5d"]

    score = np.zeros(len(scored), dtype=int)
    score += np.select(
        [foreign_5d > 1_000_000_000, foreign_5d > 500_000_000, foreign_5d > 0],
        [40, 25, 10],
        default=0,
    )
    score += np.select(
        [inst_5d > 500_000_000, inst_5d > 200_000_000, inst_5d > 0],
        [30, 20, 10],
        default=0,
    )
    score += np.minimum(scored["consecutive"].fillna(0).astype(int) * 6, 30)

    scored["supply_demand_index"] = score
    return scored[
        (scored["foreign_net_buy_5d"] >= foreign_min)
        & (scored["supply_demand_index"] >= 40)
    ][["ticker", "foreign_net_buy_5d", "institutional_net_buy_5d", "supply_demand_index"]]
