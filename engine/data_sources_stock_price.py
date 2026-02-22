#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Engine - Data Sources (Stock Price Fetch Utilities)

실시간 종목 가격/수급 관련 유틸리티를 data_sources.py에서 분리했다.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

import pandas as pd

logger = logging.getLogger(__name__)


def build_stock_price_payload(
    *,
    current: float,
    prev_close: float,
    volume: float,
    source: str,
) -> Dict[str, Any]:
    change_pct = ((current - prev_close) / prev_close) * 100 if prev_close > 0 else 0
    return {
        "price": round(float(current), 0),
        "change_pct": round(float(change_pct), 2),
        "prev_close": round(float(prev_close), 0),
        "volume": int(volume),
        "source": source,
    }


def fetch_stock_price_from_toss(ticker: str) -> Dict[str, Any] | None:
    import requests

    toss_url = (
        "https://wts-info-api.tossinvest.com/api/v3/stock-prices/details"
        f"?productCodes=A{str(ticker).zfill(6)}"
    )
    response = requests.get(toss_url, timeout=3)
    if response.status_code != 200:
        return None

    result = response.json().get("result", [])
    if not result:
        return None

    item = result[0]
    current = float(item.get("close", 0))
    prev_close = float(item.get("base", 0))
    volume = float(item.get("accTradeVolume", 0))
    if current <= 0:
        return None

    return build_stock_price_payload(
        current=current,
        prev_close=prev_close,
        volume=volume,
        source="toss",
    )


def fetch_stock_price_from_naver(ticker: str) -> Dict[str, Any] | None:
    import requests

    naver_url = f"https://m.stock.naver.com/api/stock/{str(ticker).zfill(6)}/basic"
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Referer": "https://m.stock.naver.com/",
    }
    response = requests.get(naver_url, headers=headers, timeout=5)
    if response.status_code != 200:
        return None

    data = response.json()
    close_price = data.get("closePrice")
    if not close_price:
        return None

    current = float(str(close_price).replace(",", ""))
    change_pct = float(data.get("fluctuationsRatio", 0))
    volume = float(str(data.get("accumulatedTradingVolume", "0")).replace(",", ""))
    prev_close = current / (1 + (change_pct / 100)) if change_pct != -100 else 0

    return build_stock_price_payload(
        current=current,
        prev_close=prev_close,
        volume=volume,
        source="naver",
    )


def is_valid_yf_history(hist: pd.DataFrame) -> bool:
    if hist.empty:
        return False
    if isinstance(hist.columns, pd.MultiIndex):
        return "Close" in hist.columns.get_level_values(0)
    return "Close" in hist.columns


def extract_series_value(series: pd.Series, index: int) -> float:
    value = series.iloc[index]
    return float(value.item() if hasattr(value, "item") else value)


def fetch_stock_price_from_yfinance(ticker: str) -> Dict[str, Any] | None:
    import logging as _logging
    import yfinance as yf

    yf_logger = _logging.getLogger("yfinance")
    original_level = yf_logger.level
    yf_logger.setLevel(_logging.CRITICAL)

    try:
        history = pd.DataFrame()
        market_symbol = f"{ticker}.KS"

        try:
            history = yf.download(market_symbol, period="5d", progress=False, threads=False)
        except Exception as error:
            logger.debug(f"yfinance KS fetch failed for {ticker}: {error}")

        if not is_valid_yf_history(history):
            market_symbol = f"{ticker}.KQ"
            try:
                history = yf.download(market_symbol, period="5d", progress=False, threads=False)
            except Exception as error:
                logger.debug(f"yfinance KQ fetch failed for {ticker}: {error}")

        if history.empty:
            return None

        close_series = history["Close"] if "Close" in history.columns else history.iloc[:, 0]
        if isinstance(close_series, pd.DataFrame):
            close_series = close_series.iloc[:, 0]

        if isinstance(history.columns, pd.MultiIndex):
            try:
                volume_series = history["Volume"]
                if isinstance(volume_series, pd.DataFrame):
                    volume_series = volume_series.iloc[:, 0]
            except KeyError:
                volume_series = pd.Series([0] * len(close_series))
        else:
            volume_series = (
                history["Volume"] if "Volume" in history.columns else pd.Series([0] * len(close_series))
            )

        if close_series.empty:
            return None

        current = extract_series_value(close_series, -1)
        prev_close = extract_series_value(close_series, -2) if len(close_series) > 1 else current
        volume = extract_series_value(volume_series, -1) if not volume_series.empty else 0

        return build_stock_price_payload(
            current=current,
            prev_close=prev_close,
            volume=volume,
            source="yfinance",
        )
    finally:
        yf_logger.setLevel(original_level)


def fetch_investor_trend_naver(ticker: str) -> Dict[str, int] | None:
    """
    네이버 증권 API를 통한 최신 날짜 수급 데이터 수집 (Fallback용)
    - 수량(Volume)을 가져와 종가(Close)를 곱하여 금액(Value)으로 추정 반환
    """
    import requests

    try:
        url = f"https://m.stock.naver.com/api/stock/{str(ticker).zfill(6)}/trend"
        headers = {"User-Agent": "Mozilla/5.0"}
        res = requests.get(url, headers=headers, timeout=3)
        if res.status_code == 200:
            data = res.json()
            if isinstance(data, list) and len(data) > 0:
                item = data[0]

                close_str = str(item.get("closePrice", "0")).replace(",", "")
                foreign_str = str(item.get("foreignerPureBuyQuant", "0")).replace(",", "").replace("+", "")
                inst_str = str(item.get("organPureBuyQuant", "0")).replace(",", "").replace("+", "")

                try:
                    close = int(close_str)
                    foreign_vol = int(foreign_str)
                    inst_vol = int(inst_str)
                except (TypeError, ValueError):
                    return None

                return {
                    "foreign": foreign_vol * close,
                    "institution": inst_vol * close,
                }
    except Exception as error:
        logger.debug(f"Naver investor trend fetch failed for {ticker}: {error}")
    return None
