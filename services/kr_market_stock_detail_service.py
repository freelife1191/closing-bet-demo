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
from typing import Any, Callable

import pandas as pd
from pandas.api.types import is_datetime64_any_dtype

from services.kr_market_data_cache_sqlite_payload import (
    load_json_payload_from_sqlite as _load_json_payload_from_sqlite,
    save_json_payload_to_sqlite as _save_json_payload_to_sqlite,
)
from services.investor_trend_5day_service import get_investor_trend_5day_for_ticker
from services.kr_market_csv_utils import (
    get_ticker_padded_series as _get_padded_ticker_series,
    load_csv_readonly as _load_csv_readonly,
)
from services.kr_market_realtime_price_service import normalize_ticker


_INVESTOR_TREND_5DAY_CACHE_LOCK = threading.Lock()
_INVESTOR_TREND_5DAY_CACHE: OrderedDict[
    tuple[object, ...],
    dict[str, tuple[int, int]],
] = OrderedDict()
_INVESTOR_TREND_5DAY_CACHE_MAX_ENTRIES = 8
_INVESTOR_TREND_5DAY_SQLITE_MAX_ROWS = 256
_INVESTOR_TREND_5DAY_SQLITE_CACHE_KEY_SUFFIX = "::investor_trend_5day_map"
_STOCK_DETAIL_CACHE_LOCK = threading.Lock()
_STOCK_DETAIL_CACHE: OrderedDict[
    tuple[str, str, str],
    dict[str, Any],
] = OrderedDict()
_STOCK_DETAIL_CACHE_MAX_ENTRIES = 256
_STOCK_DETAIL_SQLITE_MAX_ROWS = 4_096
_STOCK_DETAIL_SQLITE_CACHE_SCHEMA_VERSION = "stock_detail_v1"
_STOCK_DETAIL_SQLITE_CACHE_INTERVAL_MINUTES = 15
_LOGGER = logging.getLogger(__name__)


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
            return copy.deepcopy(cached_payload)

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
    data_dir: str | None = None,
) -> None:
    normalized_ticker = str(ticker_padded).zfill(6)

    normalized_data_dir = (data_dir or "").strip()
    if normalized_data_dir:
        try:
            trend_data = get_investor_trend_5day_for_ticker(
                ticker=normalized_ticker,
                data_dir=normalized_data_dir,
                verify_with_references=False,
            )
        except Exception as error:
            logger.debug("Unified 5-day trend service failed (%s): %s", normalized_ticker, error)
        else:
            if isinstance(trend_data, dict) and not _has_csv_anomaly_flags(trend_data):
                payload["investorTrend5Day"] = {
                    "foreign": int(trend_data.get("foreign", 0) or 0),
                    "institution": int(trend_data.get("institution", 0) or 0),
                }
                return
            if isinstance(trend_data, dict):
                logger.debug(
                    "Unified 5-day trend anomaly detected (%s): verify_with_references retry",
                    normalized_ticker,
                )
                try:
                    verified_trend = get_investor_trend_5day_for_ticker(
                        ticker=normalized_ticker,
                        data_dir=normalized_data_dir,
                        verify_with_references=True,
                    )
                except Exception as error:
                    logger.debug(
                        "Unified 5-day trend verification failed (%s): %s",
                        normalized_ticker,
                        error,
                    )
                else:
                    if isinstance(verified_trend, dict):
                        payload["investorTrend5Day"] = {
                            "foreign": int(verified_trend.get("foreign", 0) or 0),
                            "institution": int(verified_trend.get("institution", 0) or 0),
                        }
                        return

    try:
        trend_df = _load_csv_readonly(
            load_csv_file,
            "all_institutional_trend_data.csv",
            usecols=["ticker", "date", "foreign_buy", "inst_buy"],
        )
    except Exception as e:
        logger.warning(f"Failed to calculate 5-day trend for {ticker_padded}: {e}")
        return

    if trend_df.empty or "ticker" not in trend_df.columns:
        return
    if "foreign_buy" not in trend_df.columns or "inst_buy" not in trend_df.columns:
        return

    trend_map = _get_or_build_investor_trend_5day_map(trend_df)
    trend_values = trend_map.get(normalized_ticker)
    if not trend_values:
        return

    foreign_5d, inst_5d = trend_values
    payload["investorTrend5Day"] = {
        "foreign": foreign_5d,
        "institution": inst_5d,
    }


