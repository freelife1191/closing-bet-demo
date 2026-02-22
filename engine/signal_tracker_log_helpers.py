#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Signal Tracker 로그/성과 업데이트 헬퍼.
"""

from __future__ import annotations

import os
from datetime import datetime

import numpy as np
import pandas as pd


def _get_ticker_padded_series(df: pd.DataFrame) -> pd.Series:
    if "ticker" not in df.columns:
        return pd.Series(dtype=object)
    if "_ticker_padded" in df.columns:
        return df["_ticker_padded"]

    padded = df["ticker"].astype(str).str.zfill(6)
    try:
        df["_ticker_padded"] = padded
        return df["_ticker_padded"]
    except Exception:
        return padded


def _normalize_price_map_keys(latest_price_map: dict[str, float]) -> dict[str, float]:
    normalized: dict[str, float] = {}
    for ticker, value in latest_price_map.items():
        ticker_key = str(ticker).zfill(6)
        try:
            normalized[ticker_key] = float(value or 0)
        except (TypeError, ValueError):
            normalized[ticker_key] = 0.0
    return normalized


def normalize_new_signals_for_log(new_signals: pd.DataFrame) -> pd.DataFrame:
    """시그널 로그 추가 전 ticker 포맷을 정규화한다."""
    if not new_signals.empty and "ticker" in new_signals.columns:
        working_new = new_signals.copy()
        working_new["ticker"] = _get_ticker_padded_series(working_new)
        if "_ticker_padded" in working_new.columns:
            working_new = working_new.drop(columns=["_ticker_padded"])
        return working_new
    return new_signals


def append_signals_log(
    *,
    signals_log_path: str,
    new_signals: pd.DataFrame,
    today: str,
    existing_signals: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """오늘 동일 티커 중복을 제거하고 로그를 병합한다."""
    working_new = normalize_new_signals_for_log(new_signals)

    if existing_signals is not None:
        existing = existing_signals.copy()
    else:
        if not os.path.exists(signals_log_path):
            return working_new
        existing = pd.read_csv(
            signals_log_path,
            encoding="utf-8-sig",
            dtype={"ticker": str},
            low_memory=False,
        )
    if existing.empty:
        return working_new

    if "ticker" in existing.columns:
        existing["ticker"] = _get_ticker_padded_series(existing)
    if "signal_date" in existing.columns and "ticker" in existing.columns and "ticker" in working_new.columns:
        existing = existing[
            ~((existing["signal_date"] == today) & (existing["ticker"].isin(working_new["ticker"])))
        ]

    return pd.concat([existing, working_new], ignore_index=True)


def update_open_signals_frame(
    *,
    df: pd.DataFrame,
    latest_price_map: dict[str, float],
    stop_loss_pct: float,
    hold_days_limit: int,
    now: datetime,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """OPEN 시그널을 벡터화 방식으로 업데이트하고 청산 로그용 프레임을 반환한다."""
    if df.empty or "status" not in df.columns or "ticker" not in df.columns:
        return df, pd.DataFrame(columns=["ticker", "close_reason", "return_pct"])

    working = df.copy()
    working["ticker"] = _get_ticker_padded_series(working)
    normalized_price_map = _normalize_price_map_keys(latest_price_map)
    if "exit_date" in working.columns:
        working["exit_date"] = working["exit_date"].astype(object)

    open_mask = working["status"] == "OPEN"
    if not open_mask.any():
        return working, pd.DataFrame(columns=["ticker", "close_reason", "return_pct"])

    open_view = working.loc[open_mask, ["ticker", "entry_price", "signal_date"]].copy()
    open_view["current_price"] = (
        open_view["ticker"].map(normalized_price_map).pipe(pd.to_numeric, errors="coerce").fillna(0.0)
    )
    open_view["valid_current"] = open_view["current_price"] > 0

    open_view["entry_price_num"] = pd.to_numeric(open_view["entry_price"], errors="coerce").fillna(0.0)
    open_view["return_pct"] = np.where(
        open_view["entry_price_num"] > 0,
        (open_view["current_price"] - open_view["entry_price_num"]) / open_view["entry_price_num"] * 100,
        0.0,
    )

    signal_dates = pd.to_datetime(open_view["signal_date"], errors="coerce")
    open_view["hold_days"] = (now - signal_dates).dt.days.fillna(0).astype(int)
    open_view["close_stop"] = open_view["return_pct"] <= -float(stop_loss_pct)
    open_view["close_time"] = open_view["hold_days"] >= int(hold_days_limit)
    open_view["should_close"] = open_view["valid_current"] & (open_view["close_stop"] | open_view["close_time"])
    open_view["close_reason"] = np.where(open_view["close_stop"], "STOP_LOSS", "TIME_EXIT")

    valid_view = open_view[open_view["valid_current"]]
    if not valid_view.empty:
        working.loc[valid_view.index, "current_price"] = valid_view["current_price"].round(0).to_numpy()
        working.loc[valid_view.index, "return_pct"] = valid_view["return_pct"].round(2).to_numpy()

    closing_view = open_view[open_view["should_close"]]
    if not closing_view.empty:
        now_str = now.strftime("%Y-%m-%d")
        working.loc[closing_view.index, "status"] = "CLOSED"
        working.loc[closing_view.index, "exit_price"] = closing_view["current_price"].round(0).to_numpy()
        working.loc[closing_view.index, "exit_date"] = now_str
        working.loc[closing_view.index, "return_pct"] = closing_view["return_pct"].round(2).to_numpy()
        working.loc[closing_view.index, "hold_days"] = closing_view["hold_days"].astype(int).to_numpy()

    if "_ticker_padded" in working.columns:
        working = working.drop(columns=["_ticker_padded"])
    return working, closing_view[["ticker", "close_reason", "return_pct"]].copy()
