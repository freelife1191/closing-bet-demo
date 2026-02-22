#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Paper Trading 가격 수집 유틸리티

서비스 본체에서 네트워크별 수집 로직을 분리해 가독성과 테스트 용이성을 높인다.
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

import pandas as pd


def _normalize_ticker(ticker: str) -> str:
    return str(ticker).zfill(6)


def _is_normalized_unique_ticker_list(tickers: list[str]) -> bool:
    seen: set[str] = set()
    for ticker in tickers:
        if not isinstance(ticker, str) or len(ticker) != 6 or not ticker.isdigit():
            return False
        if ticker in seen:
            return False
        seen.add(ticker)
    return True


def _normalize_unique_tickers(tickers: list[str]) -> list[str]:
    if not tickers:
        return []
    if _is_normalized_unique_ticker_list(tickers):
        return list(tickers)

    seen: set[str] = set()
    normalized: list[str] = []
    for ticker in tickers:
        ticker_str = _normalize_ticker(ticker)
        if ticker_str in seen:
            continue
        seen.add(ticker_str)
        normalized.append(ticker_str)
    return normalized


def _extract_close_series(df: pd.DataFrame) -> pd.Series | pd.DataFrame:
    """yfinance 다운로드 결과에서 종가 시계열을 안정적으로 추출한다."""
    try:
        return df["Close"]
    except KeyError:
        if isinstance(df.columns, pd.MultiIndex) and "Close" in df.columns.get_level_values(0):
            return df.xs("Close", axis=1, level=0, drop_level=True)
        return df


def fetch_prices_toss(
    *,
    session: Any,
    tickers: list[str],
    chunk_size: int,
    retry_count: int,
    logger: Any,
) -> Dict[str, int]:
    """Toss API에서 여러 종목 가격을 한 번에 조회한다."""
    if not tickers:
        return {}

    normalized_tickers = _normalize_unique_tickers(tickers)
    if not normalized_tickers:
        return {}

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
    }
    ticker_map = {ticker: ticker for ticker in normalized_tickers}
    toss_codes = [f"A{ticker}" for ticker in normalized_tickers]

    prices: Dict[str, int] = {}
    for i in range(0, len(toss_codes), chunk_size):
        chunk = toss_codes[i : i + chunk_size]
        codes_str = ",".join(chunk)
        url = (
            "https://wts-info-api.tossinvest.com/api/v3/stock-prices/details"
            f"?productCodes={codes_str}"
        )

        for attempt in range(retry_count):
            try:
                response = session.get(url, headers=headers, timeout=5)
                if response.status_code == 200:
                    results = response.json().get("result", [])
                    for item in results:
                        raw_code = item.get("code", "")
                        clean_code = raw_code[1:] if raw_code.startswith("A") else raw_code
                        original_ticker = ticker_map.get(clean_code)
                        close = item.get("close")
                        if original_ticker and close is not None:
                            prices[original_ticker] = int(close)
                    break

                if response.status_code == 429:
                    wait_seconds = (attempt + 1) * 2
                    logger.warning(f"Toss API Rate Limit. Waiting {wait_seconds}s...")
                    time.sleep(wait_seconds)
                    continue

                logger.warning(
                    f"Toss API returned {response.status_code}: {response.text[:100]}"
                )
                if 400 <= response.status_code < 500:
                    break
            except Exception as error:
                if attempt < retry_count - 1:
                    time.sleep(1)
                    logger.warning(
                        f"Toss API Retry {attempt + 1}/{retry_count} failed: {error}"
                    )
                else:
                    logger.error(f"Toss API Error after retries: {error}")

    return prices


def fetch_prices_naver(
    *,
    session: Any,
    tickers: list[str],
    throttle_sec: float,
    logger: Any,
) -> Dict[str, int]:
    """Naver API에서 개별 종목 가격을 조회한다."""
    if not tickers:
        return {}

    normalized_tickers = _normalize_unique_tickers(tickers)
    if not normalized_tickers:
        return {}

    from requests.exceptions import ConnectionError as RequestsConnectionError

    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Referer": "https://m.stock.naver.com/",
    }

    prices: Dict[str, int] = {}
    for idx, ticker in enumerate(normalized_tickers):
        if idx > 0 and throttle_sec > 0:
            time.sleep(throttle_sec)
        try:
            url = f"https://m.stock.naver.com/api/stock/{ticker}/basic"
            response = session.get(url, headers=headers, timeout=5)
            if response.status_code != 200:
                continue

            data = response.json()
            close_price = data.get("closePrice")
            if close_price:
                prices[ticker] = int(str(close_price).replace(",", ""))
        except RequestsConnectionError as error:
            remaining = len(normalized_tickers) - idx
            logger.warning(
                "Naver API 네트워크 오류 (DNS/연결 실패). "
                f"나머지 {remaining}개 종목 건너뜀: {error}"
            )
            break
        except Exception as error:
            logger.error(f"Naver API Error for {ticker}: {error}")

    return prices


def fetch_prices_yfinance(
    *,
    yf_module: Any,
    tickers: list[str],
    logger: Any,
) -> Dict[str, int]:
    """yfinance에서 종가를 조회한다."""
    if not tickers or yf_module is None or not hasattr(yf_module, "download"):
        return {}

    normalized_tickers = _normalize_unique_tickers(tickers)
    if not normalized_tickers:
        return {}

    yf_tickers = [f"{ticker}.KS" for ticker in normalized_tickers]
    try:
        df = yf_module.download(yf_tickers, period="1d", progress=False, threads=False)
    except Exception as error:
        logger.error(f"PaperTrading YF Error: {error}")
        return {}

    if df.empty:
        return {}

    closes = _extract_close_series(df)

    prices: Dict[str, int] = {}
    for ticker in normalized_tickers:
        symbol = f"{ticker}.KS"
        value: Optional[float] = None
        try:
            if isinstance(closes, pd.Series):
                value = closes.iloc[-1]
            elif symbol in closes.columns:
                value = closes[symbol].dropna().iloc[-1]
            if value is not None:
                prices[ticker] = int(float(value))
        except Exception:
            continue

    return prices


def fetch_prices_pykrx(
    *,
    pykrx_stock: Any,
    tickers: list[str],
    logger: Any | None = None,
) -> Dict[str, int]:
    """pykrx에서 종가를 조회한다."""
    if not pykrx_stock or not tickers:
        return {}

    normalized_tickers = _normalize_unique_tickers(tickers)
    if not normalized_tickers:
        return {}

    now = datetime.now()
    today_str = now.strftime("%Y%m%d")
    yesterday_str = (now - timedelta(days=1)).strftime("%Y%m%d")

    prices: Dict[str, int] = {}
    for ticker in normalized_tickers:
        try:
            df = pykrx_stock.get_market_ohlcv(today_str, today_str, ticker)
            if df.empty or "종가" not in df.columns:
                df = pykrx_stock.get_market_ohlcv(yesterday_str, yesterday_str, ticker)
            if not df.empty and "종가" in df.columns:
                close_price = df["종가"].iloc[-1]
                if close_price > 0:
                    prices[ticker] = int(close_price)
        except Exception as error:
            if logger is not None:
                logger.debug(f"pykrx 가격 조회 실패 ({ticker}): {error}")
            continue

    return prices
