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
) -> pd.DataFrame:
    data_dir = os.path.dirname(filepath)
    filename = os.path.basename(filepath)
    if not filename:
        return pd.DataFrame()

    signature = shared_file_signature(filepath)
    if signature is None:
        return pd.DataFrame()

    return load_shared_csv_file(
        data_dir,
        filename,
        deep_copy=True,
        usecols=usecols,
        signature=signature,
    )


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

    # dtype/low_memory 옵션이 기본값일 때는 공용 SQLite-backed 캐시를 우선 사용한다.
    if dtype is None and low_memory is False:
        try:
            cached = _load_csv_via_shared_cache(
                filepath=filepath,
                usecols=usecols,
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
