#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Common Data Status Service

공통 라우트의 데이터 파일 상태 조회 로직을 분리한다.
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any, Callable

import pandas as pd

from services.file_row_count_cache import (
    clear_file_row_count_cache,
    file_signature,
    get_cached_file_row_count,
)


def clear_common_data_status_cache() -> None:
    """테스트/운영에서 row-count 캐시를 명시적으로 비운다."""
    clear_file_row_count_cache()


def _format_size(size_bytes: int) -> str:
    if size_bytes > 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    if size_bytes > 1024:
        return f"{size_bytes / 1024:.1f} KB"
    return f"{size_bytes} B"


def _normalize_data_date_token(value: Any) -> str | None:
    token = str(value or "").strip()
    if not token:
        return None
    if len(token) >= 10:
        token = token[:10]

    for fmt in ("%Y-%m-%d", "%Y%m%d"):
        try:
            return datetime.strptime(token, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def _extract_csv_data_date(path: str) -> str | None:
    for column_name in ("date", "signal_date"):
        try:
            frame = pd.read_csv(path, usecols=[column_name], dtype={column_name: str})
        except Exception:
            continue
        if frame.empty or column_name not in frame.columns:
            continue
        series = frame[column_name].astype(str).map(_normalize_data_date_token).dropna()
        if not series.empty:
            return str(series.max())
    return None


def _extract_vcp_metadata(path: str) -> tuple[str | None, str | None]:
    metadata_path = os.path.join(os.path.dirname(path), "vcp_signals_latest.json")
    if not os.path.exists(metadata_path):
        return None, None
    return _extract_json_data_metadata(metadata_path)


def _extract_json_data_metadata(path: str) -> tuple[str | None, str | None]:
    with open(path, encoding="utf-8") as handle:
        payload = json.load(handle)

    if not isinstance(payload, dict):
        return None, None

    data_timestamp = None
    for key in ("generated_at", "timestamp", "generatedAt", "updatedAt"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            data_timestamp = value.strip()
            break

    for key in ("dataset_date", "date", "signal_date"):
        normalized = _normalize_data_date_token(payload.get(key))
        if normalized:
            return normalized, data_timestamp

    return _normalize_data_date_token(data_timestamp), data_timestamp


def _extract_data_metadata(path: str, logger: Any) -> tuple[str | None, str | None]:
    try:
        if str(path).lower().endswith(".csv"):
            data_date = _extract_csv_data_date(path)
            if data_date:
                return data_date, None
            if os.path.basename(str(path)) == "signals_log.csv":
                return _extract_vcp_metadata(path)
            return None, None
        if str(path).lower().endswith(".json"):
            return _extract_json_data_metadata(path)
    except Exception as error:
        logger.debug(f"Failed to extract logical data date ({path}): {error}")
    return None, None


def build_common_data_status_payload(
    *,
    data_files_to_check: list[dict[str, Any]],
    load_update_status: Callable[..., dict[str, Any]],
    logger: Any,
    now: datetime | None = None,
) -> dict[str, Any]:
    current_time = now or datetime.now()
    files_status: list[dict[str, Any]] = []

    for file_info in data_files_to_check:
        path = file_info["path"]
        signature = file_signature(path)
        if signature is None:
            files_status.append(
                {
                    "name": file_info["name"],
                    "path": path,
                    "exists": False,
                    "lastModified": "",
                    "size": "-",
                    "rowCount": None,
                    "dataDate": None,
                    "dataTimestamp": None,
                    "link": file_info.get("link", ""),
                    "menu": file_info.get("menu", ""),
                }
            )
            continue

        mtime_ns, size_bytes = signature
        modified_at = datetime.fromtimestamp(mtime_ns / 1_000_000_000)
        data_date, data_timestamp = _extract_data_metadata(path, logger)
        files_status.append(
            {
                "name": file_info["name"],
                "path": path,
                "exists": True,
                "lastModified": modified_at.isoformat(),
                "size": _format_size(int(size_bytes)),
                "rowCount": get_cached_file_row_count(
                    path=path,
                    signature=signature,
                    logger=logger,
                ),
                "dataDate": data_date,
                "dataTimestamp": data_timestamp,
                "link": file_info.get("link", ""),
                "menu": file_info.get("menu", ""),
            }
        )

    try:
        current_status = load_update_status(deep_copy=False)
    except TypeError:
        current_status = load_update_status()
    update_status = {
        "isRunning": current_status.get("isRunning", False),
        "lastRun": current_status.get("startTime") or current_time.isoformat(),
        "progress": current_status.get("currentItem") or "",
    }
    return {"files": files_status, "update_status": update_status}
