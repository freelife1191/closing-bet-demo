#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Engine - Data Source Strategy Pattern

호환 레이어: 기존 import 경로(engine.data_sources)를 유지하면서
전략/글로벌 수집기 구현은 분리 모듈에서 제공합니다.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

import pandas as pd

from engine.data_sources_global_fetcher import GlobalDataFetcher
from engine.data_sources_stock_price import (
    build_stock_price_payload as _build_stock_price_payload_impl,
    extract_series_value as _extract_series_value_impl,
    fetch_investor_trend_naver as _fetch_investor_trend_naver_impl,
    fetch_stock_price_from_naver as _fetch_stock_price_from_naver_impl,
    fetch_stock_price_from_toss as _fetch_stock_price_from_toss_impl,
    fetch_stock_price_from_yfinance as _fetch_stock_price_from_yfinance_impl,
    is_valid_yf_history as _is_valid_yf_history_impl,
)
from engine.data_sources_strategies import (
    DataSourceManager,
    DataSourceStrategy,
    FDRSource,
    PykrxSource,
    YFinanceSource,
)

logger = logging.getLogger(__name__)


# -----------------------------------------------------------------------------
# Stock price compatibility wrappers
# -----------------------------------------------------------------------------
def _build_stock_price_payload(
    *,
    current: float,
    prev_close: float,
    volume: float,
    source: str,
) -> Dict[str, Any]:
    return _build_stock_price_payload_impl(
        current=current,
        prev_close=prev_close,
        volume=volume,
        source=source,
    )


def _fetch_stock_price_from_toss(ticker: str) -> Dict[str, Any] | None:
    return _fetch_stock_price_from_toss_impl(ticker)


def _fetch_stock_price_from_naver(ticker: str) -> Dict[str, Any] | None:
    return _fetch_stock_price_from_naver_impl(ticker)


def _is_valid_yf_history(hist: pd.DataFrame) -> bool:
    return _is_valid_yf_history_impl(hist)


def _extract_series_value(series: pd.Series, index: int) -> float:
    return _extract_series_value_impl(series, index)


def _fetch_stock_price_from_yfinance(ticker: str) -> Dict[str, Any] | None:
    return _fetch_stock_price_from_yfinance_impl(ticker)


def fetch_stock_price(ticker):
    """
    개별 종목 실시간 가격 수집 (Shared Utility)
    - Toss -> Naver -> yfinance 순서로 폴백

    NOTE:
    테스트에서 provider 함수를 monkeypatch 하므로, 아래 전역 함수명을 직접 참조한다.
    """
    providers = (
        _fetch_stock_price_from_toss,
        _fetch_stock_price_from_naver,
        _fetch_stock_price_from_yfinance,
    )

    for provider in providers:
        try:
            payload = provider(str(ticker).zfill(6))
            if payload:
                return payload
        except Exception as error:
            logger.debug(f"{provider.__name__} failed for {ticker}: {error}")

    return None


def fetch_investor_trend_naver(ticker):
    """
    네이버 증권 API를 통한 최신 날짜 수급 데이터 수집 (Fallback용)
    - 수량(Volume)을 가져와 종가(Close)를 곱하여 금액(Value)으로 추정 반환
    Returns: {'foreign': int, 'institution': int} or None
    """
    return _fetch_investor_trend_naver_impl(ticker)


__all__ = [
    "DataSourceStrategy",
    "FDRSource",
    "PykrxSource",
    "YFinanceSource",
    "DataSourceManager",
    "GlobalDataFetcher",
    "fetch_stock_price",
    "fetch_investor_trend_naver",
    "_build_stock_price_payload",
    "_fetch_stock_price_from_toss",
    "_fetch_stock_price_from_naver",
    "_is_valid_yf_history",
    "_extract_series_value",
    "_fetch_stock_price_from_yfinance",
]
