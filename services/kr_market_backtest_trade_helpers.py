#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KR Market Backtest - Trade/Cumulative Helpers
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import pandas as pd

from services.kr_market_backtest_common import format_signal_date, safe_float


def _get_ticker_padded_series(df: pd.DataFrame) -> pd.Series:
    if "_ticker_padded" in df.columns:
        return df["_ticker_padded"]

    padded = df["ticker"].astype(str).str.zfill(6)
    try:
        df["_ticker_padded"] = padded
        return df["_ticker_padded"]
    except Exception:
        return padded


def prepare_cumulative_price_dataframe(raw_price_df: Any) -> Any:
    """누적성과 계산용 가격 DataFrame을 정규화한다."""
    if not isinstance(raw_price_df, pd.DataFrame) or raw_price_df.empty:
        return pd.DataFrame()
    if "date" not in raw_price_df.columns or "ticker" not in raw_price_df.columns:
        return pd.DataFrame()

    df = raw_price_df.copy()
    df["ticker"] = _get_ticker_padded_series(df)
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df[df["date"].notna()]

    for col in ["open", "high", "low", "close"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    if not df["date"].is_monotonic_increasing:
        df = df.sort_values("date")
    df.set_index("date", inplace=True)
    return df


def build_ticker_price_index(price_df: Any) -> dict[str, pd.DataFrame]:
    """ticker별 시계열 DataFrame 인덱스를 생성한다."""
    if not isinstance(price_df, pd.DataFrame) or price_df.empty:
        return {}
    if "ticker" not in price_df.columns:
        return {}

    normalized_df = price_df.copy()
    normalized_df["ticker"] = _get_ticker_padded_series(normalized_df)

    if "date" in normalized_df.columns:
        sorted_df = normalized_df
        if not normalized_df["date"].is_monotonic_increasing:
            sorted_df = normalized_df.sort_values(["ticker", "date"])
        return {
            str(ticker): group
            for ticker, group in sorted_df.groupby("ticker", sort=False)
            if isinstance(group, pd.DataFrame) and not group.empty
        }

    indexed: dict[str, pd.DataFrame] = {}
    for ticker, group in normalized_df.groupby("ticker", sort=False):
        if not isinstance(group, pd.DataFrame) or group.empty:
            continue
        indexed[str(ticker)] = group.sort_index()
    return indexed


def extract_stats_date_from_results_filename(filepath: str, fallback_date: Any = "") -> str:
    """파일명에서 통계 기준일(YYYY-MM-DD)을 추출한다."""
    filename = str(filepath).split("/")[-1]
    file_date_str = filename.split("_")[-1].replace(".json", "")
    try:
        return datetime.strptime(file_date_str, "%Y%m%d").strftime("%Y-%m-%d")
    except Exception:
        return format_signal_date(fallback_date)


def calculate_cumulative_trade_metrics(
    entry_price: float,
    stats_date: str,
    stock_prices: Any,
) -> dict[str, Any]:
    """종가베팅 1건의 Outcome/ROI/Trail/기간/최대상승률을 계산한다."""
    outcome = "OPEN"
    roi = 0.0
    max_high = 0.0
    days = 0
    price_trail: list[float] = []

    if not isinstance(stock_prices, pd.DataFrame) or stock_prices.empty:
        return {
            "outcome": outcome,
            "roi": roi,
            "max_high": max_high,
            "days": days,
            "price_trail": price_trail,
        }

    try:
        signal_ts = pd.Timestamp(stats_date)
    except Exception:
        signal_ts = None

    if signal_ts is None:
        return {
            "outcome": outcome,
            "roi": roi,
            "max_high": max_high,
            "days": days,
            "price_trail": price_trail,
        }

    period_prices = stock_prices[stock_prices.index > signal_ts]
    required_cols = {"high", "low", "close"}
    has_required_cols = required_cols.issubset(set(period_prices.columns))
    if has_required_cols:
        period_prices = period_prices[
            (period_prices["high"] > 0)
            & (period_prices["low"] > 0)
            & (period_prices["close"] > 0)
        ]

    target_price = entry_price * 1.09
    stop_price = entry_price * 0.95

    exit_date = None
    if has_required_cols:
        hit_target = period_prices[period_prices["high"] >= target_price]
        hit_stop = period_prices[period_prices["low"] <= stop_price]
        first_win_date = hit_target.index[0] if not hit_target.empty else None
        first_loss_date = hit_stop.index[0] if not hit_stop.empty else None

        if first_win_date is not None and first_loss_date is not None:
            if first_win_date <= first_loss_date:
                outcome = "WIN"
                roi = 9.0
                exit_date = first_win_date
            else:
                outcome = "LOSS"
                roi = -5.0
                exit_date = first_loss_date
        elif first_win_date is not None:
            outcome = "WIN"
            roi = 9.0
            exit_date = first_win_date
        elif first_loss_date is not None:
            outcome = "LOSS"
            roi = -5.0
            exit_date = first_loss_date

    trade_period = period_prices[period_prices.index <= exit_date] if exit_date is not None else period_prices

    price_trail = [entry_price]
    if "close" in trade_period.columns and not trade_period.empty:
        closes = [float(v) for v in trade_period["close"].tolist() if pd.notna(v)]
        price_trail.extend(closes)
        if len(price_trail) > 1:
            if outcome == "WIN":
                price_trail[-1] = target_price
            elif outcome == "LOSS":
                price_trail[-1] = stop_price

    days = len(trade_period)

    if "high" in trade_period.columns and not trade_period.empty:
        high_price = trade_period["high"].max()
        if pd.notna(high_price) and high_price > 0:
            max_high = round(((high_price - entry_price) / entry_price) * 100, 1)

    if outcome == "OPEN" and price_trail and roi == 0.0:
        last_price = price_trail[-1]
        roi = round(((last_price - entry_price) / entry_price) * 100, 1)

    return {
        "outcome": outcome,
        "roi": roi,
        "max_high": max_high,
        "days": days,
        "price_trail": price_trail,
    }


def build_cumulative_trade_record(
    signal: dict[str, Any],
    stats_date: str,
    price_df: Any,
    price_index: dict[str, pd.DataFrame] | None = None,
) -> dict[str, Any] | None:
    """종가베팅 시그널에서 누적성과 trade 레코드 1건을 생성한다."""
    if not isinstance(signal, dict):
        return None

    ticker = str(signal.get("ticker", signal.get("stock_code", ""))).zfill(6)
    if not ticker or ticker == "000000":
        return None

    entry_price = safe_float(signal.get("entry_price", 0), default=0.0)
    if entry_price <= 0:
        return None

    metrics: dict[str, Any] = {
        "outcome": "OPEN",
        "roi": 0.0,
        "max_high": 0.0,
        "days": 0,
        "price_trail": [],
    }

    if isinstance(price_index, dict):
        stock_prices = price_index.get(ticker)
        if isinstance(stock_prices, pd.DataFrame) and not stock_prices.empty:
            metrics = calculate_cumulative_trade_metrics(entry_price, stats_date, stock_prices)
    elif isinstance(price_df, pd.DataFrame) and not price_df.empty and "ticker" in price_df.columns:
        stock_prices = price_df[price_df["ticker"] == ticker]
        metrics = calculate_cumulative_trade_metrics(entry_price, stats_date, stock_prices)

    score = signal.get("score", {})
    score_value = score.get("total", 0) if isinstance(score, dict) else 0

    return {
        "id": f"{ticker}-{stats_date}",
        "date": stats_date,
        "grade": signal.get("grade"),
        "name": signal.get("name", signal.get("stock_name", "")),
        "code": ticker,
        "market": signal.get("market", ""),
        "entry": entry_price,
        "outcome": metrics["outcome"],
        "roi": metrics["roi"],
        "maxHigh": metrics["max_high"],
        "priceTrail": metrics["price_trail"],
        "days": metrics["days"],
        "score": score_value,
        "themes": signal.get("themes", []),
    }
