#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Engine - Data Source Fallback Manager
"""

from __future__ import annotations

import logging
from typing import List

import pandas as pd

from engine.data_sources_provider_strategies import FDRSource, PykrxSource, YFinanceSource
from engine.data_sources_strategy_base import DataSourceStrategy


logger = logging.getLogger(__name__)


class DataSourceManager:
    """
    데이터 소스 매니저.

    여러 데이터 소스를 순차적으로 시도하는 폴백 체인을 구현한다.
    """

    def __init__(self, sources: List[DataSourceStrategy] | None = None):
        if sources is None:
            sources = [
                FDRSource(),
                PykrxSource(),
                YFinanceSource(),
            ]
        self.sources = sources

    def fetch_with_fallback(
        self,
        fetch_method: str,
        *args,
        **kwargs,
    ) -> pd.DataFrame:
        """폴백 체인을 통해 데이터 조회."""
        for source in self.sources:
            if not source.is_available():
                continue

            try:
                method = getattr(source, fetch_method, None)
                if method:
                    df = method(*args, **kwargs)
                    if not df.empty:
                        logger.debug(f"Data fetched from {source.__class__.__name__}")
                        return df
            except Exception as error:
                logger.debug(f"{source.__class__.__name__} failed: {error}")
                continue

        logger.warning(f"All data sources failed for {fetch_method}")
        return pd.DataFrame()

    def fetch_index_data(
        self,
        symbol: str,
        start_date: str,
        end_date: str | None = None,
    ) -> pd.DataFrame:
        """지수 데이터 조회 (폴백 포함)."""
        return self.fetch_with_fallback("fetch_index_data", symbol, start_date, end_date)

    def fetch_stock_data(
        self,
        ticker: str,
        start_date: str,
        end_date: str | None = None,
    ) -> pd.DataFrame:
        """종목 데이터 조회 (폴백 포함)."""
        return self.fetch_with_fallback("fetch_stock_data", ticker, start_date, end_date)

    def fetch_fx_rate(
        self,
        pair: str = "USD/KRW",
        days: int = 7,
    ) -> pd.DataFrame:
        """환율 데이터 조회 (폴백 포함)."""
        return self.fetch_with_fallback("fetch_fx_rate", pair, days)

    def get_latest_fx_rate(self, pair: str = "USD/KRW", default: float = 1350.0) -> float:
        """최신 환율 조회."""
        df = self.fetch_fx_rate(pair)
        if not df.empty:
            latest = df.iloc[-1]["close"]
            try:
                return float(latest)
            except (ValueError, TypeError):
                pass

        return default


__all__ = ["DataSourceManager"]
