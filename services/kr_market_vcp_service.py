#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KR Market VCP Service (Facade)

VCP 시그널 구성/백그라운드 실행/실패 재분석 로직을 하위 모듈로 분리한다.
"""

from __future__ import annotations

from services.kr_market_vcp_background_service import run_vcp_background_pipeline
from services.kr_market_vcp_payload_service import build_vcp_signals_payload
from services.kr_market_vcp_reanalysis_service import (
    build_vcp_reanalysis_no_targets_payload,
    build_vcp_reanalysis_success_payload,
    collect_failed_vcp_rows,
    execute_vcp_failed_ai_reanalysis,
    prepare_vcp_signals_scope,
    run_async_analyzer_batch,
    validate_vcp_reanalysis_source_frame,
)


__all__ = [
    "prepare_vcp_signals_scope",
    "collect_failed_vcp_rows",
    "run_async_analyzer_batch",
    "build_vcp_signals_payload",
    "run_vcp_background_pipeline",
    "validate_vcp_reanalysis_source_frame",
    "build_vcp_reanalysis_no_targets_payload",
    "build_vcp_reanalysis_success_payload",
    "execute_vcp_failed_ai_reanalysis",
]
