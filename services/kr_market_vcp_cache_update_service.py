#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KR Market VCP cache update service.
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any, Callable

from services.kr_market_data_cache_service import atomic_write_text


def update_vcp_ai_cache_files(
    target_date: str | None,
    updated_recommendations: dict[str, Any],
    get_data_path: Callable[[str], str],
    load_json_file: Callable[[str], dict[str, Any]],
    logger: Any,
) -> int:
    """VCP AI 캐시 파일(ai_analysis_results/kr_ai_analysis)에 재분석 결과를 반영한다."""
    if not updated_recommendations:
        return 0

    date_str = str(target_date or "").replace("-", "")
    candidate_files = [
        f"ai_analysis_results_{date_str}.json" if date_str else "",
        "ai_analysis_results.json",
        f"kr_ai_analysis_{date_str}.json" if date_str else "",
        "kr_ai_analysis.json",
    ]

    updated_files = 0
    now_iso = datetime.now().isoformat()

    for filename in candidate_files:
        if not filename:
            continue

        filepath = get_data_path(filename)
        if not os.path.exists(filepath):
            continue

        try:
            data = load_json_file(filename)
            signals = data.get("signals", []) if isinstance(data, dict) else []
            if not isinstance(signals, list) or not signals:
                continue

            changed = False
            for item in signals:
                if not isinstance(item, dict):
                    continue
                ticker = str(item.get("ticker") or item.get("stock_code") or "").zfill(6)
                if ticker in updated_recommendations:
                    item["gemini_recommendation"] = updated_recommendations[ticker]
                    changed = True

            if not changed:
                continue

            data["generated_at"] = now_iso
            atomic_write_text(
                filepath,
                json.dumps(data, ensure_ascii=False, indent=2),
            )
            updated_files += 1
        except Exception as error:
            logger.warning(f"VCP AI cache update failed ({filename}): {error}")

    return updated_files
