#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Engine - Pandas Utilities (I/O)

Safe CSV/JSON file load and save helpers.
"""

import json
import logging
import os
from typing import Any, Dict, List, Optional

import pandas as pd
from services.kr_market_data_cache_service import (
    atomic_write_text,
    file_signature as shared_file_signature,
    load_csv_file as load_shared_csv_file,
    load_json_payload_from_path,
)

logger = logging.getLogger(__name__)


def _load_csv_via_shared_cache(
    filepath: str,
    *,
    usecols: Optional[List[str]] = None,
    dtype: Optional[Dict[str, Any]] = None,
) -> pd.DataFrame:
    data_dir = os.path.dirname(filepath)
    filename = os.path.basename(filepath)
    if not filename:
        return pd.DataFrame()

    signature = shared_file_signature(filepath)
    if signature is None:
        return pd.DataFrame()

    normalized_usecols = [str(column) for column in usecols] if usecols is not None else None
    try:
        loaded = load_shared_csv_file(
            data_dir,
            filename,
            deep_copy=True,
            usecols=normalized_usecols,
            signature=signature,
        )
    except ValueError:
        # usecols 스키마 불일치 시 shared(SQLite) 경로를 usecols=None으로 한 번 더 시도한다.
        # direct read fallback 빈도를 줄이되, 요청 컬럼이 전혀 없으면 기존처럼 예외를 유지한다.
        if normalized_usecols is None:
            raise
        loaded = load_shared_csv_file(
            data_dir,
            filename,
            deep_copy=True,
            usecols=None,
            signature=signature,
        )
        existing_columns = [column for column in normalized_usecols if column in loaded.columns]
        if existing_columns:
            loaded = loaded.loc[:, existing_columns]
        else:
            raise
    if dtype is None:
        return loaded

    # read_csv(dtype=...)와 동일하게 캐시 로드 후 dtype을 강제 적용한다.
    # 캐시 payload의 dtype 추론 차이로 인해 변환 실패 시 호출부에서 direct read_csv로 fallback한다.
    return loaded.astype(dtype, copy=False)


def load_csv_file(
    filepath: str,
    dtype: Optional[Dict[str, Any]] = None,
    usecols: Optional[List[str]] = None,
    low_memory: bool = False,
) -> pd.DataFrame:
    """CSV 파일 안전하게 로드."""
    if not os.path.exists(filepath):
        logger.warning(f"File not found: {filepath}")
        return pd.DataFrame()

    # low_memory=False 경로는 공용 SQLite-backed 캐시를 우선 사용한다.
    # dtype이 지정된 경우에도 캐시 로드 후 dtype 강제 적용을 시도해 direct read를 줄인다.
    if low_memory is False:
        try:
            cached = _load_csv_via_shared_cache(
                filepath=filepath,
                usecols=usecols,
                dtype=dtype,
            )
            if isinstance(cached, pd.DataFrame):
                return cached
        except Exception as e:
            logger.debug(f"Shared CSV cache fallback to direct read ({filepath}): {e}")

    try:
        return pd.read_csv(
            filepath,
            dtype=dtype,
            usecols=usecols,
            low_memory=low_memory,
        )
    except Exception as e:
        logger.error(f"Failed to load CSV {filepath}: {e}")
        return pd.DataFrame()


def load_json_file(filepath: str) -> dict:
    """JSON 파일 안전하게 로드."""
    if not os.path.exists(filepath):
        logger.debug(f"JSON file not found: {filepath}")
        return {}

    try:
        payload = load_json_payload_from_path(filepath)
        return payload if isinstance(payload, dict) else {}
    except Exception as e:
        logger.error(f"Failed to load JSON {filepath}: {e}")
        return {}


def save_json_file(
    filepath: str,
    data: dict,
    indent: int = 2,
    ensure_ascii: bool = False,
) -> bool:
    """JSON 파일 안전하게 저장."""
    try:
        atomic_write_text(
            filepath,
            json.dumps(data, indent=indent, ensure_ascii=ensure_ascii),
        )
        return True
    except Exception as e:
        logger.error(f"Failed to save JSON {filepath}: {e}")
        return False
