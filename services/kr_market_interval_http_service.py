#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KR Market interval HTTP request handling service.
"""

from __future__ import annotations

from typing import Any, Callable


def handle_interval_config_request(
    *,
    method: str,
    req_data: dict[str, Any],
    current_interval: int,
    apply_interval_fn: Callable[[int], None],
    persist_interval_fn: Callable[[int], None],
) -> tuple[int, dict[str, Any]]:
    """config/interval 요청을 검증/처리하여 (status, payload)를 반환한다."""
    if method == "GET":
        return 200, {"interval": current_interval}

    try:
        new_interval = int(req_data.get("interval"))
    except (TypeError, ValueError):
        return 400, {"error": "Invalid interval"}

    if new_interval < 1 or new_interval > 1440:
        return 400, {"error": "Invalid interval"}

    apply_interval_fn(new_interval)
    persist_interval_fn(new_interval)
    return 200, {
        "status": "success",
        "message": f"Updated interval to {new_interval} minutes",
        "interval": new_interval,
    }

