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
from services.kr_market_data_cache_service import (
    file_signature as _shared_file_signature,
    load_csv_file as _load_shared_csv_file,
)


@dataclass
class CsvCacheEntry:
    """mtime 기반 CSV 캐시 엔트리."""

    mtime: float
    frame: pd.DataFrame


def _project_existing_requested_columns(
    df: pd.DataFrame,
    requested_usecols: list[str] | tuple[str, ...] | None,
) -> pd.DataFrame:
    """usecols fallback 시 존재하는 요청 컬럼만 투영해 메모리/캐시 크기를 줄인다."""
    if requested_usecols is None:
        return df
    existing_columns = [str(column) for column in requested_usecols if str(column) in df.columns]
    if not existing_columns:
        return df
    return df.loc[:, existing_columns]


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

    normalized_kwargs: list[tuple[str, object]] = []
    for key, value in sorted(read_csv_kwargs.items(), key=lambda item: item[0]):
        if key == "usecols" and isinstance(value, (list, tuple)):
            normalized_value: object = tuple(str(column) for column in value)
        elif isinstance(value, dict):
            normalized_value = tuple(sorted((str(k), str(v)) for k, v in value.items()))
        else:
            normalized_value = repr(value)
        normalized_kwargs.append((str(key), normalized_value))
    full_key = f"{path}::{cache_key}::{tuple(normalized_kwargs)}"
    try:
        mtime = os.path.getmtime(path)
    except OSError as error:
        logger.warning(f"CSV mtime 조회 실패 ({path}): {error}")
        return pd.DataFrame()

    cached = cache.get(full_key)
    if cached and cached.mtime == mtime:
        return cached.frame.copy(deep=deep_copy) if deep_copy else cached.frame

    usecols = read_csv_kwargs.get("usecols")
    dtype = read_csv_kwargs.get("dtype")
    low_memory = read_csv_kwargs.get("low_memory", False)
    has_only_supported_kwargs = set(read_csv_kwargs.keys()).issubset(
        {"usecols", "dtype", "low_memory"}
    )
    can_use_shared_loader = (
        has_only_supported_kwargs
        and (usecols is None or isinstance(usecols, (list, tuple)))
        and (dtype is None or isinstance(dtype, dict))
        and low_memory in (False, None)
    )

    df: pd.DataFrame
    if can_use_shared_loader:
        data_dir = os.path.dirname(path)
        filename = os.path.basename(path)
        signature = _shared_file_signature(path)
        if signature is not None and filename:
            normalized_usecols = [str(column) for column in usecols] if usecols is not None else None
            try:
                df = _load_shared_csv_file(
                    data_dir,
                    filename,
                    deep_copy=False,
                    usecols=normalized_usecols,
                    signature=signature,
                )
            except ValueError as error:
                # usecols 스키마 불일치 시 SQLite-backed shared loader를
                # usecols=None으로 한 번 더 재시도해 direct read를 줄인다.
                logger.debug(f"shared csv usecols fallback ({path}): {error}")
                if normalized_usecols is not None:
                    try:
                        df = _load_shared_csv_file(
                            data_dir,
                            filename,
                            deep_copy=False,
                            usecols=None,
                            signature=signature,
                        )
                        df = _project_existing_requested_columns(df, normalized_usecols)
                    except Exception as fallback_error:
                        logger.debug(f"shared csv cache fallback to pd.read_csv ({path}): {fallback_error}")
                        fallback_kwargs = dict(read_csv_kwargs)
                        fallback_kwargs.pop("usecols", None)
                        df = pd.read_csv(path, **fallback_kwargs)
                        df = _project_existing_requested_columns(df, normalized_usecols)
                else:
                    df = pd.read_csv(path, **read_csv_kwargs)
            except Exception as error:
                logger.debug(f"shared csv cache fallback to pd.read_csv ({path}): {error}")
                df = pd.read_csv(path, **read_csv_kwargs)
            else:
                if isinstance(dtype, dict):
                    try:
                        # shared loader 경로에서도 read_csv(dtype=...)와 동일하게 dtype 강제 적용
                        df = df.astype(dtype)
                    except Exception as error:
                        logger.debug(f"shared csv dtype cast fallback to pd.read_csv ({path}): {error}")
                        df = pd.read_csv(path, **read_csv_kwargs)
        else:
            df = pd.read_csv(path, **read_csv_kwargs)
    else:
        df = pd.read_csv(path, **read_csv_kwargs)

    cache[full_key] = CsvCacheEntry(mtime=mtime, frame=df)
    return df.copy(deep=deep_copy) if deep_copy else df
