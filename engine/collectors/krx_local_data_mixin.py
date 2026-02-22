#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KRX Collector 로컬 fallback/상세 조회 믹스인.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import pandas as pd
from pandas.api.types import is_datetime64_any_dtype

from engine.models import ChartData, StockData, SupplyData
from services.kr_market_data_cache_service import load_csv_file as load_shared_csv_file


logger = logging.getLogger(__name__)


def _get_ticker_padded_series(df: pd.DataFrame) -> pd.Series:
    if "_ticker_padded" in df.columns:
        return df["_ticker_padded"]

    padded = df["ticker"].astype(str).str.zfill(6)
    try:
        df["_ticker_padded"] = padded
        return df["_ticker_padded"]
    except Exception:
        return padded


def _ensure_datetime_column(df: pd.DataFrame, column: str = "date") -> None:
    """date 컬럼이 datetime이 아닐 때만 변환한다."""
    if column not in df.columns:
        return
    if is_datetime64_any_dtype(df[column]):
        return
    df[column] = pd.to_datetime(df[column], errors="coerce")


def _file_signature(path: str) -> tuple[int, int] | None:
    try:
        stat = os.stat(path)
    except OSError:
        return None
    return int(stat.st_mtime_ns), int(stat.st_size)


class KRXCollectorLocalDataMixin:
    """KRXCollector의 로컬 CSV fallback 및 상세/차트/수급 조회를 제공한다."""

    def _get_data_dir(self) -> str:
        cached = getattr(self, "_local_data_dir", None)
        if cached:
            return cached

        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        resolved = os.path.join(base_dir, "data")
        self._local_data_dir = resolved
        return resolved

    def _read_local_csv(
        self,
        filename: str,
        *,
        cache_key: str | None = None,
        deep_copy: bool = True,
        **read_csv_kwargs,
    ) -> pd.DataFrame:
        data_dir = self._get_data_dir()
        path = os.path.join(data_dir, filename)
        file_sig = _file_signature(path)
        if file_sig is None:
            return pd.DataFrame()

        usecols = read_csv_kwargs.get("usecols")
        normalized_usecols: list[str] | None = None
        if isinstance(usecols, (list, tuple)):
            normalized_usecols = [str(column) for column in usecols]
        cache_token = cache_key or filename
        local_cache_key = f"{path}::{cache_token}::{tuple(normalized_usecols) if normalized_usecols is not None else '*'}"
        local_cache = getattr(self, "_local_processed_csv_cache", None)
        if local_cache is None:
            local_cache = {}
            self._local_processed_csv_cache = local_cache
        cached = local_cache.get(local_cache_key)
        if (
            isinstance(cached, dict)
            and cached.get("signature") == file_sig
            and isinstance(cached.get("frame"), pd.DataFrame)
        ):
            cached_frame = cached["frame"]
            return cached_frame.copy(deep=True) if deep_copy else cached_frame

        try:
            loaded = load_shared_csv_file(
                data_dir,
                filename,
                deep_copy=False,
                usecols=normalized_usecols,
                signature=file_sig,
            )
        except ValueError:
            if normalized_usecols is None:
                raise
            logger.debug("KRX local csv usecols mismatch (%s): fallback to full load", filename)
            loaded = load_shared_csv_file(
                data_dir,
                filename,
                deep_copy=False,
                usecols=None,
                signature=file_sig,
            )

        if callable(usecols) and not loaded.empty:
            selected_columns = [column for column in loaded.columns if usecols(column)]
            if selected_columns:
                loaded = loaded.loc[:, selected_columns]

        local_cache[local_cache_key] = {"signature": file_sig, "frame": loaded}
        return loaded.copy(deep=True) if deep_copy else loaded

    def _load_stock_lookup_maps(self) -> tuple[dict[str, str], dict[str, str]]:
        stocks_path = os.path.join(self._get_data_dir(), "korean_stocks_list.csv")
        signature = _file_signature(stocks_path)
        cache = getattr(self, "_stocks_lookup_cache", None)
        if (
            isinstance(cache, dict)
            and cache.get("signature") == signature
        ):
            market_map = cache.get("market_map", {})
            name_map = cache.get("name_map", {})
            if isinstance(market_map, dict) and isinstance(name_map, dict):
                return market_map, name_map

        stocks_df = self._read_local_csv(
            "korean_stocks_list.csv",
            cache_key="stocks_list",
            deep_copy=False,
            usecols=["ticker", "name", "market"],
        )
        market_map: dict[str, str] = {}
        name_map: dict[str, str] = {}
        if not stocks_df.empty and "ticker" in stocks_df.columns:
            tickers = _get_ticker_padded_series(stocks_df)
            if "market" in stocks_df.columns:
                market_map = dict(zip(tickers, stocks_df["market"]))
            if "name" in stocks_df.columns:
                name_map = dict(zip(tickers, stocks_df["name"]))

        self._stocks_lookup_cache = {
            "signature": signature,
            "market_map": market_map,
            "name_map": name_map,
        }
        return market_map, name_map

    def _load_from_local_csv(
        self,
        market: str,
        top_n: int,
        target_date: str = None,
    ) -> List[StockData]:
        """로컬 daily_prices.csv에서 상승률 상위 종목 로드."""
        csv_path = os.path.join(self._get_data_dir(), "daily_prices.csv")

        try:
            df = self._read_local_csv(
                "daily_prices.csv",
                cache_key="daily_prices",
                deep_copy=False,
                usecols=[
                    "ticker",
                    "date",
                    "open",
                    "close",
                    "volume",
                ],
            )
            if df.empty:
                logger.error(f"daily_prices.csv 파일 없음 또는 비어있음: {csv_path}")
                return []

            market_map, name_map = self._load_stock_lookup_maps()

            _ensure_datetime_column(df, "date")
            if target_date:
                if len(str(target_date)) == 8:
                    dt = datetime.strptime(str(target_date), "%Y%m%d")
                else:
                    dt = pd.to_datetime(target_date)

                latest_df = df[df["date"].dt.date == dt.date()].copy()
                if latest_df.empty:
                    logger.warning(f"로컬 CSV에 {target_date} 데이터 없음. 최신 날짜로 대체 시도.")
                    latest_date = df["date"].max()
                    latest_df = df[df["date"] == latest_date].copy()
            else:
                latest_date = df["date"].max()
                latest_df = df[df["date"] == latest_date].copy()

            logger.info(f"로컬 데이터 날짜: {latest_df['date'].max()}")

            latest_df["ticker"] = _get_ticker_padded_series(latest_df)
            latest_df["market_actual"] = latest_df["ticker"].map(market_map)

            logger.info(f"Market Map Size: {len(market_map)}")
            logger.info(f"Before Market Filter: {len(latest_df)} rows")

            latest_df = latest_df[latest_df["market_actual"] == market]
            logger.info(f"After Market Filter ({market}): {len(latest_df)} rows")

            if "change_pct" not in latest_df.columns:
                if "open" in latest_df.columns and "close" in latest_df.columns:
                    latest_df["change_pct"] = (
                        (latest_df["close"] - latest_df["open"]) / latest_df["open"] * 100
                    ).fillna(0)
                else:
                    latest_df["change_pct"] = 0

            if "trading_value" not in latest_df.columns:
                if "volume" in latest_df.columns and "close" in latest_df.columns:
                    latest_df["trading_value"] = latest_df["volume"] * latest_df["close"]
                else:
                    latest_df["trading_value"] = 0
            else:
                latest_df["trading_value"] = latest_df["trading_value"].fillna(0).astype(float)
                mask_zero = latest_df["trading_value"] <= 0
                if mask_zero.any():
                    logger.debug(f"Recalculating 0/NaN trading_value for {mask_zero.sum()} rows")
                    latest_df.loc[mask_zero, "trading_value"] = (
                        latest_df.loc[mask_zero, "volume"] * latest_df.loc[mask_zero, "close"]
                    )

            mask_price = latest_df["close"] >= 1000
            mask_vol = latest_df["trading_value"] >= 1_000_000_000
            mask_rise = latest_df["change_pct"] > 0

            logger.info(f"TopGainers Filter ({market}): Rise={mask_rise.sum()}, ValidVol={mask_vol.sum()}")

            top_df = latest_df[mask_price & mask_vol & mask_rise].nlargest(top_n, "change_pct")

            results = []
            for row in top_df.itertuples(index=False):
                ticker = str(getattr(row, "ticker", "")).zfill(6)
                results.append(
                    StockData(
                        code=ticker,
                        name=name_map.get(ticker, ticker),
                        market=market,
                        sector="",
                        close=int(getattr(row, "close", 0)),
                        change_pct=float(getattr(row, "change_pct", 0.0)),
                        trading_value=float(getattr(row, "trading_value", 0.0)),
                        volume=int(getattr(row, "volume", 0) or 0),
                        marcap=0,
                        high_52w=0,
                        low_52w=0,
                    )
                )

            logger.info(f"로컬 CSV에서 {len(results)}개 종목 로드 완료 ({market})")
            if len(results) == 0:
                logger.warning("로컬 CSV 로드 결과가 0개입니다. 파일 내용을 확인하세요.")
            else:
                for i, item in enumerate(results[:5]):
                    logger.info(f"  [{i+1}] {item.name}: {item.change_pct}%")

            return results

        except Exception as error:
            logger.error(f"로컬 CSV 로드 실패: {error}")
            return []

    async def get_stock_detail(self, code: str) -> Optional[Dict]:
        """종목 상세 정보 조회 (pykrx -> CSV fallback)."""
        name = self._get_stock_name(code)
        high_52w = 0
        low_52w = 0

        try:
            df = self._read_local_csv(
                "daily_prices.csv",
                cache_key="daily_prices_52w",
                deep_copy=False,
                usecols=["ticker", "date", "high", "low"],
            )
            if not df.empty:
                df["ticker"] = _get_ticker_padded_series(df)
                stock_df = df[df["ticker"] == code].copy()

                if not stock_df.empty:
                    _ensure_datetime_column(stock_df, "date")
                    latest_date = stock_df["date"].max()
                    one_year_ago = latest_date - timedelta(days=365)
                    year_df = stock_df[stock_df["date"] >= one_year_ago]

                    if not year_df.empty:
                        high_52w = int(year_df["high"].max())
                        low_52w = int(year_df["low"].min())
        except Exception as error:
            logger.warning(f"52주 신고/신저가 계산 실패 (CSV): {error}")

        return {
            "code": code,
            "name": name,
            "high_52w": high_52w if high_52w > 0 else 0,
            "low_52w": low_52w if low_52w > 0 else 0,
        }

    async def get_chart_data(self, code: str, days: int) -> Optional[ChartData]:
        """차트 데이터 조회 (pykrx -> CSV fallback)."""
        try:
            from pykrx import stock

            end_date_str = self._get_latest_market_date()
            end_date = datetime.strptime(end_date_str, "%Y%m%d")
            start_date = end_date - timedelta(days=int(days * 1.6) + 10)
            start_date_str = start_date.strftime("%Y%m%d")

            df = stock.get_market_ohlcv_by_date(start_date_str, end_date_str, code)
            if not df.empty:
                df = df.tail(days)
                return ChartData(
                    dates=[dt.date() for dt in df.index],
                    opens=df["시가"].tolist(),
                    highs=df["고가"].tolist(),
                    lows=df["저가"].tolist(),
                    closes=df["종가"].tolist(),
                    volumes=df["거래량"].tolist(),
                )
        except Exception as error:
            logger.warning(f"pykrx 차트 조회 실패 ({code}): {error}")

        try:
            df = self._read_local_csv(
                "daily_prices.csv",
                cache_key="daily_prices_chart",
                deep_copy=False,
                usecols=["ticker", "date", "open", "high", "low", "close", "volume"],
            )
            if df.empty:
                return None

            df["ticker"] = _get_ticker_padded_series(df)
            _ensure_datetime_column(df, "date")
            stock_df = df[df["ticker"] == code].sort_values("date")
            if stock_df.empty:
                return None

            stock_df = stock_df.tail(days)
            return ChartData(
                dates=[dt.date() for dt in stock_df["date"]],
                opens=stock_df["open"].tolist(),
                highs=stock_df["high"].tolist(),
                lows=stock_df["low"].tolist(),
                closes=stock_df["close"].tolist(),
                volumes=stock_df["volume"].tolist(),
            )

        except Exception as error:
            logger.error(f"차트 데이터 CSV 조회 실패 ({code}): {error}")
            return None

    async def get_supply_data(self, code: str) -> Optional[SupplyData]:
        """수급 데이터 조회 (pykrx -> CSV fallback)."""
        try:
            from pykrx import stock

            end_date = self._get_latest_market_date()
            end_dt = datetime.strptime(end_date, "%Y%m%d")
            start_date = (end_dt - timedelta(days=10)).strftime("%Y%m%d")

            df = stock.get_market_trading_value_by_date(start_date, end_date, code)
            if not df.empty:
                df = df.tail(5)
                foreign_col = next((col for col in df.columns if "외국인" in col), None)
                inst_col = next((col for col in df.columns if "기관" in col), None)
                retail_col = next((col for col in df.columns if "개인" in col), None)

                return SupplyData(
                    foreign_buy_5d=int(df[foreign_col].sum()) if foreign_col else 0,
                    inst_buy_5d=int(df[inst_col].sum()) if inst_col else 0,
                    retail_buy_5d=int(df[retail_col].sum()) if retail_col else 0,
                )
        except Exception as error:
            logger.warning(f"pykrx 수급 조회 실패 ({code}): {error}")

        try:
            df = self._read_local_csv(
                "all_institutional_trend_data.csv",
                cache_key="institutional_trend_supply",
                deep_copy=False,
                usecols=["ticker", "date", "foreign_buy", "inst_buy"],
            )
            if df.empty:
                return SupplyData(0, 0, 0)
            df["ticker"] = _get_ticker_padded_series(df)
            _ensure_datetime_column(df, "date")

            stock_df = df[df["ticker"] == code].sort_values("date")
            if stock_df.empty:
                return SupplyData(0, 0, 0)

            recent_df = stock_df.tail(5)
            return SupplyData(
                foreign_buy_5d=int(recent_df["foreign_buy"].sum()),
                inst_buy_5d=int(recent_df["inst_buy"].sum()),
                retail_buy_5d=0,
            )

        except Exception as error:
            logger.error(f"수급 데이터 CSV 조회 실패 ({code}): {error}")
            return None
