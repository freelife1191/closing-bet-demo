#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KR Market VCP cache update service.
"""

from __future__ import annotations

import os
from typing import Any, Callable

from engine.ticker_utils import normalize_ticker
from services.common_update_ai_analysis_service import _valid_recommendations, _write_ai_analysis_files


def update_vcp_ai_cache_files(
    target_date: str | None,
    updated_recommendations: dict[str, Any],
    get_data_path: Callable[[str], str],
    load_json_file: Callable[[str], dict[str, Any]],
    logger: Any,
    ai_results: dict[str, Any] | None = None,
) -> int:
    """재분석 결과를 수집과 같은 규칙으로 날짜별 VCP AI 캐시에 병합하고 반영한 종목 수를 돌려준다.

    캐시에 없던 종목은 추가하고 날짜 파일이 없으면 만든다. 날짜 없는 파일은 분석 날짜가
    오늘이거나 그 파일의 signal_date 와 같을 때만 쓰고, 실패 판정은 기존 유효 판정을 덮지
    않는다([VCP-044]).
    """
    del load_json_file  # 저장 함수가 파일을 직접 읽는다
    if not target_date:
        return 0

    rows: dict[str, dict[str, Any]] = {}
    for ticker, payload in (ai_results or {}).items():
        ticker_key = normalize_ticker(ticker)
        if ticker_key and isinstance(payload, dict):
            rows[ticker_key] = {**payload, "ticker": ticker_key}
    for ticker, recommendation in (updated_recommendations or {}).items():
        ticker_key = normalize_ticker(ticker)
        if ticker_key and isinstance(recommendation, dict) and recommendation:
            row = rows.setdefault(ticker_key, {"ticker": ticker_key})
            # 분석기 원본 판정이 유효하면 원본(model 등 부가 필드 포함)을 남긴다
            if "gemini_recommendation" not in _valid_recommendations(row):
                row["gemini_recommendation"] = recommendation
    if not rows:
        return 0

    try:
        return _write_ai_analysis_files(
            data_dir=os.path.dirname(get_data_path("signals_log.csv")),
            analysis_date=target_date,
            results={"signals": list(rows.values())},
        )
    except Exception as error:
        logger.warning(f"VCP AI cache update failed ({target_date}): {error}")
        return 0
