#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KR Market Jongga History Payload Builder
"""

from __future__ import annotations

import os
from typing import Any, Callable

from services.kr_market_data_cache_service import load_json_payload_from_path


def build_jongga_history_payload(
    target_date: str,
    data_dir: str,
    load_json_file: Callable[[str], dict[str, Any]],
    recalculate_jongga_grades: Callable[[dict[str, Any]], bool],
    sort_jongga_signals: Callable[[list[dict[str, Any]]], None],
) -> tuple[int, dict[str, Any]]:
    """특정 날짜 종가베팅 이력 payload를 구성한다."""
    date_str = target_date.replace("-", "")
    history_filename = f"jongga_v2_results_{date_str}.json"
    history_path = os.path.join(data_dir, history_filename)

    if os.path.exists(history_path):
        data = load_json_file(history_filename)
        if not isinstance(data, dict) or not data:
            try:
                raw_data = load_json_payload_from_path(history_path)
                data = raw_data if isinstance(raw_data, dict) else {}
            except Exception:
                data = {} if not isinstance(data, dict) else data
        if isinstance(data, dict) and "signals" in data:
            recalculate_jongga_grades(data)
            sort_jongga_signals(data["signals"])
        return 200, data if isinstance(data, dict) else {}

    latest_data = load_json_file("jongga_v2_latest.json")
    if isinstance(latest_data, dict) and str(latest_data.get("date", ""))[:10] == target_date:
        if "signals" in latest_data:
            recalculate_jongga_grades(latest_data)
            sort_jongga_signals(latest_data["signals"])
        return 200, latest_data

    return 404, {
        "error": f"{target_date} 날짜의 데이터가 없습니다.",
        "date": target_date,
        "signals": [],
    }
