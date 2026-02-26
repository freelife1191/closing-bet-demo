#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KR Market Realtime/Detail Service

실시간 가격 및 종목 상세 조회 로직 분리 (Facade).
"""

from __future__ import annotations

import logging
from typing import Any, Callable

import pandas as pd

from services.kr_market_realtime_price_cache import (
    load_cached_realtime_prices as _load_cached_realtime_prices_impl,
    save_realtime_prices_to_cache as _save_realtime_prices_to_cache_impl,
)
from services.kr_market_realtime_price_service import (
    build_market_map as _build_market_map_impl,
    fetch_naver_missing_prices as _fetch_naver_missing_prices_impl,
    fetch_small_batch_prices as _fetch_small_batch_prices_impl,
    fetch_toss_bulk_prices as _fetch_toss_bulk_prices_impl,
    fetch_yfinance_missing_prices as _fetch_yfinance_missing_prices_impl,
    fill_missing_prices_from_csv as _fill_missing_prices_from_csv_impl,
    normalize_ticker as _normalize_ticker_impl,
    normalize_unique_tickers as _normalize_unique_tickers_impl,
)
from services.kr_market_stock_detail_service import (
    append_investor_trend_5day as _append_investor_trend_5day_impl,
    build_default_stock_detail_payload as _build_default_stock_detail_payload_impl,
    build_toss_detail_payload as _build_toss_detail_payload_impl,
    fetch_stock_detail_payload as _fetch_stock_detail_payload_impl,
    load_naver_stock_detail_payload as _load_naver_stock_detail_payload_impl,
    to_market_code as _to_market_code_impl,
)

_BULK_CACHE_SHORT_CIRCUIT_MAX_AGE_SECONDS = 60


def _normalize_ticker(ticker: Any) -> str:
    return _normalize_ticker_impl(ticker)


def _normalize_unique_tickers(tickers: list[Any]) -> list[str]:
    return _normalize_unique_tickers_impl(tickers)


def _fetch_small_batch_prices(
    tickers: list[Any],
    logger: logging.Logger,
    *,
    normalize_input: bool = True,
) -> dict[str, float]:
    return _fetch_small_batch_prices_impl(
        tickers,
        logger,
        normalize_input=normalize_input,
    )


def _fetch_toss_bulk_prices(
    tickers: list[Any],
    logger: logging.Logger,
    *,
    normalize_input: bool = True,
) -> dict[str, float]:
    return _fetch_toss_bulk_prices_impl(
        tickers,
        logger,
        normalize_input=normalize_input,
    )


def _fetch_naver_missing_prices(
    tickers: list[Any],
    prices: dict[str, float],
    logger: logging.Logger,
    *,
    normalize_input: bool = True,
) -> None:
    _fetch_naver_missing_prices_impl(
        tickers,
        prices,
        logger,
        normalize_input=normalize_input,
    )


def _build_market_map(
    load_csv_file: Callable[[str], pd.DataFrame],
    logger: logging.Logger | None = None,
) -> dict[str, str]:
    return _build_market_map_impl(load_csv_file, logger=logger)


def _fetch_yfinance_missing_prices(
    tickers: list[Any],
    prices: dict[str, float],
    load_csv_file: Callable[[str], pd.DataFrame],
    logger: logging.Logger,
    *,
    normalize_input: bool = True,
    get_data_path: Callable[[str], str] | None = None,
) -> None:
    _fetch_yfinance_missing_prices_impl(
        tickers,
        prices,
        load_csv_file,
        logger,
        normalize_input=normalize_input,
        get_data_path=get_data_path,
    )


def _fill_missing_prices_from_csv(
    tickers: list[Any],
    prices: dict[str, float],
    load_csv_file: Callable[[str], pd.DataFrame],
    latest_price_map: dict[str, float] | None = None,
    *,
    normalize_input: bool = True,
    get_data_path: Callable[[str], str] | None = None,
    logger: logging.Logger | None = None,
) -> None:
    _fill_missing_prices_from_csv_impl(
        tickers,
        prices,
        load_csv_file,
        latest_price_map=latest_price_map,
        normalize_input=normalize_input,
        get_data_path=get_data_path,
        logger=logger,
    )


def _load_cached_realtime_prices(
    tickers: list[Any],
    *,
    get_data_path: Callable[[str], str] | None = None,
    logger: logging.Logger | None = None,
    max_age_seconds: int = 900,
) -> dict[str, float]:
    return _load_cached_realtime_prices_impl(
        tickers,
        get_data_path=get_data_path,
        logger=logger,
        max_age_seconds=max_age_seconds,
    )


def _save_realtime_prices_to_cache(
    prices: dict[str, float],
    *,
    source: str,
    get_data_path: Callable[[str], str] | None = None,
    logger: logging.Logger | None = None,
) -> None:
    _save_realtime_prices_to_cache_impl(
        prices,
        source=source,
        get_data_path=get_data_path,
        logger=logger,
    )


def _has_complete_positive_prices(
    tickers: list[str],
    prices: dict[str, float],
) -> bool:
    for ticker in tickers:
        try:
            price_value = float(prices.get(ticker, 0) or 0)
        except (TypeError, ValueError):
            return False
        if price_value <= 0:
            return False
    return True


def _to_positive_float(value: object) -> float:
    try:
        resolved = float(value or 0)
    except (TypeError, ValueError):
        return 0.0
    return resolved if resolved > 0 else 0.0


def _collect_refreshed_prices(
    tickers: list[str],
    prices: dict[str, float],
    baseline_prices: dict[str, float],
) -> dict[str, float]:
    refreshed_prices: dict[str, float] = {}
    for ticker_str in tickers:
        resolved_price = _to_positive_float(prices.get(ticker_str, 0))
        if resolved_price <= 0:
            continue
        baseline_price = _to_positive_float(baseline_prices.get(ticker_str, 0))
        if baseline_price <= 0 or baseline_price != resolved_price:
            refreshed_prices[ticker_str] = resolved_price
    return refreshed_prices


def fetch_realtime_prices(
    tickers: list[Any],
    load_csv_file: Callable[[str], pd.DataFrame],
    logger: logging.Logger,
    load_latest_price_map: Callable[[], dict[str, float]] | None = None,
    get_data_path: Callable[[str], str] | None = None,
) -> dict[str, float]:
    """실시간 가격 조회 (소량 정밀 + 대량 Bulk + CSV fallback)."""
    if not tickers:
        return {}

    normalized_tickers = _normalize_unique_tickers(tickers)
    if not normalized_tickers:
        return {}

    # 중복 제거 후 유효 요청 건수 기준으로 분기한다.
    if len(normalized_tickers) <= 5:
        small_prices = _fetch_small_batch_prices(
            normalized_tickers,
            logger,
            normalize_input=False,
        )
        if _has_complete_positive_prices(normalized_tickers, small_prices):
            _save_realtime_prices_to_cache(
                small_prices,
                source="small_batch",
                get_data_path=get_data_path,
                logger=logger,
            )
            return small_prices
        unresolved_for_cache = [
            ticker_str
            for ticker_str in normalized_tickers
            if _to_positive_float(small_prices.get(ticker_str, 0)) <= 0
        ]
        cached_prices: dict[str, float] = {}
        if unresolved_for_cache:
            cached_prices = _load_cached_realtime_prices(
                unresolved_for_cache,
                get_data_path=get_data_path,
                logger=logger,
            )
            for ticker_str in unresolved_for_cache:
                fallback = _to_positive_float(cached_prices.get(ticker_str, 0))
                if fallback > 0:
                    small_prices[ticker_str] = fallback
        _save_realtime_prices_to_cache(
            small_prices,
            source="small_batch",
            get_data_path=get_data_path,
            logger=logger,
        )
        return small_prices

    # 대량 요청은 네트워크 fan-out 비용이 크므로, 매우 최근 SQLite 캐시가 완전하면 즉시 반환한다.
    recent_cached_prices = _load_cached_realtime_prices(
        normalized_tickers,
        get_data_path=get_data_path,
        logger=logger,
        max_age_seconds=_BULK_CACHE_SHORT_CIRCUIT_MAX_AGE_SECONDS,
    )
    if _has_complete_positive_prices(normalized_tickers, recent_cached_prices):
        return recent_cached_prices

    prices = _fetch_toss_bulk_prices(
        normalized_tickers,
        logger,
        normalize_input=False,
    )
    _fetch_naver_missing_prices(
        normalized_tickers,
        prices,
        logger,
        normalize_input=False,
    )
    _fetch_yfinance_missing_prices(
        normalized_tickers,
        prices,
        load_csv_file,
        logger,
        normalize_input=False,
        get_data_path=get_data_path,
    )
    _save_realtime_prices_to_cache(
        prices,
        source="bulk_chain",
        get_data_path=get_data_path,
        logger=logger,
    )
    baseline_resolved_prices: dict[str, float] = {
        ticker_str: _to_positive_float(prices.get(ticker_str, 0))
        for ticker_str in normalized_tickers
        if _to_positive_float(prices.get(ticker_str, 0)) > 0
    }
    if _has_complete_positive_prices(normalized_tickers, prices):
        return prices

    cached_prices: dict[str, float] = {
        ticker: _to_positive_float(price)
        for ticker, price in recent_cached_prices.items()
        if _to_positive_float(price) > 0
    }
    unresolved_for_cache = [
        ticker_str
        for ticker_str in normalized_tickers
        if _to_positive_float(prices.get(ticker_str, 0)) <= 0
        and _to_positive_float(cached_prices.get(ticker_str, 0)) <= 0
    ]
    if unresolved_for_cache:
        stale_cached_prices = _load_cached_realtime_prices(
            unresolved_for_cache,
            get_data_path=get_data_path,
            logger=logger,
        )
        for ticker_str, stale_price in stale_cached_prices.items():
            resolved_stale_price = _to_positive_float(stale_price)
            if resolved_stale_price > 0:
                cached_prices[str(ticker_str)] = resolved_stale_price

    for ticker_str in normalized_tickers:
        current = _to_positive_float(prices.get(ticker_str, 0))
        if current <= 0:
            fallback = _to_positive_float(cached_prices.get(ticker_str, 0))
            if fallback > 0:
                prices[ticker_str] = fallback

    if _has_complete_positive_prices(normalized_tickers, prices):
        refreshed_prices = _collect_refreshed_prices(
            normalized_tickers,
            prices,
            baseline_resolved_prices,
        )
        if refreshed_prices:
            _save_realtime_prices_to_cache(
                refreshed_prices,
                source="bulk_resolved",
                get_data_path=get_data_path,
                logger=logger,
            )
        return prices

    latest_price_map: dict[str, float] | None = None
    if load_latest_price_map is not None:
        try:
            loaded = load_latest_price_map()
            if isinstance(loaded, dict):
                latest_price_map = loaded
        except Exception as e:
            logger.debug(f"load_latest_price_map failed: {e}")

    _fill_missing_prices_from_csv(
        normalized_tickers,
        prices,
        load_csv_file,
        latest_price_map=latest_price_map,
        normalize_input=False,
        get_data_path=get_data_path,
        logger=logger,
    )

    # 네트워크 체인 이후 cache/CSV 보완으로 새로 해소된 값은 updated_at을 갱신해
    # 다음 호출의 recent SQLite short-circuit 적중률을 높인다.
    refreshed_prices = _collect_refreshed_prices(
        normalized_tickers,
        prices,
        baseline_resolved_prices,
    )
    if refreshed_prices:
        _save_realtime_prices_to_cache(
            refreshed_prices,
            source="bulk_resolved",
            get_data_path=get_data_path,
            logger=logger,
        )
    return prices


def _to_market_code(market_value: str | None) -> str:
    return _to_market_code_impl(market_value)


def _build_default_stock_detail_payload(ticker_padded: str) -> dict[str, Any]:
    return _build_default_stock_detail_payload_impl(ticker_padded)


def _append_investor_trend_5day(
    payload: dict[str, Any],
    ticker_padded: str,
    load_csv_file: Callable[[str], pd.DataFrame],
    logger: logging.Logger,
    data_dir: str | None = None,
) -> None:
    _append_investor_trend_5day_impl(
        payload,
        ticker_padded,
        load_csv_file,
        logger,
        data_dir=data_dir,
    )


def _build_toss_detail_payload(ticker_padded: str, toss_data: dict[str, Any]) -> dict[str, Any]:
    return _build_toss_detail_payload_impl(ticker_padded, toss_data)


def _load_naver_stock_detail_payload(ticker_padded: str) -> dict[str, Any] | None:
    return _load_naver_stock_detail_payload_impl(ticker_padded)


def fetch_stock_detail_payload(
    ticker: str,
    load_csv_file: Callable[[str], pd.DataFrame],
    logger: logging.Logger,
    data_dir: str | None = None,
) -> dict[str, Any]:
    return _fetch_stock_detail_payload_impl(
        ticker,
        load_csv_file,
        logger,
        data_dir=data_dir,
    )
