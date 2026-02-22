#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Engine - Market Gate Logic Utils

Market Gate 공통 유틸/응답 빌더 함수를 분리한다.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict


def sanitize_for_json(data: Any) -> Any:
    """JSON 직렬화를 위해 NaN, Infinity 등을 None으로 변환 (재귀)."""
    if isinstance(data, dict):
        return {k: sanitize_for_json(v) for k, v in data.items()}
    if isinstance(data, list):
        return [sanitize_for_json(v) for v in data]
    if isinstance(data, float):
        import math

        if math.isnan(data) or math.isinf(data):
            return None
        return data
    return data


def resolve_analysis_date_str(result: Dict[str, Any], target_date: str | None) -> str:
    """저장 파일명용 날짜 문자열(YYYYMMDD)을 계산한다."""
    if target_date:
        return target_date.replace("-", "")
    if "dataset_date" in result:
        try:
            return result["dataset_date"].replace("-", "")
        except (TypeError, AttributeError):
            return datetime.now().strftime("%Y%m%d")
    return datetime.now().strftime("%Y%m%d")


def build_default_result(msg: str) -> Dict[str, Any]:
    return {
        "timestamp": datetime.now().isoformat(),
        "total_score": 50,
        "is_gate_open": True,
        "gate_reason": "데이터 부족 (Default Open)",
        "status": "분석 대기 (Neutral)",
        "label": "Neutral",
        "color": "YELLOW",
        "message": msg,
        "dataset_date": "",
        "details": {},
    }


__all__ = [
    "sanitize_for_json",
    "resolve_analysis_date_str",
    "build_default_result",
]
