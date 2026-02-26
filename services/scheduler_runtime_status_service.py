#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Scheduler Runtime Status Service

스케줄러 체인 실행 상태(전체/VCP/종가베팅)를 파일 기반으로 관리한다.
"""

from __future__ import annotations

import json
import os
import threading
from datetime import datetime
from typing import Any

from services.kr_market_data_cache_service import (
    atomic_write_text,
    load_json_payload_from_path,
)

_SCHEDULER_RUNTIME_STATUS_FILENAME = "scheduler_runtime_status.json"
_SCHEDULER_RUNTIME_STATUS_LOCK = threading.Lock()


def _build_default_status() -> dict[str, Any]:
    return {
        "is_data_scheduling_running": False,
        "is_jongga_scheduling_running": False,
        "is_vcp_scheduling_running": False,
        "updated_at": None,
    }


def _resolve_status_file_path(data_dir: str) -> str:
    normalized_data_dir = str(data_dir or "data")
    return os.path.join(normalized_data_dir, _SCHEDULER_RUNTIME_STATUS_FILENAME)


def _normalize_scheduler_runtime_status(raw_status: Any) -> dict[str, Any]:
    base = _build_default_status()
    if isinstance(raw_status, dict):
        base["is_data_scheduling_running"] = bool(raw_status.get("is_data_scheduling_running", False))
        base["is_jongga_scheduling_running"] = bool(raw_status.get("is_jongga_scheduling_running", False))
        base["is_vcp_scheduling_running"] = bool(raw_status.get("is_vcp_scheduling_running", False))
        base["updated_at"] = raw_status.get("updated_at")
    return base


def get_scheduler_runtime_status(*, data_dir: str = "data") -> dict[str, Any]:
    """현재 스케줄러 런타임 상태를 조회한다."""
    status_file = _resolve_status_file_path(data_dir)
    loaded = load_json_payload_from_path(status_file, deep_copy=False)
    return _normalize_scheduler_runtime_status(loaded)


def set_scheduler_runtime_status(
    *,
    data_dir: str = "data",
    data_scheduling_running: bool | None = None,
    jongga_scheduling_running: bool | None = None,
    vcp_scheduling_running: bool | None = None,
) -> dict[str, Any]:
    """스케줄러 런타임 상태를 부분 업데이트한다."""
    with _SCHEDULER_RUNTIME_STATUS_LOCK:
        current = get_scheduler_runtime_status(data_dir=data_dir)

        if data_scheduling_running is not None:
            current["is_data_scheduling_running"] = bool(data_scheduling_running)
        if jongga_scheduling_running is not None:
            current["is_jongga_scheduling_running"] = bool(jongga_scheduling_running)
        if vcp_scheduling_running is not None:
            current["is_vcp_scheduling_running"] = bool(vcp_scheduling_running)

        current["updated_at"] = datetime.now().isoformat()
        status_file = _resolve_status_file_path(data_dir)
        atomic_write_text(
            status_file,
            json.dumps(current, ensure_ascii=False, indent=2),
        )
        return dict(current)


def reset_scheduler_runtime_status(*, data_dir: str = "data") -> dict[str, Any]:
    """스케줄러 런타임 상태를 초기화한다."""
    with _SCHEDULER_RUNTIME_STATUS_LOCK:
        status = _build_default_status()
        status["updated_at"] = datetime.now().isoformat()
        status_file = _resolve_status_file_path(data_dir)
        atomic_write_text(
            status_file,
            json.dumps(status, ensure_ascii=False, indent=2),
        )
        return dict(status)


__all__ = [
    "get_scheduler_runtime_status",
    "set_scheduler_runtime_status",
    "reset_scheduler_runtime_status",
]
