#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Engine - Global Data Fetcher

글로벌 시세/원자재/크립토 수집 로직을 분리합니다.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, Optional

import pandas as pd

from engine.data_sources_strategies import DataSourceManager

logger = logging.getLogger(__name__)


class GlobalDataFetcher:
    """
    글로벌 데이터 수집기

    지수, 원자재, 크립토 등 다양한 글로벌 데이터를 수집합니다.
    """

    def __init__(self, manager: DataSourceManager | None = None):
        self.manager = manager or DataSourceManager()

    def _collect_series_value_pairs(
        self,
        items: Dict[str, str],
        fetch_fn: Callable[[str], pd.DataFrame],
        data_name: str,
    ) -> Dict[str, Dict[str, Any]]:
        """심볼 맵을 순회하며 유효 가격쌍(value/change_pct)을 수집한다."""
        result: Dict[str, Dict[str, Any]] = {}
        for key, symbol in items.items():
            df = fetch_fn(symbol)
            value_pair = self._extract_valid_value_pair(df, key, data_name)
            if value_pair:
                result[key] = value_pair
        return result

    def _extract_valid_value_pair(
        self,
        df: pd.DataFrame,
        data_key: str,
        data_name: str,
    ) -> Optional[Dict[str, Any]]:
        """
        DataFrame에서 유효한 가격 쌍을 추출하고 변동률 계산

        NaN 및 0 값을 건너뛰고 유효한 최신/이전 데이터 쌍을 찾습니다.

        Args:
            df: 가격 데이터가 포함된 DataFrame
            data_key: 데이터 키 (예: 'sp500', 'gold')
            data_name: 데이터 이름 (로그용)

        Returns:
            {'value': float, 'change_pct': float} 또는 None (유효한 데이터 없음)
        """
        if df.empty or len(df) < 2 or "close" not in df.columns:
            return None

        close_series = pd.to_numeric(df["close"], errors="coerce")
        valid_series = close_series[(close_series.notna()) & (close_series != 0)]
        if len(valid_series) < 2:
            logger.debug(f"{data_name} ({data_key}): Invalid data (NaN or zero)")
            return None

        latest = float(valid_series.iloc[-1])
        prev = float(valid_series.iloc[-2])
        change = ((latest - prev) / prev) * 100 if prev > 0 else 0.0
        return {"value": latest, "change_pct": round(change, 2)}

    def fetch_all_indices(
        self,
        start_date: str,
        end_date: str | None = None,
    ) -> Dict[str, Dict[str, Any]]:
        """
        주요 지수 데이터 수집

        Args:
            start_date: 시작 날짜
            end_date: 종료 날짜

        Returns:
            {key: {'value': float, 'change_pct': float}} 형태의 dict
        """
        indices = {
            "sp500": "^GSPC",
            "nasdaq": "^IXIC",
            "kospi": "^KS11",
            "kosdaq": "^KQ11",
        }

        return self._collect_series_value_pairs(
            indices,
            fetch_fn=lambda symbol: self.manager.fetch_index_data(symbol, start_date, end_date),
            data_name="Index",
        )

    def fetch_commodities(
        self,
        start_date: str,
        end_date: str | None = None,
    ) -> Dict[str, Dict[str, Any]]:
        """
        원자재 데이터 수집

        Args:
            start_date: 시작 날짜
            end_date: 종료 날짜

        Returns:
            {key: {'value': float, 'change_pct': float}} 형태의 dict
        """
        commodities = {
            "gold": "GC=F",
            "silver": "SI=F",
        }

        krx_commodities = {
            "krx_gold": "132030",  # KODEX 골드선물(H)
            "krx_silver": "144600",  # KODEX 은선물(H)
        }

        result = self._collect_series_value_pairs(
            commodities,
            fetch_fn=lambda symbol: self.manager.fetch_index_data(symbol, start_date, end_date),
            data_name="Commodity",
        )
        result.update(
            self._collect_series_value_pairs(
                krx_commodities,
                fetch_fn=lambda ticker: self.manager.fetch_stock_data(ticker, start_date, end_date),
                data_name="KRX Commodity",
            )
        )
        return result

    def fetch_crypto(
        self,
        start_date: str,
        end_date: str | None = None,
    ) -> Dict[str, Dict[str, Any]]:
        """
        크립토 데이터 수집

        Args:
            start_date: 시작 날짜
            end_date: 종료 날짜

        Returns:
            {key: {'value': float, 'change_pct': float}} 형태의 dict
        """
        crypto = {
            "btc": "BTC-USD",
            "eth": "ETH-USD",
            "xrp": "XRP-USD",
        }

        return self._collect_series_value_pairs(
            crypto,
            fetch_fn=lambda symbol: self.manager.fetch_index_data(symbol, start_date, end_date),
            data_name="Crypto",
        )

