#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Engine - Data Source Provider Strategies
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

import pandas as pd

from engine.data_sources_strategy_base import DataSourceStrategy


logger = logging.getLogger(__name__)


class FDRSource(DataSourceStrategy):
    """
    FinanceDataReader 데이터 소스.

    한국 시장 데이터에 최적화되어 있으며 신뢰도가 높다.
    """

    def __init__(self) -> None:
        self._available = False
        self._fdr = None
        self._check_availability()

    def _check_availability(self) -> None:
        try:
            import FinanceDataReader as fdr

            self._fdr = fdr
            self._available = True
            logger.debug("FinanceDataReader is available")
        except ImportError:
            self._available = False
            logger.debug("FinanceDataReader not installed")

    def is_available(self) -> bool:
        return self._available

    def fetch_index_data(
        self,
        symbol: str,
        start_date: str,
        end_date: str | None = None,
    ) -> pd.DataFrame:
        if not self.is_available():
            return pd.DataFrame()

        try:
            df = self._fdr.DataReader(symbol, start_date, end_date)
            if not df.empty:
                df = df.reset_index()
                df = self.normalize_dataframe(df)
                return df[["date", "close", "open", "high", "low", "volume"]]
        except Exception as error:
            logger.debug(f"FDR index fetch failed for {symbol}: {error}")

        return pd.DataFrame()

    def fetch_stock_data(
        self,
        ticker: str,
        start_date: str,
        end_date: str | None = None,
    ) -> pd.DataFrame:
        if not self.is_available():
            return pd.DataFrame()

        try:
            df = self._fdr.DataReader(ticker, start_date, end_date)
            if not df.empty:
                df = df.reset_index()
                df = self.normalize_dataframe(df)
                return df[["date", "close", "open", "high", "low", "volume"]]
        except Exception as error:
            logger.debug(f"FDR stock fetch failed for {ticker}: {error}")

        return pd.DataFrame()

    def fetch_fx_rate(
        self,
        pair: str = "USD/KRW",
        days: int = 7,
    ) -> pd.DataFrame:
        if not self.is_available():
            return pd.DataFrame()

        try:
            start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
            df = self._fdr.DataReader(pair, start_date)
            if not df.empty:
                df = df.reset_index()
                df = self.normalize_dataframe(df)
                return df[["date", "close"]]
        except Exception as error:
            logger.debug(f"FDR FX fetch failed for {pair}: {error}")

        return pd.DataFrame()


class PykrxSource(DataSourceStrategy):
    """
    pykrx 데이터 소스.

    KRX 공식 데이터 제공, 한국 시장 전용
    """

    def __init__(self) -> None:
        self._available = False
        self._stock = None
        self._check_availability()

    def _check_availability(self) -> None:
        try:
            from pykrx import stock

            self._stock = stock
            self._available = True
            logger.debug("pykrx is available")
        except ImportError:
            self._available = False
            logger.debug("pykrx not installed")

    def is_available(self) -> bool:
        return self._available

    def fetch_index_data(
        self,
        symbol: str,
        start_date: str,
        end_date: str | None = None,
    ) -> pd.DataFrame:
        if not self.is_available():
            return pd.DataFrame()

        try:
            start_str = start_date.replace("-", "")
            end_str = end_date.replace("-", "") if end_date else datetime.now().strftime("%Y%m%d")

            code_map = {"KS11": "1001", "KQ11": "2001"}
            ticker_code = code_map.get(symbol, symbol)

            df = self._stock.get_index_ohlcv_by_date(start_str, end_str, ticker_code)
            if not df.empty:
                df = df.reset_index()
                df = self.normalize_dataframe(df)
                return df[["date", "close", "open", "high", "low", "volume"]]
        except Exception as error:
            logger.debug(f"pykrx index fetch failed for {symbol}: {error}")

        return pd.DataFrame()

    def fetch_stock_data(
        self,
        ticker: str,
        start_date: str,
        end_date: str | None = None,
    ) -> pd.DataFrame:
        if not self.is_available():
            return pd.DataFrame()

        try:
            start_str = start_date.replace("-", "")
            end_str = end_date.replace("-", "") if end_date else datetime.now().strftime("%Y%m%d")

            df = self._stock.get_market_ohlcv_by_date(start_str, end_str, ticker)
            if not df.empty:
                df = df.reset_index()
                df = self.normalize_dataframe(df)
                return df[["date", "close", "open", "high", "low", "volume"]]
        except Exception as error:
            logger.debug(f"pykrx stock fetch failed for {ticker}: {error}")

        return pd.DataFrame()

    def fetch_fx_rate(self, pair: str = "USD/KRW", days: int = 7) -> pd.DataFrame:
        del pair, days
        return pd.DataFrame()


class YFinanceSource(DataSourceStrategy):
    """
    yfinance 데이터 소스.

    글로벌 지수, 원자재, 크립토 데이터에 사용
    """

    def __init__(self) -> None:
        self._available = False
        self._yf = None
        self._check_availability()

    def _check_availability(self) -> None:
        try:
            import yfinance as yf

            self._yf = yf
            self._available = True
            logger.debug("yfinance is available")
        except ImportError:
            self._available = False
            logger.debug("yfinance not installed")

    def is_available(self) -> bool:
        return self._available

    def fetch_index_data(
        self,
        symbol: str,
        start_date: str,
        end_date: str | None = None,
    ) -> pd.DataFrame:
        if not self.is_available():
            return pd.DataFrame()

        try:
            df = self._yf.download(
                symbol,
                start=start_date,
                end=end_date,
                progress=False,
                threads=False,
            )

            if not df.empty:
                df = df.reset_index()
                df = self.normalize_dataframe(df)
                return df[["date", "close", "open", "high", "low", "volume"]]
        except Exception as error:
            logger.debug(f"yfinance index fetch failed for {symbol}: {error}")

        return pd.DataFrame()

    def fetch_stock_data(
        self,
        ticker: str,
        start_date: str,
        end_date: str | None = None,
    ) -> pd.DataFrame:
        return self.fetch_index_data(ticker, start_date, end_date)

    def fetch_fx_rate(
        self,
        pair: str = "USDKRW=X",
        days: int = 7,
    ) -> pd.DataFrame:
        if not self.is_available():
            return pd.DataFrame()

        try:
            symbol_map = {"USD/KRW": "USDKRW=X"}
            symbol = symbol_map.get(pair, pair)
            start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

            df = self._yf.download(
                symbol,
                start=start_date,
                progress=False,
                threads=False,
            )

            if not df.empty:
                df = df.reset_index()
                df = self.normalize_dataframe(df)
                return df[["date", "close"]]
        except Exception as error:
            logger.debug(f"yfinance FX fetch failed for {pair}: {error}")

        return pd.DataFrame()


__all__ = [
    "FDRSource",
    "PykrxSource",
    "YFinanceSource",
]
