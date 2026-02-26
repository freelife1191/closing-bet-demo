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
from services.kr_market_data_cache_sqlite_payload import (
    load_json_payload_from_sqlite as _load_json_payload_from_sqlite,
    save_json_payload_to_sqlite as _save_json_payload_to_sqlite,
)
from services.investor_trend_5day_service import (
    get_investor_trend_5day_for_ticker,
)


logger = logging.getLogger(__name__)
_SUPPLY_SUMMARY_SQLITE_MAX_ROWS = 256
_SUPPLY_SUMMARY_SQLITE_CACHE_KEY_SUFFIX = "::krx_supply_summary_5d"
_STOCK_LOOKUP_SQLITE_MAX_ROWS = 256
_STOCK_LOOKUP_SQLITE_CACHE_KEY_SUFFIX = "::krx_stock_lookup_maps"
_TOP_GAINERS_SQLITE_MAX_ROWS = 512
_TOP_GAINERS_SQLITE_CACHE_KEY_SUFFIX = "::krx_top_gainers"
_PYKRX_TOP_GAINERS_SQLITE_MAX_ROWS = 512
_PYKRX_TOP_GAINERS_SQLITE_CACHE_KEY_SUFFIX = "::krx_pykrx_top_gainers"
_PYKRX_SUPPLY_SUMMARY_SQLITE_MAX_ROWS = 2_048
_PYKRX_SUPPLY_SUMMARY_SQLITE_CACHE_KEY_SUFFIX = "::krx_pykrx_supply_summary_5d"
_PYKRX_CHART_SQLITE_MAX_ROWS = 2_048
_PYKRX_CHART_SQLITE_CACHE_KEY_SUFFIX = "::krx_pykrx_chart"


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


def _project_existing_usecols_columns(
    df: pd.DataFrame,
    usecols: list[str] | tuple[str, ...] | None,
) -> pd.DataFrame:
    """usecols 불일치 fallback 이후 존재 컬럼만 투영해 메모리 사용을 줄인다."""
    if usecols is None:
        return df
    existing_columns = [str(column) for column in usecols if str(column) in df.columns]
    if not existing_columns:
        return df
    return df.loc[:, existing_columns]


def _file_signature(path: str) -> tuple[int, int] | None:
    try:
        stat = os.stat(path)
    except OSError:
        return None
    return int(stat.st_mtime_ns), int(stat.st_size)


def _supply_summary_sqlite_cache_key(trend_path: str) -> str:
    normalized_path = os.path.abspath(trend_path)
    return f"{normalized_path}{_SUPPLY_SUMMARY_SQLITE_CACHE_KEY_SUFFIX}"


def _stock_lookup_sqlite_cache_key(stocks_path: str) -> str:
    normalized_path = os.path.abspath(stocks_path)
    return f"{normalized_path}{_STOCK_LOOKUP_SQLITE_CACHE_KEY_SUFFIX}"


def _stable_token_to_int(token: str) -> int:
    normalized = str(token or "")
    if normalized.isdigit():
        try:
            return int(normalized)
        except Exception:
            pass
    acc = 17
    for ch in normalized:
        acc = (acc * 31 + ord(ch)) % 2_000_000_000
    return int(acc)


def _normalize_top_gainers_target_key(target_date: str | None) -> str:
    normalized_target = str(target_date or "").strip()
    if not normalized_target:
        return "latest"
    return normalized_target


def _top_gainers_sqlite_cache_key(
    *,
    csv_path: str,
    market: str,
    top_n: int,
    target_date: str | None,
    min_change_pct: float,
) -> str:
    normalized_path = os.path.abspath(csv_path)
    target_key = _normalize_top_gainers_target_key(target_date)
    market_key = str(market or "").strip().upper()
    return (
        f"{normalized_path}{_TOP_GAINERS_SQLITE_CACHE_KEY_SUFFIX}"
        f"::{market_key}::{target_key}::{int(top_n)}::{float(min_change_pct):.6f}"
    )


def _top_gainers_sqlite_signature(
    *,
    daily_signature: tuple[int, int] | None,
    stocks_signature: tuple[int, int] | None,
) -> tuple[int, int]:
    daily_token = f"{int(daily_signature[0])}:{int(daily_signature[1])}" if daily_signature else "0:0"
    stocks_token = f"{int(stocks_signature[0])}:{int(stocks_signature[1])}" if stocks_signature else "0:0"
    return (
        _stable_token_to_int(daily_token),
        _stable_token_to_int(stocks_token),
    )


