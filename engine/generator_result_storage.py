#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
시그널 생성 결과 저장/갱신 유틸리티.
"""

from __future__ import annotations

import json
import os
from datetime import date, datetime
from typing import Optional

from engine.models import ScreenerResult, Signal
from numpy_json_encoder import NumpyEncoder
from services.kr_market_data_cache_service import (
    atomic_write_text,
    load_json_payload_from_path,
)


def _write_result_json(path: str, payload: dict) -> None:
    atomic_write_text(
        path,
        json.dumps(payload, indent=2, ensure_ascii=False, cls=NumpyEncoder),
    )


def save_result_to_json(
    result: ScreenerResult,
    data_dir: str = "data",
) -> None:
    """스크리너 결과를 daily/latest JSON 파일로 저장."""
    os.makedirs(data_dir, exist_ok=True)

    data = {
        "date": result.date.isoformat(),
        "total_candidates": result.total_candidates,
        "filtered_count": result.filtered_count,
        "signals": [s.to_dict() for s in result.signals],
        "by_grade": result.by_grade,
        "by_market": result.by_market,
        "processing_time_ms": result.processing_time_ms,
        "market_status": result.market_status,
        "market_summary": result.market_summary,
        "trending_themes": result.trending_themes,
        "scanned_count": getattr(result, "scanned_count", 0),
        "updated_at": datetime.now().isoformat(),
    }

    date_str = result.date.strftime("%Y%m%d")
    daily_path = os.path.join(data_dir, f"jongga_v2_results_{date_str}.json")
    latest_path = os.path.join(data_dir, "jongga_v2_latest.json")

    _write_result_json(daily_path, data)
    _write_result_json(latest_path, data)

    print(f"\n[저장 완료] Daily: {daily_path}")
    print(f"[저장 완료] Latest: {latest_path}")


def _sort_key_signal_dict(signal_obj: dict) -> tuple[int, float]:
    """저장된 dict 형태 시그널 정렬 키 (Grade DESC, Score DESC)."""
    grade_map = {"S": 3, "A": 2, "B": 1}
    grade_val = grade_map.get(str(signal_obj.get("grade", "")).strip().upper(), 0)

    score_obj = signal_obj.get("score", 0)
    if isinstance(score_obj, dict):
        total_score = score_obj.get("total", 0)
    else:
        try:
            total_score = float(score_obj)
        except (ValueError, TypeError):
            total_score = 0

    return grade_val, total_score


def update_single_signal_json(
    code: str,
    signal: Signal,
    data_dir: str = "data",
    as_of_date: Optional[date] = None,
) -> None:
    """latest/daily JSON에서 특정 종목 시그널만 교체 후 저장."""
    latest_path = os.path.join(data_dir, "jongga_v2_latest.json")
    if not os.path.exists(latest_path):
        return

    data = load_json_payload_from_path(latest_path)
    if not isinstance(data, dict):
        return
    if not isinstance(data.get("signals"), list):
        return

    data["signals"] = [
        signal.to_dict() if row["stock_code"] == code else row
        for row in data["signals"]
    ]
    data["signals"].sort(key=_sort_key_signal_dict, reverse=True)
    data["updated_at"] = datetime.now().isoformat()

    _write_result_json(latest_path, data)

    target_day = as_of_date or date.today()
    date_str = target_day.strftime("%Y%m%d")
    daily_path = os.path.join(data_dir, f"jongga_v2_results_{date_str}.json")
    if os.path.exists(daily_path):
        _write_result_json(daily_path, data)