def _get_or_build_investor_trend_5day_map(
    trend_df: pd.DataFrame,
) -> dict[str, tuple[int, int]]:
    """
    투자자 5일 수급 합산 맵을 프레임 단위로 캐시한다.

    CSV 원본 로드는 load_csv_readonly(내부 SQLite snapshot 포함)로 처리하고,
    여기서는 반복 groupby 비용만 줄인다.
    """
    cache_key = _build_investor_trend_5day_cache_key(trend_df)
    with _INVESTOR_TREND_5DAY_CACHE_LOCK:
        cached = _INVESTOR_TREND_5DAY_CACHE.get(cache_key)
        if isinstance(cached, dict):
            _INVESTOR_TREND_5DAY_CACHE.move_to_end(cache_key)
            return cached

    sqlite_cache_context = _resolve_investor_trend_5day_sqlite_cache_context(cache_key)
    if sqlite_cache_context is not None:
        sqlite_cache_key, signature = sqlite_cache_context
        try:
            loaded, payload = _load_json_payload_from_sqlite(
                filepath=sqlite_cache_key,
                signature=signature,
                logger=_LOGGER,
            )
            if loaded and isinstance(payload, dict):
                cached_map = _deserialize_investor_trend_5day_map(payload)
                if cached_map is not None:
                    with _INVESTOR_TREND_5DAY_CACHE_LOCK:
                        _INVESTOR_TREND_5DAY_CACHE[cache_key] = cached_map
                        _INVESTOR_TREND_5DAY_CACHE.move_to_end(cache_key)
                        while len(_INVESTOR_TREND_5DAY_CACHE) > _INVESTOR_TREND_5DAY_CACHE_MAX_ENTRIES:
                            _INVESTOR_TREND_5DAY_CACHE.popitem(last=False)
                    return cached_map
        except Exception as error:
            _LOGGER.debug("Failed to load investor trend 5day sqlite cache: %s", error)

    trend_map = _build_investor_trend_5day_map(trend_df)
    with _INVESTOR_TREND_5DAY_CACHE_LOCK:
        _INVESTOR_TREND_5DAY_CACHE[cache_key] = trend_map
        _INVESTOR_TREND_5DAY_CACHE.move_to_end(cache_key)
        while len(_INVESTOR_TREND_5DAY_CACHE) > _INVESTOR_TREND_5DAY_CACHE_MAX_ENTRIES:
            _INVESTOR_TREND_5DAY_CACHE.popitem(last=False)

    if sqlite_cache_context is not None:
        sqlite_cache_key, signature = sqlite_cache_context
        try:
            _save_json_payload_to_sqlite(
                filepath=sqlite_cache_key,
                signature=signature,
                payload=_serialize_investor_trend_5day_map(trend_map),
                max_rows=_INVESTOR_TREND_5DAY_SQLITE_MAX_ROWS,
                logger=_LOGGER,
            )
        except Exception as error:
            _LOGGER.debug("Failed to save investor trend 5day sqlite cache: %s", error)
    return trend_map


def _has_csv_anomaly_flags(trend_data: dict[str, object] | None) -> bool:
    if not isinstance(trend_data, dict):
        return False
    quality = trend_data.get("quality")
    if not isinstance(quality, dict):
        return False
    csv_flags = quality.get("csv_anomaly_flags")
    return isinstance(csv_flags, list) and len(csv_flags) > 0


def _build_investor_trend_5day_cache_key(trend_df: pd.DataFrame) -> tuple[object, ...]:
    """
    5일 수급 집계 캐시 키를 생성한다.

    SQLite-backed CSV loader가 주입한 attrs 메타데이터가 있으면 이를 우선 사용해
    shallow copy로 생성된 서로 다른 DataFrame 객체 간에도 캐시를 재사용한다.
    """
    attrs = trend_df.attrs if isinstance(getattr(trend_df, "attrs", None), dict) else {}
    signature = attrs.get("kr_cache_signature")
    filepath = attrs.get("kr_cache_filepath")
    usecols = attrs.get("kr_cache_usecols")

    if (
        isinstance(filepath, str)
        and filepath
        and isinstance(signature, tuple)
        and len(signature) == 2
    ):
        try:
            mtime_ns = int(signature[0])
            size = int(signature[1])
            normalized_usecols = tuple(usecols) if isinstance(usecols, tuple) else ()
            return ("csv", filepath, mtime_ns, size, normalized_usecols)
        except Exception:
            pass

    return ("frame", id(trend_df), int(len(trend_df)))


