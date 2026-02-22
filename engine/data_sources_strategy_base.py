#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Engine - Data Source Strategy Base
"""

from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd


class DataSourceStrategy(ABC):
    """
    데이터 소스 전략 기본 클래스.

    모든 데이터 소스는 이 인터페이스를 구현해야 한다.
    """

    @abstractmethod
    def fetch_index_data(
        self,
        symbol: str,
        start_date: str,
        end_date: str | None = None,
    ) -> pd.DataFrame:
        """지수 데이터 조회."""
        raise NotImplementedError

    @abstractmethod
    def fetch_stock_data(
        self,
        ticker: str,
        start_date: str,
        end_date: str | None = None,
    ) -> pd.DataFrame:
        """종목 데이터 조회."""
        raise NotImplementedError

    @abstractmethod
    def fetch_fx_rate(
        self,
        pair: str = "USD/KRW",
        days: int = 7,
    ) -> pd.DataFrame:
        """환율 데이터 조회."""
        raise NotImplementedError

    @abstractmethod
    def is_available(self) -> bool:
        """데이터 소스 사용 가능 여부 확인."""
        raise NotImplementedError

    def normalize_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """DataFrame 정규화 (컬럼명 통일)."""
        if df.empty:
            return df

        df.columns = [column.lower() for column in df.columns]

        date_cols = ["date", "날짜", "index", "datetime"]
        for col in date_cols:
            if col in df.columns and "date" not in df.columns:
                df.rename(columns={col: "date"}, inplace=True)
                break

        if "종가" in df.columns and "close" not in df.columns:
            df.rename(columns={"종가": "close"}, inplace=True)
        elif "close" not in df.columns and "adj close" in df.columns:
            df.rename(columns={"adj close": "close"}, inplace=True)

        return df


__all__ = ["DataSourceStrategy"]
