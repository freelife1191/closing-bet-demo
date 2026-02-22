#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KR Market Realtime Price Service

실시간 가격 조회 로직 분리.
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Any, Callable

import pandas as pd

from services.kr_market_csv_utils import (
    build_latest_close_map_from_prices_df,
    load_csv_readonly as _load_csv_readonly,
)
from services.kr_market_realtime_latest_close_cache import (
    clear_latest_close_map_cache as _clear_latest_close_map_cache_impl,
    load_cached_latest_close_map as _load_cached_latest_close_map_impl,
)
from services.kr_market_realtime_market_map_cache import (
    build_market_map as _build_market_map_impl,
    clear_market_map_cache as _clear_market_map_cache_impl,
)


def clear_market_map_cache() -> None:
    _clear_market_map_cache_impl()
    _clear_latest_close_map_cache_impl()

def normalize_ticker(ticker: Any) -> str:
    return str(ticker).zfill(6)


def _is_normalized_unique_ticker_list(tickers: list[Any]) -> bool:
    seen: set[str] = set()
    for ticker in tickers:
        if not isinstance(ticker, str):
            return False
        if len(ticker) != 6 or not ticker.isdigit():
            return False
        if ticker in seen:
            return False
        seen.add(ticker)
    return True


def normalize_unique_tickers(tickers: list[Any]) -> list[str]:
    """입력 순서를 유지하면서 티커를 정규화/중복 제거한다."""
    if _is_normalized_unique_ticker_list(tickers):
        return list(tickers)

    seen: set[str] = set()
    normalized: list[str] = []
    for ticker in tickers:
        ticker_str = normalize_ticker(ticker)
        if ticker_str in seen:
            continue
        seen.add(ticker_str)
        normalized.append(ticker_str)
    return normalized


def _resolve_normalized_tickers(
    tickers: list[Any],
    *,
    normalize_input: bool,
) -> list[str]:
    if normalize_input:
        return normalize_unique_tickers(tickers)
    return list(tickers)


def _normalize_price_map(price_map: dict[Any, Any]) -> dict[str, float]:
    normalized: dict[str, float] = {}
    for ticker, value in price_map.items():
        ticker_key = normalize_ticker(ticker)
        try:
            normalized[ticker_key] = float(value or 0)
        except (TypeError, ValueError):
            normalized[ticker_key] = 0.0
    return normalized

def fetch_small_batch_prices(
    tickers: list[Any],
    logger: logging.Logger,
    *,
    normalize_input: bool = True,
) -> dict[str, float]:
    """소량 요청은 fetch_stock_price를 사용해 정밀 조회한다."""
    from engine.data_sources import fetch_stock_price

    if not tickers:
        return {}

    normalized_tickers = _resolve_normalized_tickers(
        tickers,
        normalize_input=normalize_input,
    )
    prices: dict[str, float] = {}

    def _fetch_one(ticker_str: str) -> tuple[str, float]:
        try:
            rt_data = fetch_stock_price(ticker_str)
            price_value = float(rt_data["price"]) if rt_data and rt_data.get("price") else 0.0
            return ticker_str, price_value
        except Exception as e:
            logger.warning(f"Failed to fetch stock price for {ticker_str}: {e}")
            return ticker_str, 0.0

    if len(normalized_tickers) <= 2:
        for ticker_str in normalized_tickers:
            resolved_ticker, price_value = _fetch_one(ticker_str)
            prices[resolved_ticker] = price_value
        return prices

    worker_count = min(4, len(normalized_tickers))
    with ThreadPoolExecutor(max_workers=max(1, worker_count)) as executor:
        futures = [executor.submit(_fetch_one, ticker_str) for ticker_str in normalized_tickers]
        for future in as_completed(futures):
            ticker_str, price_value = future.result()
            prices[ticker_str] = price_value

    return prices


