#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KR Market VCP service 퍼사드 회귀 테스트
"""

import os
import sys

import pandas as pd


sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from services.kr_market_vcp_service import (
    build_vcp_reanalysis_no_targets_payload,
    build_vcp_reanalysis_success_payload,
    validate_vcp_reanalysis_source_frame,
)


def test_validate_vcp_reanalysis_source_frame_errors():
    empty_df = pd.DataFrame()
    code, payload = validate_vcp_reanalysis_source_frame(empty_df)
    assert code == 404
    assert payload["status"] == "error"

    no_ticker_df = pd.DataFrame([{"signal_date": "2026-02-21"}])
    code, payload = validate_vcp_reanalysis_source_frame(no_ticker_df)
    assert code == 400
    assert "ticker 컬럼" in payload["message"]


def test_build_vcp_reanalysis_payload_builders():
    no_targets = build_vcp_reanalysis_no_targets_payload("2026-02-21", total_in_scope=10)
    assert no_targets["failed_targets"] == 0
    assert no_targets["updated_count"] == 0

    success = build_vcp_reanalysis_success_payload(
        target_date="2026-02-21",
        total_in_scope=20,
        failed_targets=4,
        updated_count=3,
        still_failed_count=1,
        cache_files_updated=2,
    )
    assert success["failed_targets"] == 4
    assert success["updated_count"] == 3
    assert success["cache_files_updated"] == 2
