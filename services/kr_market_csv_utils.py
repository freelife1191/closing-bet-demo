#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KR Market CSV Utility Helpers
"""

from __future__ import annotations

import re
import weakref
from collections.abc import Callable

import pandas as pd

_ISO_DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_LOADER_STRATEGY_CACHE: weakref.WeakKeyDictionary[
    Callable[..., pd.DataFrame],
    dict[bool, str],
] = weakref.WeakKeyDictionary()


def _strategy_cache_key(
    load_csv_file: Callable[..., pd.DataFrame],
    *,
    usecols: list[str] | tuple[str, ...] | None,
) -> bool:
    return bool(usecols is not None)


def _get_cached_loader_strategy(
    load_csv_file: Callable[..., pd.DataFrame],
    *,
    key: bool,
) -> str | None:
    try:
        strategy_map = _LOADER_STRATEGY_CACHE.get(load_csv_file)
    except TypeError:
        return None

    if not strategy_map:
        return None
    return strategy_map.get(key)


def _set_cached_loader_strategy(
    load_csv_file: Callable[..., pd.DataFrame],
    *,
    key: bool,
    strategy: str,
) -> None:
    try:
        strategy_map = _LOADER_STRATEGY_CACHE.setdefault(load_csv_file, {})
    except TypeError:
        return

    strategy_map[key] = strategy


def _clear_cached_loader_strategy(
    load_csv_file: Callable[..., pd.DataFrame],
    *,
    key: bool,
) -> None:
    try:
        strategy_map = _LOADER_STRATEGY_CACHE.get(load_csv_file)
    except TypeError:
        return

    if not strategy_map:
        return

    strategy_map.pop(key, None)
    if not strategy_map:
        _LOADER_STRATEGY_CACHE.pop(load_csv_file, None)


def _call_loader_with_strategy(
    load_csv_file: Callable[..., pd.DataFrame],
    filename: str,
    *,
    usecols: list[str] | tuple[str, ...] | None,
    strategy: str,
) -> pd.DataFrame:
    if strategy == "deep_copy_usecols":
        return load_csv_file(filename, deep_copy=False, usecols=usecols)
    if strategy == "usecols":
        return load_csv_file(filename, usecols=usecols)
    if strategy == "deep_copy":
        return load_csv_file(filename, deep_copy=False)
    return load_csv_file(filename)


def load_csv_readonly(
    load_csv_file: Callable[..., pd.DataFrame],
    filename: str,
    *,
    usecols: list[str] | tuple[str, ...] | None = None,
) -> pd.DataFrame:
    """가능하면 deep_copy=False로 CSV를 로드한다."""
    cache_key = _strategy_cache_key(load_csv_file, usecols=usecols)
    cached_strategy = _get_cached_loader_strategy(
        load_csv_file,
        key=cache_key,
    )
    if cached_strategy:
        try:
            return _call_loader_with_strategy(
                load_csv_file,
                filename,
                usecols=usecols,
                strategy=cached_strategy,
            )
        except TypeError:
            _clear_cached_loader_strategy(load_csv_file, key=cache_key)
        except ValueError:
            if cached_strategy != "deep_copy_usecols":
                _clear_cached_loader_strategy(load_csv_file, key=cache_key)

    try:
        result = _call_loader_with_strategy(
            load_csv_file,
            filename,
            usecols=usecols,
            strategy="deep_copy_usecols",
        )
        _set_cached_loader_strategy(
            load_csv_file,
            key=cache_key,
            strategy="deep_copy_usecols",
        )
        return result
    except TypeError:
        try:
            result = _call_loader_with_strategy(
                load_csv_file,
                filename,
                usecols=usecols,
                strategy="usecols",
            )
            _set_cached_loader_strategy(
                load_csv_file,
                key=cache_key,
                strategy="usecols",
            )
            return result
        except TypeError:
            result = _call_loader_with_strategy(
                load_csv_file,
                filename,
                usecols=usecols,
                strategy="plain",
            )
            _set_cached_loader_strategy(
                load_csv_file,
                key=cache_key,
                strategy="plain",
            )
            return result
    except ValueError:
        try:
            return _call_loader_with_strategy(
                load_csv_file,
                filename,
                usecols=usecols,
                strategy="deep_copy",
            )
        except TypeError:
            return _call_loader_with_strategy(
                load_csv_file,
                filename,
                usecols=usecols,
                strategy="plain",
            )


def get_ticker_padded_series(
    df: pd.DataFrame,
    *,
    ticker_column: str = "ticker",
    cache_column: str = "_ticker_padded",
) -> pd.Series:
    """ticker 6자리 문자열 시리즈를 반환하며 가능하면 DataFrame 컬럼으로 재사용한다."""
    if cache_column in df.columns:
        return df[cache_column]

    padded = df[ticker_column].astype(str).str.zfill(6)
    try:
        df[cache_column] = padded
        return df[cache_column]
    except Exception:
        return padded


def _is_iso_date_series(series: pd.Series) -> bool:
    """YYYY-MM-DD 형식 문자열 시리즈인지 샘플 기반으로 판단한다."""
    sample = series.dropna().astype(str).head(64)
    if sample.empty:
        return False
    return bool(sample.str.match(_ISO_DATE_PATTERN).all())


def build_latest_close_map_from_prices_df(df_prices: pd.DataFrame) -> dict[str, float]:
    """가격 DataFrame에서 ticker별 최신 close 맵을 계산한다."""
    if df_prices.empty:
        return {}
    if "ticker" not in df_prices.columns or "close" not in df_prices.columns:
        return {}

    working = pd.DataFrame(
        {
            "ticker": df_prices["ticker"].astype(str).str.zfill(6),
            "close": pd.to_numeric(df_prices["close"], errors="coerce"),
        }
    )
    working = working[working["close"].notna()]
    if working.empty:
        return {}

    if "date" in df_prices.columns:
        date_series = df_prices["date"]
        if _is_iso_date_series(date_series):
            working["date"] = date_series.astype(str)
            working = working.sort_values("date")
        else:
            parsed_dates = pd.to_datetime(date_series, errors="coerce")
            if parsed_dates.notna().any():
                working["date"] = parsed_dates
                working = working.sort_values("date")

    latest_rows = working.drop_duplicates(subset=["ticker"], keep="last")
    return latest_rows.set_index("ticker")["close"].astype(float).to_dict()