def fetch_toss_bulk_prices(
    tickers: list[Any],
    logger: logging.Logger,
    *,
    normalize_input: bool = True,
) -> dict[str, float]:
    import requests

    prices: dict[str, float] = {}
    normalized_tickers = _resolve_normalized_tickers(
        tickers,
        normalize_input=normalize_input,
    )
    toss_codes = [f"A{ticker}" for ticker in normalized_tickers]
    headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
    session = requests.Session()

    try:
        for idx in range(0, len(toss_codes), 50):
            chunk = toss_codes[idx : idx + 50]
            url = (
                "https://wts-info-api.tossinvest.com/api/v3/stock-prices/details?"
                f"productCodes={','.join(chunk)}"
            )
            response = session.get(url, headers=headers, timeout=5)
            if response.status_code != 200:
                continue
            results = response.json().get("result", [])
            for item in results:
                code = item.get("code", "")
                clean_code = code[1:] if code.startswith("A") else code
                close = item.get("close")
                if clean_code and close:
                    prices[clean_code] = float(close)
    except Exception as e:
        logger.debug(f"Toss Bulk API Failed: {e}")
    finally:
        session.close()

    return prices


def fetch_naver_missing_prices(
    tickers: list[Any],
    prices: dict[str, float],
    logger: logging.Logger,
    *,
    normalize_input: bool = True,
) -> None:
    import requests

    normalized_tickers = _resolve_normalized_tickers(
        tickers,
        normalize_input=normalize_input,
    )
    missing = [ticker for ticker in normalized_tickers if ticker not in prices]
    if not missing:
        return

    headers = {"User-Agent": "Mozilla/5.0"}

    def _fetch_chunk(chunk_tickers: list[str]) -> dict[str, float]:
        session = requests.Session()
        resolved: dict[str, float] = {}
        try:
            for ticker_code in chunk_tickers:
                try:
                    url = f"https://m.stock.naver.com/api/stock/{ticker_code}/basic"
                    response = session.get(url, headers=headers, timeout=2)
                    if response.status_code != 200:
                        continue
                    data = response.json()
                    close_price = data.get("closePrice")
                    if close_price is None:
                        continue
                    resolved[ticker_code] = float(str(close_price).replace(",", ""))
                except Exception as e:
                    logger.debug(f"Naver price fallback failed ({ticker_code}): {e}")
        finally:
            session.close()
        return resolved

    if len(missing) <= 2:
        prices.update(_fetch_chunk(missing))
        return

    worker_count = max(1, min(8, len(missing)))
    chunk_size = (len(missing) + worker_count - 1) // worker_count
    chunks = [missing[idx : idx + chunk_size] for idx in range(0, len(missing), chunk_size)]

    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        futures = [executor.submit(_fetch_chunk, chunk) for chunk in chunks]
        for future in as_completed(futures):
            try:
                prices.update(future.result())
            except Exception as e:
                logger.debug(f"Naver concurrent fallback failed: {e}")


def build_market_map(
    load_csv_file: Callable[[str], pd.DataFrame],
    logger: logging.Logger | None = None,
    get_data_path: Callable[[str], str] | None = None,
) -> dict[str, str]:
    return _build_market_map_impl(
        load_csv_file,
        logger=logger,
        get_data_path=get_data_path,
    )


def _build_latest_prices_from_dataframe(df_prices: pd.DataFrame) -> dict[str, float]:
    """daily_prices DataFrame에서 ticker별 최신 close 맵을 계산한다."""
    return build_latest_close_map_from_prices_df(df_prices)


def _load_cached_latest_close_map(
    *,
    load_csv_file: Callable[[str], pd.DataFrame],
    get_data_path: Callable[[str], str] | None,
    logger: logging.Logger | None,
) -> dict[str, float] | None:
    return _load_cached_latest_close_map_impl(
        load_csv_file=load_csv_file,
        get_data_path=get_data_path,
        load_csv_readonly=_load_csv_readonly,
        build_latest_prices_from_dataframe=_build_latest_prices_from_dataframe,
        logger=logger,
    )


