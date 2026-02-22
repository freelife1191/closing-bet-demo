#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Engine - Toss Collector Price Parsers
"""

from __future__ import annotations

from typing import Any

from engine.toss_collector_numeric_helpers import (
    compute_change,
    compute_change_pct,
    normalize_result_payload,
    normalize_ticker_code,
)


def _build_price_payload(item: dict[str, Any]) -> dict[str, Any]:
    close = item.get("close", 0)
    base = item.get("base", 0)
    return {
        "current": close,
        "prev_close": base,
        "open": item.get("open", 0),
        "high": item.get("high", 0),
        "low": item.get("low", 0),
        "volume": item.get("volume", 0),
        "trading_value": item.get("value", 0),
        "high_52w": item.get("high52w", 0),
        "low_52w": item.get("low52w", 0),
        "market_cap": item.get("marketCap", 0),
        "upper_limit": item.get("upperLimit", 0),
        "lower_limit": item.get("lowerLimit", 0),
        "change": compute_change(close, base),
        "change_pct": compute_change_pct(close, base),
    }


def parse_stock_info(code: str, data: dict[str, Any] | None) -> dict[str, Any] | None:
    if not data:
        return None

    result = normalize_result_payload(data)
    if not isinstance(result, dict):
        return None

    market_info = result.get("market", {})
    if not isinstance(market_info, dict):
        market_info = {}

    return {
        "code": code,
        "name": result.get("name", ""),
        "market": market_info.get("displayName", "UNKNOWN"),
        "market_code": market_info.get("code", ""),
        "sector": result.get("sector", ""),
        "logo_url": result.get("logoImageUrl", ""),
    }


def parse_price_details(data: dict[str, Any] | None) -> dict[str, Any] | None:
    if not data:
        return None

    result_obj = normalize_result_payload(data)
    price_data: dict[str, Any]

    if isinstance(result_obj, list):
        if not result_obj:
            return None
        first = result_obj[0]
        if not isinstance(first, dict):
            return None
        price_data = first
    elif isinstance(result_obj, dict):
        price_data = result_obj
    else:
        return None

    return _build_price_payload(price_data)


def parse_prices_batch(data: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    if not data:
        return {}

    result_obj = normalize_result_payload(data)
    if isinstance(result_obj, list):
        items = result_obj
    elif isinstance(result_obj, dict):
        items = [result_obj]
    else:
        return {}

    results: dict[str, dict[str, Any]] = {}
    for item in items:
        if not isinstance(item, dict):
            continue

        code = normalize_ticker_code(item.get("code", ""))
        if not code:
            continue

        close = item.get("close", 0)
        base = item.get("base", 0)
        results[code] = {
            "current": close,
            "open": item.get("open", 0),
            "high": item.get("high", 0),
            "low": item.get("low", 0),
            "volume": item.get("volume", 0),
            "trading_value": item.get("value", 0),
            "market_cap": item.get("marketCap", 0),
            "change": compute_change(close, base),
            "change_pct": compute_change_pct(close, base),
        }

    return results

