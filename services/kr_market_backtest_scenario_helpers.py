#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KR Market Backtest - Scenario Helpers
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from services.kr_market_backtest_common import safe_float


def _get_ticker_padded_series(df: pd.DataFrame) -> pd.Series:
    if "_ticker_padded" in df.columns:
        return df["_ticker_padded"]

    padded = df["ticker"].astype(str).str.zfill(6)
    try:
        df["_ticker_padded"] = padded
        return df["_ticker_padded"]
    except Exception:
        return padded


def _filter_subset_after_signal_date(
    subset: pd.DataFrame,
    signal_date: Any,
) -> pd.DataFrame | None:
    """시그널 이후 데이터만 추출한다.

    반환값이 None이면 기존 규칙대로 raw 수익률로 폴백해야 한다.
    """
    if "date" in subset.columns:
        try:
            filtered = subset[subset["date"] > signal_date]
        except (TypeError, ValueError):
            return None

        if not filtered.empty and not filtered["date"].is_monotonic_increasing:
            filtered = filtered.sort_values("date")
        return filtered

    try:
        signal_ts = pd.Timestamp(signal_date)
        return subset[subset.index > signal_ts]
    except (TypeError, ValueError):
        return subset


def build_latest_price_map(price_df: Any) -> dict[str, float]:
    """가격 DataFrame에서 ticker별 최신 종가 맵을 생성한다."""
    if not isinstance(price_df, pd.DataFrame) or price_df.empty:
        return {}
    if not {"ticker", "close"}.issubset(set(price_df.columns)):
        return {}

    df = price_df.copy()
    df["ticker"] = _get_ticker_padded_series(df)
    if "date" in df.columns and not df["date"].is_monotonic_increasing:
        df = df.sort_values("date")

    df["close"] = pd.to_numeric(df["close"], errors="coerce")
    latest_prices = df.groupby("ticker", sort=False).tail(1).copy()
    latest_prices = latest_prices[latest_prices["close"].notna()]
    return latest_prices.set_index("ticker")["close"].to_dict()


def inject_latest_prices_to_candidates(
    candidates: list[dict[str, Any]],
    price_map: dict[str, float],
) -> None:
    """종가베팅 후보군에 최신가/수익률을 반영한다."""
    if not isinstance(candidates, list) or not isinstance(price_map, dict):
        return

    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        code = str(
            candidate.get("stock_code")
            or candidate.get("code")
            or candidate.get("ticker")
            or ""
        ).zfill(6)
        if code not in price_map:
            continue

        current_price = safe_float(price_map.get(code), default=0.0)
        if current_price <= 0:
            continue
        candidate["current_price"] = current_price

        entry = safe_float(candidate.get("entry_price") or candidate.get("close"), default=0.0)
        if entry > 0:
            candidate["return_pct"] = round(((current_price - entry) / entry) * 100, 2)


def _calculate_raw_return(entry_price: float, current_price: float) -> float:
    entry = safe_float(entry_price, default=0.0)
    current = safe_float(current_price, default=0.0)
    if entry <= 0:
        return 0.0
    return ((current - entry) / entry) * 100


def calculate_scenario_return(
    ticker: str,
    entry_price: float,
    signal_date: Any,
    current_price: float,
    price_df: Any,
    target_pct: float = 0.15,
    stop_pct: float = 0.05,
    stock_prices: Any = None,
) -> float:
    """
    백테스트 시나리오 수익률 계산.
    - 익절: +target_pct
    - 손절: -stop_pct
    - 미충족: 현재가 기준
    """
    entry = safe_float(entry_price, default=0.0)
    current = safe_float(current_price, default=0.0)
    if entry <= 0:
        return 0.0

    if not isinstance(price_df, pd.DataFrame) or price_df.empty:
        return _calculate_raw_return(entry, current)

    if "high" not in price_df.columns or "low" not in price_df.columns:
        ret = _calculate_raw_return(entry, current)
        if ret > (target_pct * 100):
            return target_pct * 100
        if ret < -(stop_pct * 100):
            return -(stop_pct * 100)
        return ret

    if isinstance(stock_prices, pd.DataFrame):
        subset_source = stock_prices
    elif "date" in price_df.columns:
        subset_source = price_df[price_df["ticker"] == ticker]
    else:
        subset_source = price_df[(price_df["ticker"] == ticker)].sort_index()

    subset = _filter_subset_after_signal_date(subset_source, signal_date)
    if subset is None:
        return _calculate_raw_return(entry, current)

    if subset is None or subset.empty:
        return _calculate_raw_return(entry, current)

    lows = pd.to_numeric(subset.get("low"), errors="coerce").to_numpy()
    highs = pd.to_numeric(subset.get("high"), errors="coerce").to_numpy()

    if lows.size == 0 or highs.size == 0:
        return _calculate_raw_return(entry, current)

    stop_price = entry * (1 - stop_pct)
    target_price = entry * (1 + target_pct)
    low_hits = np.flatnonzero(lows <= stop_price)
    high_hits = np.flatnonzero(highs >= target_price)

    # 기존 규칙 유지: 같은 날짜에 동시 충족 시 손절 우선.
    first_low = int(low_hits[0]) if low_hits.size > 0 else None
    first_high = int(high_hits[0]) if high_hits.size > 0 else None

    if first_low is not None and first_high is not None:
        if first_low <= first_high:
            return -(stop_pct * 100)
        return target_pct * 100
    if first_low is not None:
        return -(stop_pct * 100)
    if first_high is not None:
        return target_pct * 100

    return _calculate_raw_return(entry, current)