def _pykrx_top_gainers_sqlite_cache_key(
    *,
    data_dir: str,
    market: str,
    top_n: int,
    target_date: str,
    min_change_pct: float,
) -> str:
    normalized_dir = os.path.abspath(data_dir)
    normalized_market = str(market or "").strip().upper()
    target_key = _normalize_top_gainers_target_key(target_date)
    return (
        f"{normalized_dir}{_PYKRX_TOP_GAINERS_SQLITE_CACHE_KEY_SUFFIX}"
        f"::{normalized_market}::{target_key}::{int(top_n)}::{float(min_change_pct):.6f}"
    )


def _pykrx_top_gainers_sqlite_signature(
    *,
    market: str,
    top_n: int,
    target_date: str,
    min_change_pct: float,
) -> tuple[int, int]:
    signature_seed = (
        f"{str(market or '').strip().upper()}::{_normalize_top_gainers_target_key(target_date)}"
        f"::{int(top_n)}::{float(min_change_pct):.6f}"
    )
    return (
        _stable_token_to_int(signature_seed),
        _stable_token_to_int(f"pykrx_top::{signature_seed[::-1]}"),
    )


def _serialize_top_gainers(
    results: list[StockData],
) -> dict[str, object]:
    rows: list[dict[str, object]] = []
    for item in results:
        rows.append(
            {
                "code": str(item.code).zfill(6),
                "name": str(item.name),
                "market": str(item.market),
                "sector": str(item.sector),
                "close": int(item.close),
                "change_pct": float(item.change_pct),
                "trading_value": float(item.trading_value),
                "volume": int(item.volume),
                "marcap": int(item.marcap),
                "high_52w": int(item.high_52w),
                "low_52w": int(item.low_52w),
            }
        )
    return {"rows": rows}


def _deserialize_top_gainers(
    payload: dict[str, object],
) -> list[StockData] | None:
    rows_payload = payload.get("rows")
    if not isinstance(rows_payload, list):
        return None

    results: list[StockData] = []
    for row in rows_payload:
        if not isinstance(row, dict):
            continue
        try:
            results.append(
                StockData(
                    code=str(row.get("code", "")).zfill(6),
                    name=str(row.get("name", "")),
                    market=str(row.get("market", "")),
                    sector=str(row.get("sector", "")),
                    close=int(float(row.get("close", 0))),
                    change_pct=float(row.get("change_pct", 0.0)),
                    trading_value=float(row.get("trading_value", 0.0)),
                    volume=int(float(row.get("volume", 0))),
                    marcap=int(float(row.get("marcap", 0))),
                    high_52w=int(float(row.get("high_52w", 0))),
                    low_52w=int(float(row.get("low_52w", 0))),
                )
            )
        except (TypeError, ValueError):
            continue
    return results


def _pykrx_supply_sqlite_cache_key(
    *,
    data_dir: str,
    ticker: str,
    end_date: str,
) -> str:
    normalized_dir = os.path.abspath(data_dir)
    ticker_key = str(ticker).zfill(6)
    end_date_key = _normalize_top_gainers_target_key(end_date)
    return (
        f"{normalized_dir}{_PYKRX_SUPPLY_SUMMARY_SQLITE_CACHE_KEY_SUFFIX}"
        f"::{ticker_key}::{end_date_key}"
    )


def _pykrx_supply_sqlite_signature(*, ticker: str, end_date: str) -> tuple[int, int]:
    ticker_key = str(ticker).zfill(6)
    end_date_key = _normalize_top_gainers_target_key(end_date)
    seed = f"{ticker_key}::{end_date_key}::pykrx_supply_5d"
    return (
        _stable_token_to_int(seed),
        _stable_token_to_int(f"pykrx_supply::{seed[::-1]}"),
    )


def _normalize_pykrx_supply_payload(payload: dict[str, object]) -> dict[str, int] | None:
    try:
        foreign_value = int(float(payload.get("foreign_buy_5d", 0)))
        inst_value = int(float(payload.get("inst_buy_5d", 0)))
        retail_value = int(float(payload.get("retail_buy_5d", 0)))
    except (TypeError, ValueError):
        return None
    return {
        "foreign_buy_5d": foreign_value,
        "inst_buy_5d": inst_value,
        "retail_buy_5d": retail_value,
    }


