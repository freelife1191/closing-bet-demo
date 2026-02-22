#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Engine - Market Gate External Fetchers
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Dict

import pandas as pd


def fetch_benchmark_data(start_date: str, end_date: str, logger: logging.Logger) -> pd.DataFrame:
    """KOSPI 지수 데이터 로드 (RS 계산용)."""
    try:
        try:
            import FinanceDataReader as fdr

            df = fdr.DataReader("KS11", start_date, end_date)
            if not df.empty:
                df = df.reset_index()
                df.columns = [c.lower() for c in df.columns]
                return df[["date", "close"]].rename(columns={"close": "bench_close"})
        except Exception as error:
            logger.debug(f"FDR benchmark fetch failed: {error}")

        return pd.DataFrame()
    except Exception as error:
        logger.warning(f"Benchmark fetch failed: {error}")
        return pd.DataFrame()


def get_global_data(
    *,
    global_fetcher: Any,
    target_date: str | None,
    logger: logging.Logger,
) -> dict:
    """글로벌 시장 데이터(지수/원자재/크립토/환율)를 수집한다."""
    try:
        if target_date:
            dt = datetime.strptime(target_date, "%Y-%m-%d")
            start_date = (dt - timedelta(days=7)).strftime("%Y-%m-%d")
            end_date = (dt + timedelta(days=1)).strftime("%Y-%m-%d")
        else:
            start_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
            end_date = None

        result = {"indices": {}, "commodities": {}, "crypto": {}}

        indices_data = global_fetcher.fetch_all_indices(start_date, end_date)
        result["indices"].update(indices_data)

        commodities_data = global_fetcher.fetch_commodities(start_date, end_date)
        if "gold" in commodities_data:
            result["commodities"]["us_gold"] = commodities_data["gold"]
        if "silver" in commodities_data:
            result["commodities"]["us_silver"] = commodities_data["silver"]
        if "krx_gold" in commodities_data:
            result["commodities"]["krx_gold"] = commodities_data["krx_gold"]
        if "krx_silver" in commodities_data:
            result["commodities"]["krx_silver"] = commodities_data["krx_silver"]

        crypto_data = global_fetcher.fetch_crypto(start_date, end_date)
        result["crypto"].update(crypto_data)

        usd_krw_rate = global_fetcher.manager.get_latest_fx_rate("USD/KRW", default=1400.0)
        usd_krw_change = 0.0
        try:
            fx_df = global_fetcher.manager.fetch_fx_rate("USD/KRW", days=5)
            if not fx_df.empty and len(fx_df) >= 2:
                latest = float(fx_df.iloc[-1]["close"])
                prev = float(fx_df.iloc[-2]["close"])
                usd_krw_change = ((latest - prev) / prev) * 100 if prev > 0 else 0.0
        except Exception as error:
            logger.debug(f"Failed to calculate USD/KRW change: {error}")

        result["usd_krw"] = {"value": usd_krw_rate, "change_pct": round(usd_krw_change, 2)}
        return result
    except Exception as error:
        logger.error(f"Global data fetch error: {error}")
        return {}


def get_sector_data(
    *,
    sectors: Dict[str, str],
    target_date: str | None,
    global_data: dict | None,
    logger: logging.Logger,
) -> dict:
    """주요 섹터 ETF 등락률 수집 (pykrx 사용)."""
    del target_date
    try:
        from pykrx import stock

        now = datetime.now()
        today = now.strftime("%Y%m%d")
        start_date = (now - timedelta(days=5)).strftime("%Y%m%d")

        result: dict[str, float] = {}
        for name, ticker in sectors.items():
            if name == "KOSPI 200" and global_data:
                kospi_indices = global_data.get("indices", {}).get("kospi", {})
                if "change_pct" in kospi_indices:
                    result[name] = kospi_indices["change_pct"]
                    logger.debug(f"Sector {name} synchronized with Global Index: {result[name]}%")
                    continue

            try:
                df = stock.get_market_ohlcv_by_date(start_date, today, ticker)
                if df.empty:
                    result[name] = 0.0
                    continue

                latest = df.iloc[-1]
                if "등락률" in df.columns:
                    result[name] = round(float(latest["등락률"]), 2)
                elif len(df) >= 2:
                    prev = float(df.iloc[-2]["종가"])
                    now_price = float(latest["종가"])
                    result[name] = round(((now_price - prev) / prev) * 100, 2)
                else:
                    result[name] = 0.0
            except Exception as error:
                logger.warning(f"Sector {name} fetch failed: {error}")
                result[name] = 0.0

        return result
    except Exception as error:
        logger.warning(f"Sector data error: {error}")
        return {}


def get_usd_krw(logger: logging.Logger) -> float:
    """환율 조회 (FDR -> yfinance) - 실패 시 1350 반환."""
    try:
        try:
            import FinanceDataReader as fdr

            now = datetime.now()
            start_date = (now - timedelta(days=5)).strftime("%Y-%m-%d")
            df = fdr.DataReader("USD/KRW", start_date)
            if not df.empty:
                latest = df.iloc[-1]
                rate = float(latest["Close"])
                logger.debug(f"FDR 환율 조회 성공: {rate:.2f} 원")
                return rate
        except Exception as error:
            logger.debug(f"FDR 환율 조회 실패: {error}, Trying yfinance...")

        try:
            import logging as _logging
            import yfinance as yf

            yf_logger = _logging.getLogger("yfinance")
            original_level = yf_logger.level
            yf_logger.setLevel(_logging.CRITICAL)

            try:
                ticker = "USDKRW=X"
                hist = yf.download(ticker, period="1d", progress=False, threads=False)

                if isinstance(hist.columns, pd.MultiIndex):
                    try:
                        hist = hist["Close"]
                    except (KeyError, IndexError, TypeError):
                        if "Close" in hist.columns.get_level_values(0):
                            hist = hist.xs("Close", axis=1, level=0, drop_level=True)
                        else:
                            hist = hist.iloc[:, 0]

                if isinstance(hist, pd.DataFrame):
                    if ticker in hist.columns:
                        hist = hist[ticker]
                    elif "Close" in hist.columns:
                        hist = hist["Close"]
                    else:
                        hist = hist.iloc[:, 0]

                if not hist.empty and len(hist) > 0:
                    val = hist.iloc[-1]
                    if hasattr(val, "item"):
                        val = val.item()
                    rate = float(val)
                    logger.debug(f"yfinance 환율 조회 성공: {rate:.2f} 원")
                    return rate
            finally:
                yf_logger.setLevel(original_level)
        except Exception as yf_error:
            logger.debug(f"yfinance 환율 조회 실패: {yf_error}")

        return 1350.0
    except Exception as error:
        logger.warning(f"환율 조회 실패 (기본값 사용): {error}")
        return 1350.0