def _investor_trend_5day_sqlite_cache_key(filepath: str) -> str:
    normalized_filepath = filepath.strip()
    return f"{normalized_filepath}{_INVESTOR_TREND_5DAY_SQLITE_CACHE_KEY_SUFFIX}"


def _resolve_investor_trend_5day_sqlite_cache_context(
    cache_key: tuple[object, ...],
) -> tuple[str, tuple[int, int]] | None:
    if len(cache_key) < 5:
        return None
    if cache_key[0] != "csv":
        return None

    filepath = cache_key[1]
    mtime_ns = cache_key[2]
    size = cache_key[3]
    if not isinstance(filepath, str) or not filepath:
        return None

    try:
        signature = (int(mtime_ns), int(size))
    except (TypeError, ValueError):
        return None
    return _investor_trend_5day_sqlite_cache_key(filepath), signature


def _serialize_investor_trend_5day_map(
    trend_map: dict[str, tuple[int, int]],
) -> dict[str, object]:
    rows: dict[str, list[int]] = {}
    for ticker, values in trend_map.items():
        if not isinstance(values, tuple) or len(values) != 2:
            continue
        foreign_value, inst_value = values
        rows[str(ticker).zfill(6)] = [int(foreign_value), int(inst_value)]
    return {"rows": rows}


def _deserialize_investor_trend_5day_map(
    payload: dict[str, object],
) -> dict[str, tuple[int, int]] | None:
    rows_payload = payload.get("rows")
    if not isinstance(rows_payload, dict):
        return None

    trend_map: dict[str, tuple[int, int]] = {}
    for ticker, values in rows_payload.items():
        ticker_key = str(ticker).zfill(6)
        if not ticker_key:
            continue
        if not isinstance(values, (list, tuple)) or len(values) != 2:
            continue
        try:
            foreign_value = int(float(values[0]))
            inst_value = int(float(values[1]))
        except (TypeError, ValueError):
            continue
        trend_map[ticker_key] = (foreign_value, inst_value)
    return trend_map


def _build_investor_trend_5day_map(
    trend_df: pd.DataFrame,
) -> dict[str, tuple[int, int]]:
    if trend_df.empty or "ticker" not in trend_df.columns:
        return {}

    working = trend_df
    ticker_series = _get_padded_ticker_series(working)
    try:
        working["ticker"] = ticker_series
    except Exception:
        working = working.copy()
        working["ticker"] = ticker_series

    working["foreign_buy"] = pd.to_numeric(working["foreign_buy"], errors="coerce").fillna(0)
    working["inst_buy"] = pd.to_numeric(working["inst_buy"], errors="coerce").fillna(0)

    if "date" in working.columns:
        if not is_datetime64_any_dtype(working["date"]):
            working["date"] = pd.to_datetime(working["date"], errors="coerce")
        working = working[working["date"].notna()]
        if working.empty:
            return {}
        working = working.sort_values(["ticker", "date"])
    else:
        working = working.sort_values(["ticker"])

    recent_5 = working.groupby("ticker", sort=False).tail(5)
    if recent_5.empty:
        return {}

    grouped = recent_5.groupby("ticker", sort=False).agg(
        foreign_buy_5d=("foreign_buy", "sum"),
        inst_buy_5d=("inst_buy", "sum"),
    )
    return {
        str(ticker).zfill(6): (int(foreign_sum), int(inst_sum))
        for ticker, foreign_sum, inst_sum in grouped.itertuples()
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
    load_csv_file: Callable[[str], pd.DataFrame],
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
            append_investor_trend_5day(
                payload,
                ticker_padded,
                load_csv_file,
                logger,
                data_dir=data_dir,
            )
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
