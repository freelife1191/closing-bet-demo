#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KR Market Gate Service 퍼사드
"""

from __future__ import annotations

from services.kr_market_ai_payload_service import (
    build_ai_analysis_payload_for_target_date,
    build_latest_ai_analysis_payload,
)
from services.kr_market_market_gate_validity import (
    apply_market_gate_snapshot_fallback,
    build_market_gate_empty_payload,
    build_market_gate_initializing_payload,
    evaluate_market_gate_validity,
    normalize_market_gate_payload,
    resolve_market_gate_filename,
)

__all__ = [
    "resolve_market_gate_filename",
    "evaluate_market_gate_validity",
    "apply_market_gate_snapshot_fallback",
    "build_market_gate_initializing_payload",
    "build_market_gate_empty_payload",
    "normalize_market_gate_payload",
    "build_ai_analysis_payload_for_target_date",
    "build_latest_ai_analysis_payload",
]
