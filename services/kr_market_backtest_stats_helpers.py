#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KR Market Backtest - Stats Helpers
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from services.kr_market_backtest_common import (
    JONGGA_STOP_PCT,
    JONGGA_TARGET_PCT,
    determine_backtest_status,
    pct_to_percent,
    safe_float,
)
from services.kr_market_backtest_cumulative import build_ticker_price_index
from services.kr_market_backtest_scenario_helpers import (
    calculate_scenario_return,
    inject_latest_prices_to_candidates,
)


def calculate_jongga_backtest_stats(
    candidates: list[dict[str, Any]],
    history_payloads: list[dict[str, Any]],
    price_map: dict[str, float],
    price_df: Any,
    *,
    price_index: dict[str, pd.DataFrame] | None = None,
) -> dict[str, Any]:
    """종가베팅 백테스트 요약 통계를 계산한다."""
    stats: dict[str, Any] = {
        "status": "Accumulating",
        "count": 0,
        "win_rate": 0,
        "avg_return": 0,
        "candidates": candidates if isinstance(candidates, list) else [],
    }

    total_signals = 0
    wins = 0
    losses = 0
    total_return = 0.0

    resolved_price_index = price_index or build_ticker_price_index(price_df)

    for payload in history_payloads:
        if not isinstance(payload, dict):
            continue
        signals = payload.get("signals", [])
        signal_date = payload.get("date", "")
        if not isinstance(signals, list):
            continue

        for signal in signals:
            if not isinstance(signal, dict):
                continue
            code = str(
                signal.get("stock_code")
                or signal.get("code")
                or signal.get("ticker")
                or ""
            ).zfill(6)
            if not code or code == "000000":
                continue

            entry = safe_float(
                signal.get("entry_price") or signal.get("close") or signal.get("current_price"),
                default=0.0,
            )
            if entry <= 0:
                continue

            current_price = safe_float(price_map.get(code), default=0.0)
            if current_price <= 0:
                continue

            ret = calculate_scenario_return(
                code,
                entry,
                signal_date,
                current_price,
                price_df,
                target_pct=JONGGA_TARGET_PCT,
                stop_pct=JONGGA_STOP_PCT,
                stock_prices=resolved_price_index.get(code),
            )
            total_signals += 1
            total_return += ret
            if ret >= pct_to_percent(JONGGA_TARGET_PCT):
                wins += 1
            elif ret <= -pct_to_percent(JONGGA_STOP_PCT):
                losses += 1

    if total_signals > 0:
        stats["count"] = total_signals
        closed_trades = wins + losses
        win_rate = round((wins / closed_trades) * 100, 1) if closed_trades > 0 else 0.0
        stats["win_rate"] = win_rate
        stats["avg_return"] = round(total_return / total_signals, 1)
        stats["status"] = determine_backtest_status(win_rate, closed_trades)
    elif stats["candidates"]:
        stats["status"] = "OK (New)"

    inject_latest_prices_to_candidates(stats["candidates"], price_map)
    return stats


def calculate_vcp_backtest_stats(
    vcp_df: Any,
    price_map: dict[str, float],
    price_df: Any,
    *,
    price_index: dict[str, pd.DataFrame] | None = None,
) -> dict[str, Any]:
    """VCP 백테스트 요약 통계를 계산한다."""
    stats: dict[str, Any] = {
        "status": "Accumulating",
        "count": 0,
        "win_rate": 0,
        "avg_return": 0,
    }

    if not isinstance(vcp_df, pd.DataFrame) or vcp_df.empty:
        return stats

    # 행은 있으나 아직 한 건도 집계하지 못한 상태다. 종가베팅 쪽이 후보만 있을 때
    # 쓰는 값과 같은 뜻이므로 어휘를 맞춘다. 아래에서 거래를 세면 덮어쓴다.
    stats["status"] = "OK (New)"

    total_count = 0
    wins = 0
    losses = 0
    total_return = 0.0

    resolved_price_index = price_index or build_ticker_price_index(price_df)

    for row in vcp_df.itertuples(index=False):
        ticker = str(getattr(row, "ticker", "")).zfill(6)
        entry_price = safe_float(getattr(row, "entry_price", 0), default=0.0)
        signal_date = str(getattr(row, "signal_date", ""))
        if entry_price <= 0 or not signal_date:
            continue

        current_price = safe_float(price_map.get(ticker), default=0.0)
        if current_price <= 0:
            continue

        sim_ret = calculate_scenario_return(
            ticker,
            entry_price,
            signal_date,
            current_price,
            price_df,
            target_pct=0.15,
            stop_pct=0.05,
            stock_prices=resolved_price_index.get(ticker),
        )
        total_count += 1
        total_return += sim_ret
        if sim_ret >= 15.0:
            wins += 1
        elif sim_ret <= -5.0:
            losses += 1

    if total_count > 0:
        stats["count"] = total_count
        closed_count = wins + losses
        win_rate = round((wins / closed_count) * 100, 1) if closed_count > 0 else 0.0
        stats["win_rate"] = win_rate
        stats["avg_return"] = round(total_return / total_count, 1)
        stats["status"] = determine_backtest_status(win_rate, closed_count)

    return stats
