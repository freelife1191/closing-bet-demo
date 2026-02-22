#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Engine - Market Gate Analysis Runtime

MarketGate.analyze 본문을 분리해 MarketGate 클래스를 오케스트레이터화한다.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from engine.market_gate_logic import (
    build_gate_reason as build_gate_reason_impl,
    build_market_status as build_market_status_impl,
    build_sector_signals as build_sector_signals_impl,
)


def _to_date_text(value: Any) -> str:
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d")
    return str(value)[:10]


def analyze_market_state(market_gate: Any, target_date: str | None, logger: logging.Logger) -> dict[str, Any]:
    """MarketGate 인스턴스 의존성을 이용해 시장 상태 분석을 수행한다."""
    try:
        df = market_gate._load_price_data(target_date)
        if df.empty:
            return market_gate._default_result("가격 데이터 부족")

        start_dt = _to_date_text(df.iloc[0]["date"])
        end_dt = _to_date_text(df.iloc[-1]["date"])
        bench_df = market_gate._fetch_benchmark_data(start_dt, end_dt)

        df = market_gate._calculate_indicators(df, bench_df)
        current_tech = df.iloc[-1]

        usd_krw = market_gate._get_usd_krw()

        score_trend = market_gate._score_trend(current_tech)
        score_rsi = market_gate._score_rsi(current_tech)
        score_macd = market_gate._score_macd(current_tech)
        score_vol = market_gate._score_volume(current_tech)
        score_rs = market_gate._score_rs(current_tech)

        tech_score = score_trend + score_rsi + score_macd + score_vol + score_rs
        total_score = min(tech_score, 100)

        _, macro_status = market_gate._score_macro(usd_krw)

        is_open = total_score >= 40
        gate_reason = build_gate_reason_impl(total_score, macro_status)
        status, label, color = build_market_status_impl(total_score)

        global_data = market_gate._get_global_data(target_date)
        sector_data = market_gate._get_sector_data(target_date, global_data=global_data)

        real_kospi = global_data.get("indices", {}).get("kospi", {})
        kospi_close = real_kospi.get("value", float(current_tech["close"]))
        kospi_change = real_kospi.get("change_pct", float(current_tech["change_pct"]))

        return {
            "timestamp": datetime.now().isoformat(),
            "kospi_close": kospi_close,
            "kospi_change": kospi_change,
            "kosdaq_close": global_data.get("indices", {}).get("kosdaq", {}).get("value", 0),
            "kosdaq_change_pct": global_data.get("indices", {}).get("kosdaq", {}).get("change_pct", 0),
            "usd_krw": usd_krw,
            "total_score": total_score,
            "label": label,
            "is_gate_open": is_open,
            "gate_reason": gate_reason,
            "status": status,
            "color": color,
            "dataset_date": str(current_tech["date"]),
            "details": {
                "tech_score": int(total_score),
                "rs_score": score_rs,
                "trend_score": score_trend,
                "rsi_score": score_rsi,
                "macd_score": score_macd,
                "vol_score": score_vol,
                "rsi_val": round(float(current_tech["rsi"]), 2),
                "macd_val": round(float(current_tech["macd"]), 2),
                "ma20": float(current_tech["ma20"]),
                "ma60": float(current_tech["ma60"]),
                "macro_status": macro_status,
            },
            "indices": global_data.get("indices", {}),
            "commodities": global_data.get("commodities", {}),
            "crypto": global_data.get("crypto", {}),
            "sectors": build_sector_signals_impl(sector_data),
        }
    except Exception as error:
        logger.error(f"Market Gate 분석 실패: {error}")
        return market_gate._default_result(str(error))
