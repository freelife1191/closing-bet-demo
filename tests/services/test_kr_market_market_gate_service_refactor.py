#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KR Market Gate Service 리팩토링 회귀 테스트
"""

from __future__ import annotations

import logging
from datetime import datetime

from services.kr_market_market_gate_service import (
    build_latest_ai_analysis_payload,
    evaluate_market_gate_validity,
    normalize_market_gate_payload,
    resolve_market_gate_filename,
)


def test_resolve_market_gate_filename_formats_target_date():
    assert resolve_market_gate_filename(None) == "market_gate.json"
    assert resolve_market_gate_filename("2026-02-22") == "market_gate_20260222.json"
    assert resolve_market_gate_filename("20260222") == "market_gate_20260222.json"


def test_evaluate_market_gate_validity_marks_stale_dataset_as_needs_update():
    gate_data = {
        "status": "GREEN",
        "sectors": [{"name": "반도체"}],
        "total_score": 70,
        "timestamp": "2026-02-23T09:30:00",
        "dataset_date": "2026-02-22",
    }
    is_valid, needs_update = evaluate_market_gate_validity(
        gate_data=gate_data,
        target_date=None,
        now=datetime(2026, 2, 23, 10, 30, 0),
    )

    assert is_valid is True
    assert needs_update is True


def test_build_latest_ai_analysis_payload_reuses_loaded_vcp_data():
    load_calls: list[str] = []

    def _load_json_file(filename: str):
        load_calls.append(filename)
        if filename == "jongga_v2_latest.json":
            return {}
        if filename == "ai_analysis_results.json":
            return {"signals": [{"ticker": "005930"}]}
        if filename == "kr_ai_analysis.json":
            return {}
        raise AssertionError(f"unexpected filename: {filename}")

    payload = build_latest_ai_analysis_payload(
        load_json_file=_load_json_file,
        should_use_jongga_ai_payload=lambda _jongga, _vcp: False,
        build_ai_signals_from_jongga_results=lambda *_args, **_kwargs: [],
        normalize_ai_payload_tickers=lambda data: data,
        format_signal_date=lambda date_text: date_text,
        now=datetime(2026, 2, 22, 11, 0, 0),
    )

    assert payload["signals"][0]["ticker"] == "005930"
    assert load_calls.count("ai_analysis_results.json") == 1


def test_build_ai_analysis_payload_for_target_date_handles_exceptions_gracefully():
    from services.kr_market_market_gate_service import build_ai_analysis_payload_for_target_date

    payload = build_ai_analysis_payload_for_target_date(
        target_date="2026-02-22",
        load_json_file=lambda _filename: (_ for _ in ()).throw(RuntimeError("boom")),
        build_ai_signals_from_jongga_results=lambda *_args, **_kwargs: [],
        normalize_ai_payload_tickers=lambda data: data,
        logger=logging.getLogger(__name__),
        now=datetime(2026, 2, 22, 12, 0, 0),
    )

    assert payload is None


def test_normalize_market_gate_payload_parses_string_commodity_values():
    payload = {
        "total_score": 72,
        "status": "GREEN",
        "commodities": {
            "krx_gold": {"value": "29,585", "change_pct": "0.31%"},
            "krx_silver": {"value": "14,650", "change_pct": "1.31"},
        },
    }

    normalized = normalize_market_gate_payload(payload)

    assert normalized["score"] == 72
    assert normalized["commodities"]["krx_gold"]["value"] == 29585.0
    assert normalized["commodities"]["krx_gold"]["change_pct"] == 0.31
    assert normalized["commodities"]["krx_silver"]["value"] == 14650.0
    assert normalized["commodities"]["krx_silver"]["change_pct"] == 1.31


def test_normalize_market_gate_payload_maps_generic_gold_to_us_commodity():
    payload = {
        "status": "GREEN",
        "commodities": {
            "gold": {"value": 5190.0, "change_pct": -0.3},
            "silver": {"value": 88.0, "change_pct": 1.7},
        },
    }

    normalized = normalize_market_gate_payload(payload)

    assert "krx_gold" not in normalized["commodities"]
    assert "krx_silver" not in normalized["commodities"]
    assert normalized["commodities"]["us_gold"]["value"] == 5190.0
    assert normalized["commodities"]["us_silver"]["value"] == 88.0
