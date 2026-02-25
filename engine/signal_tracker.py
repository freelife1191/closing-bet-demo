#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KR Market - Signal Tracker
실시간 시그널 기록 및 성과 추적 시스템
"""

from __future__ import annotations

import logging
import os
from typing import Optional

import numpy as np
import pandas as pd

from engine.constants import VCP_THRESHOLDS
from engine.signal_tracker_analysis_mixin import SignalTrackerAnalysisMixin
from engine.signal_tracker_source_cache import load_signal_tracker_csv_cached
from services.kr_market_csv_utils import get_ticker_padded_series as _get_ticker_padded_series


logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

PRICE_NUMERIC_COLUMNS = ["close", "current_price", "high", "low", "volume"]


class SignalTracker(SignalTrackerAnalysisMixin):
    """시그널 추적 및 성과 기록."""

    def __init__(self, data_dir: str | None = None):
        self.data_dir = data_dir or os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "data",
        )
        self.signals_log_path = os.path.join(self.data_dir, "signals_log.csv")
        self.performance_path = os.path.join(self.data_dir, "strategy_performance.json")

        self.strategy_params = {
            "foreign_min": 50000,
            "consecutive_min": 3,
            "contraction_max": float(VCP_THRESHOLDS.CONTRACTION_RATIO),
            "near_high_pct": float(VCP_THRESHOLDS.PRICE_NEAR_HIGH_RATIO),
            "hold_days": 5,
            "stop_loss_pct": 7.0,
        }

        self.price_df = self._load_price_data()
        self._price_by_ticker: dict[str, pd.DataFrame] = {}
        self._latest_price_map: dict[str, float] = {}
        self._default_price_col = ""
        self._rebuild_price_cache()
        self._stock_name_map = self._load_stock_name_map()

        logger.info("✅ Signal Tracker 초기화 완료")

    def _load_price_data(self) -> pd.DataFrame:
        """로컬 가격 데이터 로드."""
        price_path = os.path.join(self.data_dir, "daily_prices.csv")
        if not os.path.exists(price_path):
            logger.warning("⚠️ 가격 데이터 파일이 없습니다")
            return pd.DataFrame()

        try:
            df = load_signal_tracker_csv_cached(
                path=price_path,
                cache_kind="daily_prices",
                usecols=["ticker", "date", "close", "current_price", "high", "low", "volume"],
                dtype={"ticker": str},
                read_csv=pd.read_csv,
                logger=logger,
                low_memory=False,
                fallback_without_usecols=True,
                deep_copy=True,
            )
        except Exception as error:
            logger.error(f"가격 데이터 로드 실패: {error}")
            return pd.DataFrame()

        required_cols = {"ticker", "date"}
        if not required_cols.issubset(df.columns):
            logger.warning("⚠️ 가격 데이터 필수 컬럼 누락 (ticker/date)")
            return pd.DataFrame()

        df["ticker"] = _get_ticker_padded_series(df)
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df = df[df["date"].notna()].copy()

        numeric_cols = [col for col in PRICE_NUMERIC_COLUMNS if col in df.columns]
        if numeric_cols:
            df.loc[:, numeric_cols] = df.loc[:, numeric_cols].apply(
                pd.to_numeric,
                errors="coerce",
            )

        df = df.sort_values(["ticker", "date"])
        logger.info(f"   📊 가격 데이터 로드: {len(df):,}개 레코드")
        return df

    def _resolve_default_price_column(self) -> str:
        """기본 가격 컬럼(current_price 우선, 없으면 close)을 결정한다."""
        if "current_price" in self.price_df.columns:
            return "current_price"
        if "close" in self.price_df.columns:
            return "close"
        logger.warning("⚠️ 가격 데이터에 close/current_price 컬럼이 없습니다")
        return ""

    def _build_latest_price_map(self, price_col: str) -> dict[str, float]:
        """ticker별 최신 가격 맵을 벡터화로 계산한다."""
        valid_rows = self.price_df[self.price_df[price_col].notna()]
        if valid_rows.empty:
            return {}

        latest_rows = valid_rows.drop_duplicates(subset=["ticker"], keep="last")
        return latest_rows.set_index("ticker")[price_col].astype(float).to_dict()

    def _rebuild_price_cache(self) -> None:
        """ticker별 가격 시계열/최신가 캐시를 빌드한다."""
        self._price_by_ticker = {}
        self._latest_price_map = {}

        if self.price_df.empty:
            return

        self._default_price_col = self._resolve_default_price_column()
        if not self._default_price_col:
            return

        grouped = self.price_df.groupby("ticker", sort=False)
        self._price_by_ticker = {
            str(ticker): group
            for ticker, group in grouped
            if isinstance(group, pd.DataFrame) and not group.empty
        }
        self._latest_price_map = self._build_latest_price_map(self._default_price_col)

    def _load_stock_name_map(self) -> dict[str, str]:
        """종목 코드 -> 종목명 맵을 로드한다."""
        stocks_path = os.path.join(self.data_dir, "korean_stocks_list.csv")
        if not os.path.exists(stocks_path):
            return {}

        try:
            stocks_info = load_signal_tracker_csv_cached(
                path=stocks_path,
                cache_kind="stock_name_map",
                usecols=["ticker", "name"],
                dtype={"ticker": str},
                read_csv=pd.read_csv,
                logger=logger,
                low_memory=False,
                fallback_without_usecols=True,
                deep_copy=True,
            )
        except Exception as error:
            logger.debug(f"종목명 맵 로드 실패: {error}")
            return {}

        try:
            if "ticker" not in stocks_info.columns or "name" not in stocks_info.columns:
                return {}
            stocks_info["ticker"] = _get_ticker_padded_series(stocks_info)
            return stocks_info.set_index("ticker")["name"].to_dict()
        except Exception as error:
            logger.debug(f"종목명 맵 로드 실패: {error}")
            return {}

    @staticmethod
    def _count_consecutive_positive(values: np.ndarray) -> int:
        """배열 끝에서부터 양수 연속 개수를 센다."""
        count = 0
        for value in values[::-1]:
            if value > 0:
                count += 1
            else:
                break
        return count

    def _get_ticker_prices(self, ticker: str) -> pd.DataFrame:
        return self._price_by_ticker.get(str(ticker).zfill(6), pd.DataFrame())

    @staticmethod
    def _resolve_price_columns(df: pd.DataFrame) -> tuple[str, str, str] | None:
        if "current_price" in df.columns:
            price_col = "current_price"
        elif "close" in df.columns:
            price_col = "close"
        else:
            return None

        high_col = "high" if "high" in df.columns else price_col
        low_col = "low" if "low" in df.columns else price_col
        return price_col, high_col, low_col


def create_tracker(data_dir: str | None = None) -> SignalTracker:
    """SignalTracker 인스턴스 생성 편의 함수."""
    return SignalTracker(data_dir=data_dir)