def _pykrx_chart_sqlite_cache_key(
    *,
    data_dir: str,
    ticker: str,
    end_date: str,
    days: int,
) -> str:
    normalized_dir = os.path.abspath(data_dir)
    ticker_key = str(ticker).zfill(6)
    end_date_key = _normalize_top_gainers_target_key(end_date)
    return (
        f"{normalized_dir}{_PYKRX_CHART_SQLITE_CACHE_KEY_SUFFIX}"
        f"::{ticker_key}::{end_date_key}::{int(days)}"
    )


def _pykrx_chart_sqlite_signature(
    *,
    ticker: str,
    end_date: str,
    days: int,
) -> tuple[int, int]:
    ticker_key = str(ticker).zfill(6)
    end_date_key = _normalize_top_gainers_target_key(end_date)
    seed = f"{ticker_key}::{end_date_key}::{int(days)}::pykrx_chart"
    return (
        _stable_token_to_int(seed),
        _stable_token_to_int(f"pykrx_chart::{seed[::-1]}"),
    )


def _serialize_chart_data(chart: ChartData) -> dict[str, object]:
    date_tokens = []
    for dt in chart.dates:
        if hasattr(dt, "isoformat"):
            date_tokens.append(str(dt.isoformat()))
        else:
            date_tokens.append(str(dt))
    return {
        "dates": date_tokens,
        "opens": [float(value) for value in chart.opens],
        "highs": [float(value) for value in chart.highs],
        "lows": [float(value) for value in chart.lows],
        "closes": [float(value) for value in chart.closes],
        "volumes": [float(value) for value in chart.volumes],
    }


def _deserialize_chart_data(payload: dict[str, object]) -> ChartData | None:
    dates_payload = payload.get("dates")
    opens_payload = payload.get("opens")
    highs_payload = payload.get("highs")
    lows_payload = payload.get("lows")
    closes_payload = payload.get("closes")
    volumes_payload = payload.get("volumes")
    if not all(
        isinstance(item, list)
        for item in (dates_payload, opens_payload, highs_payload, lows_payload, closes_payload, volumes_payload)
    ):
        return None

    series_lengths = [
        len(dates_payload),
        len(opens_payload),
        len(highs_payload),
        len(lows_payload),
        len(closes_payload),
        len(volumes_payload),
    ]
    if not series_lengths or min(series_lengths) <= 0 or len(set(series_lengths)) != 1:
        return None

    dates = []
    for token in dates_payload:
        try:
            dates.append(pd.to_datetime(token, errors="raise").date())
        except Exception:
            return None
    try:
        return ChartData(
            dates=dates,
            opens=[float(value) for value in opens_payload],
            highs=[float(value) for value in highs_payload],
            lows=[float(value) for value in lows_payload],
            closes=[float(value) for value in closes_payload],
            volumes=[float(value) for value in volumes_payload],
        )
    except (TypeError, ValueError):
        return None


def _serialize_supply_summary_map(
    summary_map: dict[str, tuple[int, int]],
) -> dict[str, object]:
    rows: dict[str, list[int]] = {}
    for ticker, values in summary_map.items():
        if not isinstance(values, tuple) or len(values) != 2:
            continue
        foreign_value, inst_value = values
        rows[str(ticker).zfill(6)] = [int(foreign_value), int(inst_value)]
    return {"rows": rows}


def _deserialize_supply_summary_map(
    payload: dict[str, object],
) -> dict[str, tuple[int, int]] | None:
    rows_payload = payload.get("rows")
    if not isinstance(rows_payload, dict):
        return None

    summary_map: dict[str, tuple[int, int]] = {}
    for ticker, values in rows_payload.items():
        ticker_key = str(ticker).zfill(6)
        if not ticker_key:
            continue
        if not isinstance(values, (list, tuple)) or len(values) != 2:
            continue
        try:
            foreign_value = int(float(values[0]))
            inst_value = int(float(values[1]))
        except (TypeError, ValueError):
            continue
        summary_map[ticker_key] = (foreign_value, inst_value)
    return summary_map


def _serialize_stock_lookup_maps(
    market_map: dict[str, str],
    name_map: dict[str, str],
) -> dict[str, object]:
    return {
        "market_map": {str(key).zfill(6): str(value) for key, value in market_map.items()},
        "name_map": {str(key).zfill(6): str(value) for key, value in name_map.items()},
    }