def fetch_yfinance_missing_prices(
    tickers: list[Any],
    prices: dict[str, float],
    load_csv_file: Callable[[str], pd.DataFrame],
    logger: logging.Logger,
    *,
    normalize_input: bool = True,
    get_data_path: Callable[[str], str] | None = None,
) -> None:
    normalized_tickers = _resolve_normalized_tickers(
        tickers,
        normalize_input=normalize_input,
    )
    missing = [ticker for ticker in normalized_tickers if ticker not in prices]
    if not missing:
        return

    now = datetime.now()
    is_weekend = now.weekday() >= 5
    is_market_hours = 9 <= now.hour < 16
    if is_weekend or not is_market_hours:
        return

    try:
        import yfinance as yf
    except Exception as e:
        logger.debug(f"yfinance import failed: {e}")
        return

    market_map = build_market_map(
        load_csv_file,
        logger=logger,
        get_data_path=get_data_path,
    )
    yf_tickers: list[str] = []
    ticker_map: dict[str, str] = {}

    for ticker_padded in missing:
        market = market_map.get(ticker_padded, "KOSPI")
        suffix = ".KQ" if market == "KOSDAQ" else ".KS"
        yf_ticker = f"{ticker_padded}{suffix}"
        yf_tickers.append(yf_ticker)
        ticker_map[yf_ticker] = ticker_padded

    if not yf_tickers:
        return

    yf_logger = logging.getLogger("yfinance")
    original_level = yf_logger.level
    yf_logger.setLevel(logging.CRITICAL)

    try:
        price_data = yf.download(yf_tickers, period="5d", interval="1d", progress=False, threads=True)
    except Exception as e:
        logger.debug(f"yfinance Fallback Failed: {e}")
        return
    finally:
        yf_logger.setLevel(original_level)

    if price_data.empty or "Close" not in price_data:
        return

    closes = price_data["Close"]

    def extract_price(symbol: str, source: pd.DataFrame | pd.Series) -> float | None:
        try:
            if isinstance(source, pd.DataFrame) and symbol in source.columns:
                series = source[symbol].dropna()
                if not series.empty:
                    return float(series.iloc[-1])
            elif isinstance(source, pd.Series) and not source.dropna().empty:
                return float(source.dropna().iloc[-1])
        except (TypeError, ValueError, IndexError, KeyError):
            return None
        return None

    for yf_symbol in yf_tickers:
        value = extract_price(yf_symbol, closes)
        if value is not None:
            prices[ticker_map[yf_symbol]] = value


def fill_missing_prices_from_csv(
    tickers: list[Any],
    prices: dict[str, float],
    load_csv_file: Callable[[str], pd.DataFrame],
    latest_price_map: dict[str, float] | None = None,
    *,
    normalize_input: bool = True,
    get_data_path: Callable[[str], str] | None = None,
    logger: logging.Logger | None = None,
) -> None:
    normalized_tickers = _resolve_normalized_tickers(
        tickers,
        normalize_input=normalize_input,
    )
    if all(ticker_str in prices for ticker_str in normalized_tickers):
        return

    if latest_price_map:
        normalized_map = _normalize_price_map(latest_price_map)
        for ticker_str in normalized_tickers:
            if ticker_str not in prices:
                prices[ticker_str] = float(normalized_map.get(ticker_str, 0) or 0)
        return

    cached_latest_prices = _load_cached_latest_close_map(
        load_csv_file=load_csv_file,
        get_data_path=get_data_path,
        logger=logger,
    )
    if isinstance(cached_latest_prices, dict):
        for ticker_str in normalized_tickers:
            if ticker_str not in prices:
                prices[ticker_str] = float(cached_latest_prices.get(ticker_str, 0) or 0)
        return

    df_prices = _load_csv_readonly(
        load_csv_file,
        "daily_prices.csv",
        usecols=["date", "ticker", "close"],
    )
    if df_prices.empty or "ticker" not in df_prices.columns or "close" not in df_prices.columns:
        for ticker_str in normalized_tickers:
            prices.setdefault(ticker_str, 0.0)
        return

    latest_prices = _build_latest_prices_from_dataframe(df_prices)
    for ticker_str in normalized_tickers:
        if ticker_str not in prices:
            prices[ticker_str] = float(latest_prices.get(ticker_str, 0) or 0)
