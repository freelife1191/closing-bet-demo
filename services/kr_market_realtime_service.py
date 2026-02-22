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
        cached_prices = _load_cached_realtime_prices(
            normalized_tickers,
            get_data_path=get_data_path,
            logger=logger,
        )
        for ticker_str in normalized_tickers:
            current = float(small_prices.get(ticker_str, 0) or 0)
            if current <= 0:
                fallback = float(cached_prices.get(ticker_str, 0) or 0)
                if fallback > 0:
                    small_prices[ticker_str] = fallback
        _save_realtime_prices_to_cache(
            small_prices,
            source="small_batch",
            get_data_path=get_data_path,
            logger=logger,
        )
        return small_prices

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
    if load_latest_price_map is None and _has_complete_positive_prices(normalized_tickers, prices):
        return prices

    cached_prices = _load_cached_realtime_prices(
        normalized_tickers,
        get_data_path=get_data_path,
        logger=logger,
    )
    for ticker_str in normalized_tickers:
        current = float(prices.get(ticker_str, 0) or 0)
        if current <= 0:
            fallback = float(cached_prices.get(ticker_str, 0) or 0)
            if fallback > 0:
                prices[ticker_str] = fallback

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
) -> None:
    _append_investor_trend_5day_impl(payload, ticker_padded, load_csv_file, logger)


def _build_toss_detail_payload(ticker_padded: str, toss_data: dict[str, Any]) -> dict[str, Any]:
    return _build_toss_detail_payload_impl(ticker_padded, toss_data)


def _load_naver_stock_detail_payload(ticker_padded: str) -> dict[str, Any] | None:
    return _load_naver_stock_detail_payload_impl(ticker_padded)


def fetch_stock_detail_payload(
    ticker: str,
    load_csv_file: Callable[[str], pd.DataFrame],
    logger: logging.Logger,
) -> dict[str, Any]:
    return _fetch_stock_detail_payload_impl(ticker, load_csv_file, logger)