def _deserialize_stock_lookup_maps(
    payload: dict[str, object],
) -> tuple[dict[str, str], dict[str, str]] | None:
    market_payload = payload.get("market_map")
    name_payload = payload.get("name_map")
    if not isinstance(market_payload, dict) or not isinstance(name_payload, dict):
        return None

    market_map: dict[str, str] = {}
    for ticker, value in market_payload.items():
        ticker_key = str(ticker).zfill(6)
        if ticker_key:
            market_map[ticker_key] = str(value)

    name_map: dict[str, str] = {}
    for ticker, value in name_payload.items():
        ticker_key = str(ticker).zfill(6)
        if ticker_key:
            name_map[ticker_key] = str(value)

    return market_map, name_map


def _build_recent_supply_sum_map(df: pd.DataFrame) -> dict[str, tuple[int, int]]:
    """ticker별 최근 5거래일 외인/기관 합산 맵을 계산한다."""
    if df.empty:
        return {}
    if "ticker" not in df.columns:
        return {}
    if "foreign_buy" not in df.columns or "inst_buy" not in df.columns:
        return {}

    working = df
    working["ticker"] = _get_ticker_padded_series(working)
    _ensure_datetime_column(working, "date")
    working["foreign_buy"] = pd.to_numeric(working["foreign_buy"], errors="coerce").fillna(0)
    working["inst_buy"] = pd.to_numeric(working["inst_buy"], errors="coerce").fillna(0)

    if "date" in working.columns:
        working = working[working["date"].notna()]
        if working.empty:
            return {}
        working = working.sort_values(["ticker", "date"])
    else:
        working = working.sort_values(["ticker"])

    recent_df = working.groupby("ticker", sort=False).tail(5)
    if recent_df.empty:
        return {}

    grouped = recent_df.groupby("ticker", sort=False).agg(
        foreign_buy_5d=("foreign_buy", "sum"),
        inst_buy_5d=("inst_buy", "sum"),
    )
    return {
        str(ticker).zfill(6): (int(foreign_sum), int(inst_sum))
        for ticker, foreign_sum, inst_sum in grouped.itertuples()
    }


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

    @staticmethod
    def _has_csv_anomaly_flags(trend_data: dict[str, object] | None) -> bool:
        if not isinstance(trend_data, dict):
            return False
        quality = trend_data.get("quality")
        if not isinstance(quality, dict):
            return False
        csv_flags = quality.get("csv_anomaly_flags")
        return isinstance(csv_flags, list) and len(csv_flags) > 0

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
            loaded = _project_existing_usecols_columns(loaded, normalized_usecols)

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

        sqlite_cache_key = _stock_lookup_sqlite_cache_key(stocks_path)
        if signature is not None:
            try:
                loaded, payload = _load_json_payload_from_sqlite(
                    filepath=sqlite_cache_key,
                    signature=signature,
                    logger=logger,
                )
            except Exception as error:
                logger.debug("Failed to load stock lookup SQLite cache: %s", error)
            else:
                if loaded and isinstance(payload, dict):
                    deserialized = _deserialize_stock_lookup_maps(payload)
                    if deserialized is not None:
                        market_map, name_map = deserialized
                        self._stocks_lookup_cache = {
                            "signature": signature,
                            "market_map": market_map,
                            "name_map": name_map,
                        }
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
        if signature is not None:
            try:
                _save_json_payload_to_sqlite(
                    filepath=sqlite_cache_key,
                    signature=signature,
                    payload=_serialize_stock_lookup_maps(market_map, name_map),
                    max_rows=_STOCK_LOOKUP_SQLITE_MAX_ROWS,
                    logger=logger,
                )
            except Exception as error:
                logger.debug("Failed to save stock lookup SQLite cache: %s", error)
        return market_map, name_map

    def _load_supply_summary_map(self) -> dict[str, tuple[int, int]]:
        """
        수급 CSV에서 ticker별 최근 5거래일 합산 맵을 시그니처 기반으로 캐시한다.

        CSV 로드는 공통 SQLite-backed load_shared_csv_file 경로를 통해 수행된다.
        """
        trend_path = os.path.join(self._get_data_dir(), "all_institutional_trend_data.csv")
        signature = _file_signature(trend_path)
        cache = getattr(self, "_supply_summary_cache", None)
        if (
            isinstance(cache, dict)
            and cache.get("signature") == signature
            and isinstance(cache.get("map"), dict)
        ):
            return cache["map"]

        sqlite_cache_key = _supply_summary_sqlite_cache_key(trend_path)
        if signature is not None:
            try:
                loaded, payload = _load_json_payload_from_sqlite(
                    filepath=sqlite_cache_key,
                    signature=signature,
                    logger=logger,
                )
            except Exception as error:
                logger.debug("Failed to load supply summary SQLite cache: %s", error)
            else:
                if loaded and isinstance(payload, dict):
                    summary_map = _deserialize_supply_summary_map(payload)
                    if summary_map is not None:
                        self._supply_summary_cache = {
                            "signature": signature,
                            "map": summary_map,
                        }
                        return summary_map

        trend_df = self._read_local_csv(
            "all_institutional_trend_data.csv",
            cache_key="institutional_trend_supply",
            deep_copy=False,
            usecols=["ticker", "date", "foreign_buy", "inst_buy"],
        )
        summary_map = _build_recent_supply_sum_map(trend_df)
        self._supply_summary_cache = {
            "signature": signature,
            "map": summary_map,
        }
        if signature is not None:
            try:
                _save_json_payload_to_sqlite(
                    filepath=sqlite_cache_key,
                    signature=signature,
                    payload=_serialize_supply_summary_map(summary_map),
                    max_rows=_SUPPLY_SUMMARY_SQLITE_MAX_ROWS,
                    logger=logger,
                )
            except Exception as error:
                logger.debug("Failed to save supply summary SQLite cache: %s", error)
        return summary_map

    def _load_pykrx_top_gainers_snapshot(
        self,
        *,
        market: str,
        top_n: int,
        target_date: str,
        min_change_pct: float,
    ) -> list[StockData] | None:
        data_dir = self._get_data_dir()
        normalized_market = str(market or "").strip().upper()
        target_key = _normalize_top_gainers_target_key(target_date)
        memory_key = (
            normalized_market,
            int(top_n),
            target_key,
            float(min_change_pct),
        )

        memory_cache = getattr(self, "_pykrx_top_gainers_cache", None)
        if isinstance(memory_cache, dict):
            cached = memory_cache.get(memory_key)
            if isinstance(cached, list):
                return list(cached)

        sqlite_cache_key = _pykrx_top_gainers_sqlite_cache_key(
            data_dir=data_dir,
            market=normalized_market,
            top_n=top_n,
            target_date=target_key,
            min_change_pct=min_change_pct,
        )
        sqlite_signature = _pykrx_top_gainers_sqlite_signature(
            market=normalized_market,
            top_n=top_n,
            target_date=target_key,
            min_change_pct=min_change_pct,
        )
        try:
            loaded, payload = _load_json_payload_from_sqlite(
                filepath=sqlite_cache_key,
                signature=sqlite_signature,
                logger=logger,
            )
        except Exception as error:
            logger.debug("Failed to load pykrx top gainers SQLite cache: %s", error)
            return None

        if not loaded or not isinstance(payload, dict):
            return None
        deserialized = _deserialize_top_gainers(payload)
        if deserialized is None:
            return None

        if not isinstance(memory_cache, dict):
            memory_cache = {}
            self._pykrx_top_gainers_cache = memory_cache
        memory_cache[memory_key] = list(deserialized)
        return deserialized

    def _save_pykrx_top_gainers_snapshot(
        self,
        *,
        market: str,
        top_n: int,
        target_date: str,
        min_change_pct: float,
        results: list[StockData],
    ) -> None:
        data_dir = self._get_data_dir()
        normalized_market = str(market or "").strip().upper()
        target_key = _normalize_top_gainers_target_key(target_date)
        memory_key = (
            normalized_market,
            int(top_n),
            target_key,
            float(min_change_pct),
        )

        memory_cache = getattr(self, "_pykrx_top_gainers_cache", None)
        if not isinstance(memory_cache, dict):
            memory_cache = {}
            self._pykrx_top_gainers_cache = memory_cache
        memory_cache[memory_key] = list(results)

        sqlite_cache_key = _pykrx_top_gainers_sqlite_cache_key(
            data_dir=data_dir,
            market=normalized_market,
            top_n=top_n,
            target_date=target_key,
            min_change_pct=min_change_pct,
        )
        sqlite_signature = _pykrx_top_gainers_sqlite_signature(
            market=normalized_market,
            top_n=top_n,
            target_date=target_key,
            min_change_pct=min_change_pct,
        )
        try:
            _save_json_payload_to_sqlite(
                filepath=sqlite_cache_key,
                signature=sqlite_signature,
                payload=_serialize_top_gainers(results),
                max_rows=_PYKRX_TOP_GAINERS_SQLITE_MAX_ROWS,
                logger=logger,
            )
        except Exception as error:
            logger.debug("Failed to save pykrx top gainers SQLite cache: %s", error)

    def _load_pykrx_supply_summary_snapshot(
        self,
        *,
        ticker: str,
        end_date: str,
    ) -> dict[str, int] | None:
        data_dir = self._get_data_dir()
        ticker_key = str(ticker).zfill(6)
        end_date_key = _normalize_top_gainers_target_key(end_date)
        memory_key = (ticker_key, end_date_key)

        memory_cache = getattr(self, "_pykrx_supply_summary_cache", None)
        if isinstance(memory_cache, dict):
            cached = memory_cache.get(memory_key)
            if isinstance(cached, dict):
                return dict(cached)

        sqlite_cache_key = _pykrx_supply_sqlite_cache_key(
            data_dir=data_dir,
            ticker=ticker_key,
            end_date=end_date_key,
        )
        sqlite_signature = _pykrx_supply_sqlite_signature(
            ticker=ticker_key,
            end_date=end_date_key,
        )
        try:
            loaded, payload = _load_json_payload_from_sqlite(
                filepath=sqlite_cache_key,
                signature=sqlite_signature,
                logger=logger,
            )
        except Exception as error:
            logger.debug("Failed to load pykrx supply SQLite cache: %s", error)
            return None

        if not loaded or not isinstance(payload, dict):
            return None
        normalized_payload = _normalize_pykrx_supply_payload(payload)
        if normalized_payload is None:
            return None

        if not isinstance(memory_cache, dict):
            memory_cache = {}
            self._pykrx_supply_summary_cache = memory_cache
        memory_cache[memory_key] = dict(normalized_payload)
        return dict(normalized_payload)

    def _save_pykrx_supply_summary_snapshot(
        self,
        *,
        ticker: str,
        end_date: str,
        payload: dict[str, object],
    ) -> None:
        normalized_payload = _normalize_pykrx_supply_payload(payload)
        if normalized_payload is None:
            return

        data_dir = self._get_data_dir()
        ticker_key = str(ticker).zfill(6)
        end_date_key = _normalize_top_gainers_target_key(end_date)
        memory_key = (ticker_key, end_date_key)

        memory_cache = getattr(self, "_pykrx_supply_summary_cache", None)
        if not isinstance(memory_cache, dict):
            memory_cache = {}
            self._pykrx_supply_summary_cache = memory_cache
        memory_cache[memory_key] = dict(normalized_payload)

        sqlite_cache_key = _pykrx_supply_sqlite_cache_key(
            data_dir=data_dir,
            ticker=ticker_key,
            end_date=end_date_key,
        )
        sqlite_signature = _pykrx_supply_sqlite_signature(
            ticker=ticker_key,
            end_date=end_date_key,
        )
        try:
            _save_json_payload_to_sqlite(
                filepath=sqlite_cache_key,
                signature=sqlite_signature,
                payload=normalized_payload,
                max_rows=_PYKRX_SUPPLY_SUMMARY_SQLITE_MAX_ROWS,
                logger=logger,
            )
        except Exception as error:
            logger.debug("Failed to save pykrx supply SQLite cache: %s", error)

    def _load_pykrx_chart_snapshot(
        self,
        *,
        ticker: str,
        end_date: str,
        days: int,
    ) -> ChartData | None:
        data_dir = self._get_data_dir()
        ticker_key = str(ticker).zfill(6)
        end_date_key = _normalize_top_gainers_target_key(end_date)
        memory_key = (ticker_key, end_date_key, int(days))

        memory_cache = getattr(self, "_pykrx_chart_cache", None)
        if isinstance(memory_cache, dict):
            cached = memory_cache.get(memory_key)
            if isinstance(cached, ChartData):
                return cached

        sqlite_cache_key = _pykrx_chart_sqlite_cache_key(
            data_dir=data_dir,
            ticker=ticker_key,
            end_date=end_date_key,
            days=days,
        )
        sqlite_signature = _pykrx_chart_sqlite_signature(
            ticker=ticker_key,
            end_date=end_date_key,
            days=days,
        )
        try:
            loaded, payload = _load_json_payload_from_sqlite(
                filepath=sqlite_cache_key,
                signature=sqlite_signature,
                logger=logger,
            )
        except Exception as error:
            logger.debug("Failed to load pykrx chart SQLite cache: %s", error)
            return None

        if not loaded or not isinstance(payload, dict):
            return None
        chart_data = _deserialize_chart_data(payload)
        if chart_data is None:
            return None

        if not isinstance(memory_cache, dict):
            memory_cache = {}
            self._pykrx_chart_cache = memory_cache
        memory_cache[memory_key] = chart_data
        return chart_data

    def _save_pykrx_chart_snapshot(
        self,
        *,
        ticker: str,
        end_date: str,
        days: int,
        chart_data: ChartData,
    ) -> None:
        data_dir = self._get_data_dir()
        ticker_key = str(ticker).zfill(6)
        end_date_key = _normalize_top_gainers_target_key(end_date)
        memory_key = (ticker_key, end_date_key, int(days))

        memory_cache = getattr(self, "_pykrx_chart_cache", None)
        if not isinstance(memory_cache, dict):
            memory_cache = {}
            self._pykrx_chart_cache = memory_cache
        memory_cache[memory_key] = chart_data

        sqlite_cache_key = _pykrx_chart_sqlite_cache_key(
            data_dir=data_dir,
            ticker=ticker_key,
            end_date=end_date_key,
            days=days,
        )
        sqlite_signature = _pykrx_chart_sqlite_signature(
            ticker=ticker_key,
            end_date=end_date_key,
            days=days,
        )
        try:
            _save_json_payload_to_sqlite(
                filepath=sqlite_cache_key,
                signature=sqlite_signature,
                payload=_serialize_chart_data(chart_data),
                max_rows=_PYKRX_CHART_SQLITE_MAX_ROWS,
                logger=logger,
            )
        except Exception as error:
            logger.debug("Failed to save pykrx chart SQLite cache: %s", error)

    def _load_from_local_csv(
        self,
        market: str,
        top_n: int,
        target_date: str = None,
    ) -> List[StockData]:
        """로컬 daily_prices.csv에서 상승률 상위 종목 로드."""
        csv_path = os.path.join(self._get_data_dir(), "daily_prices.csv")
        stocks_path = os.path.join(self._get_data_dir(), "korean_stocks_list.csv")
        min_change_pct = float(getattr(getattr(self, "config", None), "min_change_pct", 0.0))
        top_gainers_sqlite_key = _top_gainers_sqlite_cache_key(
            csv_path=csv_path,
            market=market,
            top_n=top_n,
            target_date=target_date,
            min_change_pct=min_change_pct,
        )
        top_gainers_sqlite_signature = _top_gainers_sqlite_signature(
            daily_signature=_file_signature(csv_path),
            stocks_signature=_file_signature(stocks_path),
        )

        try:
            loaded, payload = _load_json_payload_from_sqlite(
                filepath=top_gainers_sqlite_key,
                signature=top_gainers_sqlite_signature,
                logger=logger,
            )
        except Exception as error:
            logger.debug("Failed to load top gainers SQLite cache: %s", error)
        else:
            if loaded and isinstance(payload, dict):
                deserialized = _deserialize_top_gainers(payload)
                if deserialized is not None:
                    return deserialized

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
            mask_rise = latest_df["change_pct"] >= min_change_pct

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

            try:
                _save_json_payload_to_sqlite(
                    filepath=top_gainers_sqlite_key,
                    signature=top_gainers_sqlite_signature,
                    payload=_serialize_top_gainers(results),
                    max_rows=_TOP_GAINERS_SQLITE_MAX_ROWS,
                    logger=logger,
                )
            except Exception as error:
                logger.debug("Failed to save top gainers SQLite cache: %s", error)

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
        normalized_code = str(code).zfill(6)
        try:
            from pykrx import stock

            end_date_str = self._get_latest_market_date()
            cached_chart = self._load_pykrx_chart_snapshot(
                ticker=normalized_code,
                end_date=end_date_str,
                days=days,
            )
            if isinstance(cached_chart, ChartData):
                return cached_chart

            end_date = datetime.strptime(end_date_str, "%Y%m%d")
            start_date = end_date - timedelta(days=int(days * 1.6) + 10)
            start_date_str = start_date.strftime("%Y%m%d")

            df = stock.get_market_ohlcv_by_date(start_date_str, end_date_str, normalized_code)
            if not df.empty:
                df = df.tail(days)
                resolved_chart = ChartData(
                    dates=[dt.date() for dt in df.index],
                    opens=df["시가"].tolist(),
                    highs=df["고가"].tolist(),
                    lows=df["저가"].tolist(),
                    closes=df["종가"].tolist(),
                    volumes=df["거래량"].tolist(),
                )
                self._save_pykrx_chart_snapshot(
                    ticker=normalized_code,
                    end_date=end_date_str,
                    days=days,
                    chart_data=resolved_chart,
                )
                return resolved_chart
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
            stock_df = df[df["ticker"] == normalized_code].sort_values("date")
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
        """수급 데이터 조회 (통합 5일 서비스 -> pykrx -> CSV fallback)."""
        normalized_code = str(code).zfill(6)
        data_dir = self._get_data_dir()

        try:
            trend_data = get_investor_trend_5day_for_ticker(
                ticker=normalized_code,
                data_dir=data_dir,
                verify_with_references=False,
            )
            if isinstance(trend_data, dict) and not self._has_csv_anomaly_flags(trend_data):
                return SupplyData(
                    foreign_buy_5d=int(trend_data.get("foreign", 0)),
                    inst_buy_5d=int(trend_data.get("institution", 0)),
                    retail_buy_5d=0,
                )
            if isinstance(trend_data, dict):
                logger.debug("통합 5일 수급 이상징후 감지 (%s): pykrx fallback 사용", normalized_code)
        except Exception as error:
            logger.debug("통합 5일 수급 조회 실패 (%s): %s", normalized_code, error)

        try:
            from pykrx import stock

            end_date = self._get_latest_market_date()
            cached_pykrx_supply = self._load_pykrx_supply_summary_snapshot(
                ticker=normalized_code,
                end_date=end_date,
            )
            if isinstance(cached_pykrx_supply, dict):
                return SupplyData(
                    foreign_buy_5d=int(cached_pykrx_supply.get("foreign_buy_5d", 0)),
                    inst_buy_5d=int(cached_pykrx_supply.get("inst_buy_5d", 0)),
                    retail_buy_5d=int(cached_pykrx_supply.get("retail_buy_5d", 0)),
                )

            end_dt = datetime.strptime(end_date, "%Y%m%d")
            start_date = (end_dt - timedelta(days=10)).strftime("%Y%m%d")

            df = stock.get_market_trading_value_by_date(start_date, end_date, normalized_code)
            if not df.empty:
                df = df.tail(5)
                foreign_col = next((col for col in df.columns if "외국인" in col), None)
                inst_col = next((col for col in df.columns if "기관" in col), None)
                retail_col = next((col for col in df.columns if "개인" in col), None)

                resolved_payload = {
                    "foreign_buy_5d": int(df[foreign_col].sum()) if foreign_col else 0,
                    "inst_buy_5d": int(df[inst_col].sum()) if inst_col else 0,
                    "retail_buy_5d": int(df[retail_col].sum()) if retail_col else 0,
                }
                self._save_pykrx_supply_summary_snapshot(
                    ticker=normalized_code,
                    end_date=end_date,
                    payload=resolved_payload,
                )
                return SupplyData(
                    foreign_buy_5d=int(resolved_payload["foreign_buy_5d"]),
                    inst_buy_5d=int(resolved_payload["inst_buy_5d"]),
                    retail_buy_5d=int(resolved_payload["retail_buy_5d"]),
                )
        except Exception as error:
            logger.warning(f"pykrx 수급 조회 실패 ({code}): {error}")

        try:
            supply_summary_map = self._load_supply_summary_map()
            trend_values = supply_summary_map.get(normalized_code)
            if not trend_values:
                return SupplyData(0, 0, 0)

            foreign_5d, inst_5d = trend_values
            return SupplyData(
                foreign_buy_5d=int(foreign_5d),
                inst_buy_5d=int(inst_5d),
                retail_buy_5d=0,
            )

        except Exception as error:
            logger.error(f"수급 데이터 CSV 조회 실패 ({code}): {error}")
            return None
