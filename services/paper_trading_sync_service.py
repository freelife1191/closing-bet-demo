#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Paper Trading 가격 동기화 서비스
"""

from __future__ import annotations

import logging
import time
from typing import Any, Callable


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
    """티커를 6자리 문자열로 정규화하고 중복을 제거한다."""
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


def _normalize_resolved_prices(prices: dict[str, int] | None) -> dict[str, int]:
    """공급자 가격 결과를 ticker/price 정규화 후 유효값만 반환한다."""
    if not isinstance(prices, dict) or not prices:
        return {}

    normalized: dict[str, int] = {}
    for ticker, value in prices.items():
        ticker_key = _normalize_ticker(ticker)
        try:
            price_int = int(float(value))
        except (TypeError, ValueError):
            continue
        if price_int <= 0:
            continue
        normalized[ticker_key] = price_int

    return normalized


def _remove_resolved_tickers(
    missing_tickers: list[str],
    resolved_codes: set[str],
) -> list[str]:
    """새로 해소된 티커를 missing 목록에서 제거한다."""
    if not missing_tickers or not resolved_codes:
        return missing_tickers
    return [ticker for ticker in missing_tickers if ticker not in resolved_codes]


def _resolve_prices_from_provider(
    *,
    missing_tickers: list[str],
    resolved_prices: dict[str, int],
    fetch_fn: Callable[[list[str]], dict[str, int]],
) -> list[str]:
    if not missing_tickers:
        return missing_tickers

    provider_prices = _normalize_resolved_prices(fetch_fn(missing_tickers))
    if provider_prices:
        resolved_prices.update(provider_prices)
        return _remove_resolved_tickers(missing_tickers, set(provider_prices.keys()))
    return missing_tickers


def _log_provider_fallback(
    *,
    provider_chain: list[tuple[str, Callable[[list[str]], dict[str, int]]]],
    provider_index: int,
    unresolved_count: int,
    logger: logging.Logger,
) -> None:
    """이전 공급자 실패 후 다음 공급자로 넘어갈 때 로그를 남긴다."""
    if provider_index <= 0 or provider_index >= len(provider_chain):
        return

    previous_provider = provider_chain[provider_index - 1][0]
    next_provider = provider_chain[provider_index][0]
    logger.info(
        f"{previous_provider} failed for {unresolved_count} tickers. "
        f"Trying {next_provider}..."
    )


def _build_provider_chain(
    *,
    session: Any,
    yf_module: Any,
    pykrx_stock: Any,
    fetch_prices_toss_fn: Callable[[Any, list[str]], dict[str, int]],
    fetch_prices_naver_fn: Callable[[Any, list[str]], dict[str, int]],
    fetch_prices_yfinance_fn: Callable[[Any, list[str]], dict[str, int]],
    fetch_prices_pykrx_fn: Callable[[Any, list[str]], dict[str, int]],
) -> list[tuple[str, Callable[[list[str]], dict[str, int]]]]:
    """실행 가능한 가격 공급자 체인을 구성한다."""
    chain: list[tuple[str, Callable[[list[str]], dict[str, int]]]] = [
        ("toss", lambda unresolved: fetch_prices_toss_fn(session, unresolved)),
        ("naver", lambda unresolved: fetch_prices_naver_fn(session, unresolved)),
    ]

    if yf_module is not None:
        chain.append(("yf", lambda unresolved: fetch_prices_yfinance_fn(yf_module, unresolved)))
    if pykrx_stock is not None:
        chain.append(("pykrx", lambda unresolved: fetch_prices_pykrx_fn(pykrx_stock, unresolved)))

    return chain


def refresh_price_cache_once(
    *,
    tickers: list[str],
    tickers_already_normalized: bool = False,
    session: Any,
    yf_module: Any,
    pykrx_stock: Any,
    fetch_prices_toss_fn: Callable[[Any, list[str]], dict[str, int]],
    fetch_prices_naver_fn: Callable[[Any, list[str]], dict[str, int]],
    fetch_prices_yfinance_fn: Callable[[Any, list[str]], dict[str, int]],
    fetch_prices_pykrx_fn: Callable[[Any, list[str]], dict[str, int]],
    update_interval_sec: int,
    empty_portfolio_sleep_sec: int,
    logger: logging.Logger,
) -> tuple[dict[str, int], int]:
    """
    포트폴리오 종목 최신 가격을 1회 갱신한다.

    Returns:
        (resolved_prices, 다음 루프까지 대기 초)
    """
    if not tickers:
        return {}, empty_portfolio_sleep_sec

    resolved_prices: dict[str, int] = {}
    if tickers_already_normalized:
        # 호출자가 정규화/중복제거 완료를 보장한 fast-path.
        # 대량 포트폴리오 루프에서 매 사이클 O(n) 검증 비용을 피한다.
        missing_tickers = list(tickers)
    else:
        missing_tickers = _normalize_unique_tickers(tickers)

    provider_chain = _build_provider_chain(
        session=session,
        yf_module=yf_module,
        pykrx_stock=pykrx_stock,
        fetch_prices_toss_fn=fetch_prices_toss_fn,
        fetch_prices_naver_fn=fetch_prices_naver_fn,
        fetch_prices_yfinance_fn=fetch_prices_yfinance_fn,
        fetch_prices_pykrx_fn=fetch_prices_pykrx_fn,
    )

    for idx, (_provider_name, fetch_fn) in enumerate(provider_chain):
        if not missing_tickers:
            break

        _log_provider_fallback(
            provider_chain=provider_chain,
            provider_index=idx,
            unresolved_count=len(missing_tickers),
            logger=logger,
        )

        missing_tickers = _resolve_prices_from_provider(
            missing_tickers=missing_tickers,
            resolved_prices=resolved_prices,
            fetch_fn=fetch_fn,
        )

    return resolved_prices, update_interval_sec


def run_price_update_loop(
    *,
    is_running_fn: Callable[[], bool],
    refresh_price_cache_once_fn: Callable[[Any, Any, Any], int],
    update_interval_sec: int,
    logger: logging.Logger,
) -> None:
    """백그라운드 가격 동기화 루프를 실행한다."""
    import requests
    import yfinance as yf

    try:
        from pykrx import stock
    except ImportError:
        stock = None
        logger.warning("pykrx module not found. KRX fallback will disabled.")

    logging.getLogger("yfinance").setLevel(logging.CRITICAL)
    logging.getLogger("peewee").setLevel(logging.CRITICAL)
    logging.getLogger("urllib3").setLevel(logging.ERROR)

    session = requests.Session()
    try:
        while is_running_fn():
            sleep_seconds = update_interval_sec
            try:
                sleep_seconds = refresh_price_cache_once_fn(session, yf, stock)
            except Exception as error:
                logger.error(f"PaperTrading Loop Error: {error}")
            time.sleep(max(1, int(sleep_seconds)))
    finally:
        try:
            session.close()
        except Exception as error:
            logger.debug(f"Failed to close requests session: {error}")
