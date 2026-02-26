#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Screener CSV data loader helpers.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Callable, Sequence
from typing import Any

import pandas as pd

from engine.signal_tracker_source_cache import load_signal_tracker_csv_cached
from services.kr_market_csv_utils import get_ticker_padded_series


def _read_csv_min_columns_cached(
    path: str,
    *,
    cache_kind: str,
    dtype: dict[str, Any] | None,
    usecols: Sequence[str],
    optional_usecols: Sequence[str] | None = None,
    read_csv: Callable[..., pd.DataFrame] = pd.read_csv,
    logger: logging.Logger | None = None,
) -> pd.DataFrame:
    """최소 컬럼 로드 + 스키마 불일치 폴백을 SQLite 캐시 경로로 수행한다."""
    required_cols = [str(column) for column in usecols]
    selected_cols = list(required_cols)
    if optional_usecols:
        selected_cols.extend(
            [
                str(column)
                for column in optional_usecols
                if str(column) not in selected_cols
            ]
        )

    common_kwargs = {
        "path": path,
        "cache_kind": f"screener:{cache_kind}",
        "dtype": dtype,
        "read_csv": read_csv,
        "logger": logger,
        "low_memory": False,
        "deep_copy": True,
    }

    try:
        return load_signal_tracker_csv_cached(
            **common_kwargs,
            usecols=selected_cols,
            fallback_without_usecols=False,
        )
    except ValueError:
        if optional_usecols:
            try:
                return load_signal_tracker_csv_cached(
                    **common_kwargs,
                    usecols=required_cols,
                    fallback_without_usecols=False,
                )
            except ValueError:
                pass
        return load_signal_tracker_csv_cached(
            **common_kwargs,
            usecols=required_cols,
            fallback_without_usecols=True,
        )


def load_stocks_frame(
    stocks_path: str,
    *,
    read_csv: Callable[..., pd.DataFrame] = pd.read_csv,
    logger: logging.Logger | None = None,
) -> pd.DataFrame:
    if not os.path.exists(stocks_path):
        return pd.DataFrame()

    frame = _read_csv_min_columns_cached(
        stocks_path,
        cache_kind="stocks",
        dtype={"ticker": str},
        usecols=["ticker", "name", "market"],
        read_csv=read_csv,
        logger=logger,
    )
    if "ticker" in frame.columns:
        frame["ticker"] = get_ticker_padded_series(frame)
    return frame


def load_prices_frame(
    prices_path: str,
    *,
    read_csv: Callable[..., pd.DataFrame] = pd.read_csv,
    logger: logging.Logger | None = None,
) -> pd.DataFrame:
    if not os.path.exists(prices_path):
        return pd.DataFrame()

    frame = _read_csv_min_columns_cached(
        prices_path,
        cache_kind="prices",
        dtype={"ticker": str},
        usecols=["ticker", "date", "open", "high", "low", "close", "volume"],
        optional_usecols=["current_price"],
        read_csv=read_csv,
        logger=logger,
    )
    if "ticker" in frame.columns:
        frame["ticker"] = get_ticker_padded_series(frame)
    if "date" in frame.columns:
        frame["date"] = pd.to_datetime(frame["date"])
    return frame


def load_inst_frame(
    inst_path: str,
    *,
    read_csv: Callable[..., pd.DataFrame] = pd.read_csv,
    logger: logging.Logger | None = None,
) -> pd.DataFrame:
    if not os.path.exists(inst_path):
        return pd.DataFrame()

    frame = _read_csv_min_columns_cached(
        inst_path,
        cache_kind="institutional",
        dtype={"ticker": str},
        usecols=["ticker", "date", "foreign_buy", "inst_buy"],
        read_csv=read_csv,
        logger=logger,
    )
    if "ticker" in frame.columns:
        frame["ticker"] = get_ticker_padded_series(frame)
    if "date" in frame.columns:
        frame["date"] = pd.to_datetime(frame["date"])
    return frame


__all__ = ["load_stocks_frame", "load_prices_frame", "load_inst_frame"]
