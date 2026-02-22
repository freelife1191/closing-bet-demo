#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Common Data Status Service

공통 라우트의 데이터 파일 상태 조회 로직을 분리한다.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Callable

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


def build_common_data_status_payload(
    *,
    data_files_to_check: list[dict[str, Any]],
    load_update_status: Callable[[], dict[str, Any]],
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
                    "link": file_info.get("link", ""),
                    "menu": file_info.get("menu", ""),
                }
            )
            continue

        mtime_ns, size_bytes = signature
        modified_at = datetime.fromtimestamp(mtime_ns / 1_000_000_000)
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
                "link": file_info.get("link", ""),
                "menu": file_info.get("menu", ""),
            }
        )

    current_status = load_update_status()
    update_status = {
        "isRunning": current_status.get("isRunning", False),
        "lastRun": current_status.get("startTime") or current_time.isoformat(),
        "progress": current_status.get("currentItem") or "",
    }
    return {"files": files_status, "update_status": update_status}

