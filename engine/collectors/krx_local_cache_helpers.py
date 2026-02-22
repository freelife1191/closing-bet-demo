#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KRX 로컬 CSV 캐시 헬퍼.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass

import pandas as pd


@dataclass
class CsvCacheEntry:
    """mtime 기반 CSV 캐시 엔트리."""

    mtime: float
    frame: pd.DataFrame


def read_csv_cached(
    *,
    cache: dict[str, CsvCacheEntry],
    path: str,
    cache_key: str,
    logger: logging.Logger,
    deep_copy: bool = True,
    **read_csv_kwargs,
) -> pd.DataFrame:
    """파일 mtime 기반 CSV 캐시 조회/로드."""
    if not os.path.exists(path):
        return pd.DataFrame()

    full_key = f"{path}::{cache_key}"
    try:
        mtime = os.path.getmtime(path)
    except OSError as error:
        logger.warning(f"CSV mtime 조회 실패 ({path}): {error}")
        return pd.DataFrame()

    cached = cache.get(full_key)
    if cached and cached.mtime == mtime:
        return cached.frame.copy(deep=deep_copy) if deep_copy else cached.frame

    df = pd.read_csv(path, **read_csv_kwargs)
    cache[full_key] = CsvCacheEntry(mtime=mtime, frame=df)
    return df.copy(deep=deep_copy) if deep_copy else df
