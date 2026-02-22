#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Screener Runtime Helpers

스크리닝 런타임 정렬/입력 정규화 로직을 분리한다.
"""

from __future__ import annotations

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


def prioritize_stocks_by_supply(
    stocks_df: pd.DataFrame,
    inst_df: pd.DataFrame | None,
    target_date: str | None,
    logger: Any,
) -> pd.DataFrame:
    """
    최근 5일 수급 합계 기준으로 종목 우선순위를 정렬한다.
    수급 정보가 없으면 입력 순서를 유지한다.
    """
    if stocks_df is None or stocks_df.empty:
        return stocks_df

    sorted_stocks = stocks_df.copy()
    sorted_stocks["ticker"] = _get_ticker_padded_series(sorted_stocks)

    if inst_df is None or inst_df.empty:
        return sorted_stocks

    inst_copy = inst_df.copy()
    if "ticker" in inst_copy.columns:
        inst_copy["ticker"] = _get_ticker_padded_series(inst_copy)
    if target_date:
        try:
            target_dt = pd.to_datetime(target_date)
            inst_copy = inst_copy[inst_copy["date"] <= target_dt]
        except Exception:
            pass

    if "date" in inst_copy.columns and not inst_copy["date"].is_monotonic_increasing:
        inst_copy = inst_copy.sort_values("date")

    f_col = "foreign_buy" if "foreign_buy" in inst_copy.columns else "foreign_net_buy"
    i_col = "inst_buy" if "inst_buy" in inst_copy.columns else "inst_net_buy"
    if f_col not in inst_copy.columns or i_col not in inst_copy.columns:
        return sorted_stocks

    recent_supply = (
        inst_copy.groupby("ticker")
        .tail(5)
        .groupby("ticker")
        .agg({f_col: "sum", i_col: "sum"})
        .reset_index()
    )
    recent_supply["total_supply"] = recent_supply[f_col] + recent_supply[i_col]
    recent_supply = recent_supply.sort_values("total_supply", ascending=False)
    top_tickers = recent_supply["ticker"].tolist()

    supply_order = {ticker: idx for idx, ticker in enumerate(top_tickers)}
    sorted_stocks["supply_rank"] = sorted_stocks["ticker"].map(supply_order).fillna(999999)
    sorted_stocks = sorted_stocks.sort_values("supply_rank").drop(columns=["supply_rank"])
    logger.info(f"[Screener] 수급 우선 정렬 완료: 상위 종목 {len(top_tickers)}개")
    return sorted_stocks


def build_stock_candidate(stock_row: Any) -> dict[str, str]:
    """itertuples row를 스크리너 입력 dict로 정규화한다."""
    return {
        "ticker": str(getattr(stock_row, "ticker", "")).zfill(6),
        "name": getattr(stock_row, "name", ""),
        "market": getattr(stock_row, "market", "UNKNOWN"),
    }


__all__ = ["prioritize_stocks_by_supply", "build_stock_candidate"]
