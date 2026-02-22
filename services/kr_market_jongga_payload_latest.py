#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KR Market Jongga Latest Payload Builder
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Any, Callable

import pandas as pd

from services.kr_market_csv_utils import (
    build_latest_close_map_from_prices_df,
    load_csv_readonly as _load_csv_readonly,
)
from services.kr_market_data_cache_core import (
    load_csv_file as _load_cached_csv_file,
)
from services.kr_market_jongga_payload_helpers import (
    build_no_jongga_data_payload,
    find_recent_valid_jongga_payload,
    has_non_empty_signals,
    write_json_to_path,
)


def _build_latest_price_map_from_dataframe(df_prices: pd.DataFrame) -> dict[str, float]:
    return build_latest_close_map_from_prices_df(df_prices)


def _load_latest_price_map_for_jongga(
    *,
    load_csv_file: Callable[[str], pd.DataFrame] | None,
    daily_prices_path: str,
    load_latest_price_map: Callable[[], dict[str, float]] | None,
) -> dict[str, float]:
    if load_latest_price_map is not None:
        loaded = load_latest_price_map()
        if isinstance(loaded, dict):
            return loaded

    if load_csv_file is not None:
        df_prices = _load_csv_readonly(
            load_csv_file,
            "daily_prices.csv",
            usecols=["date", "ticker", "close"],
        )
        if not isinstance(df_prices, pd.DataFrame):
            return {}
        if df_prices.empty:
            return {}
        required_cols = {"ticker", "close"}
        if not required_cols.issubset(set(df_prices.columns)):
            return {}
        if "date" in df_prices.columns:
            use_columns = ["date", "ticker", "close"]
            df_prices = df_prices[[col for col in use_columns if col in df_prices.columns]]
        else:
            df_prices = df_prices[["ticker", "close"]]
        return _build_latest_price_map_from_dataframe(df_prices)

    if not os.path.exists(daily_prices_path):
        return {}

    try:
        data_dir = os.path.dirname(daily_prices_path)
        filename = os.path.basename(daily_prices_path)
        if not filename:
            return {}
        df_prices = _load_cached_csv_file(
            data_dir,
            filename,
            deep_copy=False,
            usecols=["date", "ticker", "close"],
        )
    except Exception:
        try:
            df_prices = _load_cached_csv_file(
                data_dir,
                filename,
                deep_copy=False,
            )
        except Exception:
            return {}

    if not isinstance(df_prices, pd.DataFrame):
        return {}
    if df_prices.empty:
        return {}
    required = {"ticker", "close"}
    if not required.issubset(set(df_prices.columns)):
        return {}
    if "date" in df_prices.columns:
        df_prices = df_prices[[col for col in ["date", "ticker", "close"] if col in df_prices.columns]]
    else:
        df_prices = df_prices[[col for col in ["ticker", "close"] if col in df_prices.columns]]

    return _build_latest_price_map_from_dataframe(df_prices)


def inject_latest_prices_into_jongga_payload(
    payload: dict[str, Any],
    load_csv_file: Callable[[str], pd.DataFrame] | None,
    daily_prices_path: str,
    apply_latest_prices_to_jongga_signals: Callable[[list[dict[str, Any]], dict[str, float]], int],
    logger: Any,
    load_latest_price_map: Callable[[], dict[str, float]] | None = None,
) -> None:
    if not has_non_empty_signals(payload):
        return

    try:
        latest_price_map = _load_latest_price_map_for_jongga(
            load_csv_file=load_csv_file,
            daily_prices_path=daily_prices_path,
            load_latest_price_map=load_latest_price_map,
        )
        if not latest_price_map:
            return
        updated_count = apply_latest_prices_to_jongga_signals(payload["signals"], latest_price_map)
        logger.debug(f"[Jongga V2 Latest] Updated prices for {updated_count} signals")
    except Exception as error:
        logger.warning(f"Failed to inject prices for Jongga V2: {error}")


def build_jongga_latest_payload(
    data_dir: str,
    load_json_file: Callable[[str], dict[str, Any]],
    get_data_path: Callable[[str], str],
    recalculate_jongga_grades: Callable[[dict[str, Any]], bool],
    sort_jongga_signals: Callable[[list[dict[str, Any]]], None],
    normalize_jongga_signals_for_frontend: Callable[[list[dict[str, Any]]], None],
    apply_latest_prices_to_jongga_signals: Callable[[list[dict[str, Any]], dict[str, float]], int],
    logger: Any,
    load_csv_file: Callable[[str], pd.DataFrame] | None = None,
    now: datetime | None = None,
    load_latest_price_map: Callable[[], dict[str, float]] | None = None,
) -> dict[str, Any]:
    """종가베팅 최신 조회 payload를 구성한다."""
    current_time = now or datetime.now()
    data = load_json_file("jongga_v2_latest.json")

    if not has_non_empty_signals(data):
        recent_payload = find_recent_valid_jongga_payload(
            data_dir=data_dir,
            recalculate_jongga_grades=recalculate_jongga_grades,
            logger=logger,
        )
        if recent_payload:
            return recent_payload
        logger.info("[Jongga V2] 종가베팅 데이터 없음. 자동 실행 비활성화 상태.")
        return build_no_jongga_data_payload(current_time)

    inject_latest_prices_into_jongga_payload(
        payload=data,
        load_csv_file=load_csv_file,
        daily_prices_path=get_data_path("daily_prices.csv"),
        apply_latest_prices_to_jongga_signals=apply_latest_prices_to_jongga_signals,
        logger=logger,
        load_latest_price_map=load_latest_price_map,
    )

    if recalculate_jongga_grades(data):
        write_json_to_path(get_data_path("jongga_v2_latest.json"), data, logger)

    sort_jongga_signals(data["signals"])
    normalize_jongga_signals_for_frontend(data["signals"])
    return data
