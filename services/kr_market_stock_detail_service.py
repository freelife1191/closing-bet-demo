#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KR Market Stock Detail Service

종목 상세 조회 로직 분리.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable

import pandas as pd

from services.kr_market_csv_utils import (
    get_ticker_padded_series as _get_padded_ticker_series,
    load_csv_readonly as _load_csv_readonly,
)
from services.kr_market_realtime_price_service import normalize_ticker


def to_market_code(market_value: str | None) -> str:
    if market_value == "코스피":
        return "KOSPI"
    if market_value == "코스닥":
        return "KOSDAQ"
    return market_value or "UNKNOWN"



def build_default_stock_detail_payload(ticker_padded: str) -> dict[str, Any]:
    return {
        "code": ticker_padded,
        "name": f"종목 {ticker_padded}",
        "market": "UNKNOWN",
        "priceInfo": {"current": 0, "prevClose": 0, "high": 0, "low": 0},
        "yearRange": {"high_52w": 0, "low_52w": 0},
        "indicators": {"marketCap": 0, "per": 0, "pbr": 0},
        "investorTrend": {"foreign": 0, "institution": 0, "individual": 0},
        "financials": {"revenue": 0, "operatingProfit": 0, "netIncome": 0},
        "safety": {"debtRatio": 0, "currentRatio": 0},
        "message": "NaverFinanceCollector를 사용할 수 없어 기본 데이터를 반환합니다.",
    }


def append_investor_trend_5day(
    payload: dict[str, Any],
    ticker_padded: str,
    load_csv_file: Callable[[str], pd.DataFrame],
    logger: logging.Logger,
) -> None:
    try:
        trend_df = _load_csv_readonly(
            load_csv_file,
            "all_institutional_trend_data.csv",
            usecols=["ticker", "foreign_buy", "inst_buy"],
        )
    except Exception as e:
        logger.warning(f"Failed to calculate 5-day trend for {ticker_padded}: {e}")
        return

    if trend_df.empty or "ticker" not in trend_df.columns:
        return
    if "foreign_buy" not in trend_df.columns or "inst_buy" not in trend_df.columns:
        return

    ticker_series = _get_padded_ticker_series(trend_df)
    filtered = trend_df[ticker_series == ticker_padded]
    if filtered.empty:
        return

    recent_5 = filtered.tail(5)
    payload["investorTrend5Day"] = {
        "foreign": int(recent_5["foreign_buy"].sum()),
        "institution": int(recent_5["inst_buy"].sum()),
    }


def build_toss_detail_payload(ticker_padded: str, toss_data: dict[str, Any]) -> dict[str, Any]:
    price = toss_data.get("price", {})
    indicators = toss_data.get("indicators", {})
    investor_trend = toss_data.get("investor_trend", {})
    financials = toss_data.get("financials", {})
    stability = toss_data.get("stability", {})

    prev_close = price.get("prev_close", 0) or 0
    current_price = price.get("current", 0) or 0
    change_pct = ((current_price - prev_close) / prev_close * 100) if prev_close else 0

    return {
        "code": ticker_padded,
        "name": toss_data.get("name", ""),
        "market": to_market_code(toss_data.get("market")),
        "priceInfo": {
            "current": current_price,
            "prevClose": prev_close,
            "open": price.get("open", 0),
            "high": price.get("high", 0),
            "low": price.get("low", 0),
            "change": current_price - prev_close,
            "change_pct": change_pct,
            "volume": price.get("volume", 0),
            "trading_value": price.get("trading_value", 0),
        },
        "yearRange": {"high_52w": price.get("high_52w", 0), "low_52w": price.get("low_52w", 0)},
        "indicators": {
            "marketCap": price.get("market_cap", 0),
            "per": indicators.get("per", 0),
            "pbr": indicators.get("pbr", 0),
            "eps": indicators.get("eps", 0),
            "bps": indicators.get("bps", 0),
            "dividendYield": indicators.get("dividend_yield", 0),
            "roe": indicators.get("roe", 0),
            "psr": indicators.get("psr", 0),
        },
        "investorTrend": {
            "foreign": investor_trend.get("foreign", 0),
            "institution": investor_trend.get("institution", 0),
            "individual": investor_trend.get("individual", 0),
        },
        "financials": {
            "revenue": financials.get("revenue", 0),
            "operatingProfit": financials.get("operating_profit", 0),
            "netIncome": financials.get("net_income", 0),
        },
        "safety": {
            "debtRatio": stability.get("debt_ratio", 0),
            "currentRatio": stability.get("current_ratio", 0),
        },
    }


def load_naver_stock_detail_payload(ticker_padded: str) -> dict[str, Any] | None:
    from engine.collectors import NaverFinanceCollector

    collector = NaverFinanceCollector()
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        detail_info = loop.run_until_complete(collector.get_stock_detail_info(ticker_padded))
        financials = loop.run_until_complete(collector.get_financials(ticker_padded))
    finally:
        asyncio.set_event_loop(None)
        loop.close()

    if not detail_info:
        return None
    detail_info["financials"] = financials
    return detail_info


def fetch_stock_detail_payload(
    ticker: str,
    load_csv_file: Callable[[str], pd.DataFrame],
    logger: logging.Logger,
) -> dict[str, Any]:
    """종목 상세 조회를 Toss -> Naver -> 기본값 순서로 수행한다."""
    ticker_padded = normalize_ticker(ticker)

    try:
        from engine.toss_collector import TossCollector

        toss_data = TossCollector().get_full_stock_detail(ticker_padded)
        if toss_data and toss_data.get("name"):
            payload = build_toss_detail_payload(ticker_padded, toss_data)
            append_investor_trend_5day(payload, ticker_padded, load_csv_file, logger)
            return payload
    except Exception as e:
        logger.warning(f"TossCollector 실패, NaverFinanceCollector로 폴백: {e}")

    try:
        naver_payload = load_naver_stock_detail_payload(ticker_padded)
        if naver_payload:
            return naver_payload
    except ImportError as e:
        logger.warning(f"NaverFinanceCollector import 실패: {e}")
        return build_default_stock_detail_payload(ticker_padded)
    except Exception as e:
        logger.warning(f"NaverFinanceCollector 조회 실패: {e}")

    return build_default_stock_detail_payload(ticker_padded)
