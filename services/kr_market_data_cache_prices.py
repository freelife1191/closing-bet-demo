#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KR Market Data Cache - Price snapshot helpers
"""

from __future__ import annotations

import os
from typing import Any, Callable

import pandas as pd

from services.kr_market_data_cache_sqlite_payload import (
    load_json_payload_from_sqlite as _load_json_payload_from_sqlite,
    save_json_payload_to_sqlite as _save_json_payload_to_sqlite,
)
from services.kr_market_csv_utils import build_latest_close_map_from_prices_df
from services.kr_market_data_cache_core import (
    BACKTEST_PRICE_SNAPSHOT_CACHE,
    FILE_CACHE_LOCK,
    LATEST_VCP_PRICE_MAP_CACHE,
    file_signature,
    load_csv_file,
)

_LATEST_VCP_PRICE_MAP_SQLITE_MAX_ROWS = 256
_LATEST_VCP_PRICE_MAP_SQLITE_CACHE_KEY_SUFFIX = "::latest_vcp_price_map"


def _build_latest_price_map(df_prices: pd.DataFrame) -> dict[str, float]:
    return build_latest_close_map_from_prices_df(df_prices)


def _latest_vcp_price_map_sqlite_cache_key(price_file: str) -> str:
    return f"{os.path.abspath(price_file)}{_LATEST_VCP_PRICE_MAP_SQLITE_CACHE_KEY_SUFFIX}"


def _serialize_latest_vcp_price_map(price_map: dict[str, float]) -> dict[str, object]:
    rows: dict[str, float] = {}
    for ticker, value in price_map.items():
        ticker_key = str(ticker).zfill(6)
        if not ticker_key:
            continue
        try:
            normalized_value = float(value)
        except (TypeError, ValueError):
            continue
        if pd.isna(normalized_value):
            continue
        rows[ticker_key] = normalized_value
    return {"rows": rows}


def _deserialize_latest_vcp_price_map(payload: dict[str, object]) -> dict[str, float] | None:
    rows_payload = payload.get("rows")
    if not isinstance(rows_payload, dict):
        return None

    latest_price_map: dict[str, float] = {}
    for ticker, value in rows_payload.items():
        ticker_key = str(ticker).zfill(6)
        if not ticker_key:
            continue
        try:
            normalized_value = float(value)
        except (TypeError, ValueError):
            continue
        if pd.isna(normalized_value):
            continue
        latest_price_map[ticker_key] = normalized_value
    return latest_price_map


def _load_latest_vcp_price_map_from_sqlite(
    *,
    price_file: str,
    signature: tuple[int, int],
    logger: Any,
) -> dict[str, float] | None:
    try:
        loaded, payload = _load_json_payload_from_sqlite(
            filepath=_latest_vcp_price_map_sqlite_cache_key(price_file),
            signature=signature,
            logger=logger,
        )
    except Exception as error:
        logger.debug("Failed to load latest price map SQLite cache: %s", error)
        return None

    if not loaded or not isinstance(payload, dict):
        return None
    return _deserialize_latest_vcp_price_map(payload)


def _save_latest_vcp_price_map_to_sqlite(
    *,
    price_file: str,
    signature: tuple[int, int],
    price_map: dict[str, float],
    logger: Any,
) -> None:
    try:
        _save_json_payload_to_sqlite(
            filepath=_latest_vcp_price_map_sqlite_cache_key(price_file),
            signature=signature,
            payload=_serialize_latest_vcp_price_map(price_map),
            max_rows=_LATEST_VCP_PRICE_MAP_SQLITE_MAX_ROWS,
            logger=logger,
        )
    except Exception as error:
        logger.debug("Failed to save latest price map SQLite cache: %s", error)


def _load_daily_prices_subset(
    data_dir: str,
    usecols: list[str],
    signature: tuple[int, int] | None = None,
) -> pd.DataFrame:
    """공통 CSV 파일 캐시를 재사용해 daily_prices 서브셋을 로드한다."""
    return load_csv_file(
        data_dir,
        "daily_prices.csv",
        deep_copy=False,
        usecols=usecols,
        signature=signature,
    )


def load_latest_vcp_price_map(data_dir: str, logger: Any) -> dict[str, float]:
    """daily_prices.csv에서 ticker별 최신 종가 맵을 로드한다."""
    price_file = os.path.join(data_dir, "daily_prices.csv")
    signature = file_signature(price_file)
    if signature is None:
        return {}

    with FILE_CACHE_LOCK:
        cache_signature = LATEST_VCP_PRICE_MAP_CACHE.get("signature")
        cache_value = LATEST_VCP_PRICE_MAP_CACHE.get("value", {})
        if cache_signature == signature and isinstance(cache_value, dict):
            return dict(cache_value)

        # 백테스트 스냅샷에 이미 최신 가격맵이 있으면 재파싱 없이 재사용한다.
        backtest_signature = BACKTEST_PRICE_SNAPSHOT_CACHE.get("signature")
        backtest_price_map = BACKTEST_PRICE_SNAPSHOT_CACHE.get("price_map", {})
        if backtest_signature == signature and isinstance(backtest_price_map, dict):
            LATEST_VCP_PRICE_MAP_CACHE["signature"] = signature
            LATEST_VCP_PRICE_MAP_CACHE["value"] = dict(backtest_price_map)
            return dict(backtest_price_map)

    sqlite_cached = _load_latest_vcp_price_map_from_sqlite(
        price_file=price_file,
        signature=signature,
        logger=logger,
    )
    if sqlite_cached is not None:
        with FILE_CACHE_LOCK:
            LATEST_VCP_PRICE_MAP_CACHE["signature"] = signature
            LATEST_VCP_PRICE_MAP_CACHE["value"] = dict(sqlite_cached)
        return dict(sqlite_cached)

    df_prices = _load_daily_prices_subset(
        data_dir=data_dir,
        usecols=["date", "ticker", "close"],
        signature=signature,
    )
    if df_prices.empty:
        return {}

    latest_price_map = _build_latest_price_map(df_prices)
    with FILE_CACHE_LOCK:
        LATEST_VCP_PRICE_MAP_CACHE["signature"] = signature
        LATEST_VCP_PRICE_MAP_CACHE["value"] = dict(latest_price_map)
    _save_latest_vcp_price_map_to_sqlite(
        price_file=price_file,
        signature=signature,
        price_map=latest_price_map,
        logger=logger,
    )
    logger.debug(f"Loaded latest prices for {len(latest_price_map)} tickers")
    return latest_price_map


def load_backtest_price_snapshot(
    data_dir: str,
    build_latest_price_map: Callable[[Any], dict[str, float]],
) -> tuple[pd.DataFrame, dict[str, float]]:
    """
    백테스트용 가격 스냅샷 로드.
    반환값: (전체 가격 DataFrame, ticker별 최신 종가 맵)
    """
    price_file = os.path.join(data_dir, "daily_prices.csv")
    signature = file_signature(price_file)
    if signature is None:
        return pd.DataFrame(), {}

    with FILE_CACHE_LOCK:
        cache_signature = BACKTEST_PRICE_SNAPSHOT_CACHE.get("signature")
        cache_df = BACKTEST_PRICE_SNAPSHOT_CACHE.get("df")
        cache_price_map = BACKTEST_PRICE_SNAPSHOT_CACHE.get("price_map")
        latest_signature = LATEST_VCP_PRICE_MAP_CACHE.get("signature")
        latest_cache_map = LATEST_VCP_PRICE_MAP_CACHE.get("value", {})
        if (
            cache_signature == signature
            and isinstance(cache_df, pd.DataFrame)
            and isinstance(cache_price_map, dict)
        ):
            return cache_df.copy(deep=True), dict(cache_price_map)

    df_prices_full = _load_daily_prices_subset(
        data_dir=data_dir,
        usecols=["date", "ticker", "close", "high", "low"],
        signature=signature,
    )
    if df_prices_full.empty:
        return pd.DataFrame(), {}
    df_prices_full["ticker"] = df_prices_full["ticker"].astype(str).str.zfill(6)
    if latest_signature == signature and isinstance(latest_cache_map, dict):
        latest_price_map = dict(latest_cache_map)
    else:
        latest_price_map = build_latest_price_map(df_prices_full)

    with FILE_CACHE_LOCK:
        BACKTEST_PRICE_SNAPSHOT_CACHE["signature"] = signature
        BACKTEST_PRICE_SNAPSHOT_CACHE["df"] = df_prices_full
        BACKTEST_PRICE_SNAPSHOT_CACHE["price_map"] = dict(latest_price_map)
        LATEST_VCP_PRICE_MAP_CACHE["signature"] = signature
        LATEST_VCP_PRICE_MAP_CACHE["value"] = dict(latest_price_map)

    return df_prices_full.copy(deep=True), dict(latest_price_map)
