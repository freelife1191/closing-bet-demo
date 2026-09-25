#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KR Market Stock Detail Service

종목 상세 조회 로직 분리.
"""

from __future__ import annotations

import asyncio
import copy
import logging
import os
import threading
from collections import OrderedDict
from datetime import datetime
from typing import Any

from engine.investor_personal_flow import cached_personal_value
from services.kr_market_data_cache_sqlite_payload import (
    load_json_payload_from_sqlite as _load_json_payload_from_sqlite,
    save_json_payload_to_sqlite as _save_json_payload_to_sqlite,
)
from services.investor_trend_5day_service import get_investor_trend_5day_for_ticker
from services.kr_market_realtime_price_service import normalize_ticker


_STOCK_DETAIL_CACHE_LOCK = threading.Lock()
_STOCK_DETAIL_CACHE: OrderedDict[
    tuple[str, str, str],
    dict[str, Any],
] = OrderedDict()
_STOCK_DETAIL_CACHE_MAX_ENTRIES = 256
_STOCK_DETAIL_SQLITE_MAX_ROWS = 4_096
_STOCK_DETAIL_SQLITE_CACHE_SCHEMA_VERSION = "stock_detail_v1"
_STOCK_DETAIL_SQLITE_CACHE_INTERVAL_MINUTES = 15


def _resolve_data_dir_path(data_dir: str | None = None) -> str:
    if isinstance(data_dir, str) and data_dir.strip():
        return os.path.abspath(data_dir.strip())
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_dir, "data")


def _stable_token_to_int(token: str) -> int:
    normalized = str(token or "")
    if normalized.isdigit():
        try:
            return int(normalized)
        except Exception:
            pass
    acc = 17
    for char in normalized:
        acc = (acc * 31 + ord(char)) % 2_000_000_000
    return int(acc)


def _current_stock_detail_cache_slot(now: datetime | None = None) -> str:
    resolved_now = now or datetime.now()
    interval_minutes = max(1, int(_STOCK_DETAIL_SQLITE_CACHE_INTERVAL_MINUTES))
    bucket = (resolved_now.hour * 60 + resolved_now.minute) // interval_minutes
    return f"{resolved_now.strftime('%Y%m%d')}:{bucket:02d}"


def _stock_detail_sqlite_context(
    *,
    ticker_padded: str,
    cache_slot: str,
    data_dir: str | None,
) -> tuple[str, tuple[int, int], str]:
    resolved_data_dir = _resolve_data_dir_path(data_dir)
    ticker_key = str(ticker_padded).zfill(6)
    slot_key = str(cache_slot or "latest")
    sqlite_key = os.path.join(
        resolved_data_dir,
        ".kr_stock_detail_cache",
        f"{ticker_key}__{slot_key}.snapshot",
    )
    signature_seed = f"{ticker_key}:{slot_key}:{_STOCK_DETAIL_SQLITE_CACHE_SCHEMA_VERSION}"
    signature = (
        _stable_token_to_int(signature_seed),
        _stable_token_to_int(f"stock_detail::{signature_seed[::-1]}"),
    )
    return sqlite_key, signature, resolved_data_dir


def _normalize_stock_detail_payload(payload: Any) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return None
    normalized = copy.deepcopy(payload)
    if not isinstance(normalized.get("code"), str):
        return None
    trend = normalized.get("investorTrend")
    if isinstance(trend, dict):
        trend["individual"] = cached_personal_value(trend, "individual")
    return normalized


def _load_cached_stock_detail_payload(
    *,
    ticker_padded: str,
    cache_slot: str,
    data_dir: str | None,
    logger: logging.Logger,
) -> dict[str, Any] | None:
    sqlite_key, signature, resolved_data_dir = _stock_detail_sqlite_context(
        ticker_padded=ticker_padded,
        cache_slot=cache_slot,
        data_dir=data_dir,
    )
    memory_key = (resolved_data_dir, str(ticker_padded).zfill(6), str(cache_slot))

    with _STOCK_DETAIL_CACHE_LOCK:
        cached_payload = _STOCK_DETAIL_CACHE.get(memory_key)
        if isinstance(cached_payload, dict):
            _STOCK_DETAIL_CACHE.move_to_end(memory_key)
            return _normalize_stock_detail_payload(cached_payload)

    try:
        loaded, payload = _load_json_payload_from_sqlite(
            filepath=sqlite_key,
            signature=signature,
            logger=logger,
        )
    except Exception as error:
        logger.debug("Failed to load stock detail sqlite cache (%s): %s", ticker_padded, error)
        return None

    if not loaded:
        return None

    normalized_payload = _normalize_stock_detail_payload(payload)
    if normalized_payload is None:
        return None

    with _STOCK_DETAIL_CACHE_LOCK:
        _STOCK_DETAIL_CACHE[memory_key] = copy.deepcopy(normalized_payload)
        _STOCK_DETAIL_CACHE.move_to_end(memory_key)
        while len(_STOCK_DETAIL_CACHE) > _STOCK_DETAIL_CACHE_MAX_ENTRIES:
            _STOCK_DETAIL_CACHE.popitem(last=False)
    return copy.deepcopy(normalized_payload)


def _save_cached_stock_detail_payload(
    *,
    ticker_padded: str,
    cache_slot: str,
    data_dir: str | None,
    payload: dict[str, Any],
    logger: logging.Logger,
) -> None:
    normalized_payload = _normalize_stock_detail_payload(payload)
    if normalized_payload is None:
        return

    sqlite_key, signature, resolved_data_dir = _stock_detail_sqlite_context(
        ticker_padded=ticker_padded,
        cache_slot=cache_slot,
        data_dir=data_dir,
    )
    memory_key = (resolved_data_dir, str(ticker_padded).zfill(6), str(cache_slot))

    with _STOCK_DETAIL_CACHE_LOCK:
        _STOCK_DETAIL_CACHE[memory_key] = copy.deepcopy(normalized_payload)
        _STOCK_DETAIL_CACHE.move_to_end(memory_key)
        while len(_STOCK_DETAIL_CACHE) > _STOCK_DETAIL_CACHE_MAX_ENTRIES:
            _STOCK_DETAIL_CACHE.popitem(last=False)

    try:
        _save_json_payload_to_sqlite(
            filepath=sqlite_key,
            signature=signature,
            payload=normalized_payload,
            max_rows=_STOCK_DETAIL_SQLITE_MAX_ROWS,
            logger=logger,
        )
    except Exception as error:
        logger.debug("Failed to save stock detail sqlite cache (%s): %s", ticker_padded, error)


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
        "investorTrend": {"foreign": None, "institution": None, "individual": None, "individual_schema": 1},
        "financials": {"revenue": 0, "operatingProfit": 0, "netIncome": 0},
        "safety": {"debtRatio": 0, "currentRatio": 0},
        "message": "NaverFinanceCollector를 사용할 수 없어 기본 데이터를 반환합니다.",
    }


def append_investor_trend_5day(
    payload: dict[str, Any],
    ticker_padded: str,
    logger: logging.Logger,
    data_dir: str | None = None,
) -> None:
    """통합 서비스의 확정 5일 합계를 붙인다. 값이 없으면 키를 넣지 않는다([FLOW-023]).

    모달은 키가 없으면 Toss 합계로 물러서고, Toss 일수가 5 보다 적으면 「(N일)」을 붙인다.
    같은 5일 규칙을 여기에 다시 두지 않는다.
    """
    normalized_ticker = str(ticker_padded).zfill(6)
    normalized_data_dir = (data_dir or "").strip()
    if not normalized_data_dir:
        return

    try:
        trend_data = get_investor_trend_5day_for_ticker(
            ticker=normalized_ticker,
            data_dir=normalized_data_dir,
            verify_with_references=True,
        )
    except Exception as error:
        logger.debug("Unified 5-day trend service failed (%s): %s", normalized_ticker, error)
        return
    if not isinstance(trend_data, dict):
        return

    quality = trend_data.get("quality")
    if isinstance(quality, dict) and quality.get("csv_anomaly_flags"):
        logger.debug(
            "Unified 5-day trend anomaly (%s): flags=%s source=%s",
            normalized_ticker,
            quality.get("csv_anomaly_flags"),
            trend_data.get("source"),
        )
    payload["investorTrend5Day"] = {
        "foreign": int(trend_data.get("foreign", 0) or 0),
        "institution": int(trend_data.get("institution", 0) or 0),
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
            # [FE-048] 추세 요청이 실패하면 {} 가 온다. 0 을 채우면 실제 순매수 0 과 구분되지 않는다
            "foreign": investor_trend.get("foreign"),
            "institution": investor_trend.get("institution"),
            "foreignDays": investor_trend.get("foreign_days"),
            "institutionDays": investor_trend.get("institution_days"),
            "individual": investor_trend.get("individual"),
            "individual_schema": 1,
        },
        "financials": {
            "revenue": financials.get("revenue", 0),
            "operatingProfit": financials.get("operating_profit", 0),
            "netIncome": financials.get("net_income", 0),
            "revenuePeriod": financials.get("revenue_period"),
            "operatingProfitPeriod": financials.get("operating_profit_period"),
            "netIncomePeriod": financials.get("net_income_period"),
        },
        "safety": {
            "debtRatio": stability.get("debt_ratio", 0),
            "currentRatio": stability.get("current_ratio", 0),
        },
    }


def load_naver_stock_detail_payload(ticker_padded: str) -> dict[str, Any] | None:
    try:
        from engine.collectors.naver import NaverFinanceCollector
    except Exception:
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
    logger: logging.Logger,
    data_dir: str | None = None,
) -> dict[str, Any]:
    """종목 상세 조회를 Toss -> Naver -> 기본값 순서로 수행한다."""
    ticker_padded = normalize_ticker(ticker)
    cache_slot = _current_stock_detail_cache_slot()

    cached_payload = _load_cached_stock_detail_payload(
        ticker_padded=ticker_padded,
        cache_slot=cache_slot,
        data_dir=data_dir,
        logger=logger,
    )
    if isinstance(cached_payload, dict):
        return cached_payload

    try:
        from engine.toss_collector import TossCollector

        toss_data = TossCollector().get_full_stock_detail(ticker_padded)
        if toss_data and toss_data.get("name"):
            payload = build_toss_detail_payload(ticker_padded, toss_data)
            append_investor_trend_5day(payload, ticker_padded, logger, data_dir=data_dir)
            _save_cached_stock_detail_payload(
                ticker_padded=ticker_padded,
                cache_slot=cache_slot,
                data_dir=data_dir,
                payload=payload,
                logger=logger,
            )
            return payload
    except Exception as e:
        logger.warning(f"TossCollector 실패, NaverFinanceCollector로 폴백: {e}")

    try:
        naver_payload = load_naver_stock_detail_payload(ticker_padded)
        if naver_payload:
            _save_cached_stock_detail_payload(
                ticker_padded=ticker_padded,
                cache_slot=cache_slot,
                data_dir=data_dir,
                payload=naver_payload,
                logger=logger,
            )
            return naver_payload
    except ImportError as e:
        logger.warning(f"NaverFinanceCollector import 실패: {e}")
        fallback_payload = build_default_stock_detail_payload(ticker_padded)
        _save_cached_stock_detail_payload(
            ticker_padded=ticker_padded,
            cache_slot=cache_slot,
            data_dir=data_dir,
            payload=fallback_payload,
            logger=logger,
        )
        return fallback_payload
    except Exception as e:
        logger.warning(f"NaverFinanceCollector 조회 실패: {e}")

    fallback_payload = build_default_stock_detail_payload(ticker_padded)
    _save_cached_stock_detail_payload(
        ticker_padded=ticker_padded,
        cache_slot=cache_slot,
        data_dir=data_dir,
        payload=fallback_payload,
        logger=logger,
    )
    return fallback_payload
