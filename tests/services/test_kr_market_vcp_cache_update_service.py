#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KR Market VCP cache update service 테스트
"""

from __future__ import annotations

import json
from pathlib import Path

from services.kr_market_vcp_cache_update_service import update_vcp_ai_cache_files


def test_update_vcp_ai_cache_files_updates_matching_tickers(tmp_path: Path):
    target_file = tmp_path / "ai_analysis_results.json"
    target_file.write_text(
        json.dumps(
            {
                "signals": [
                    {"ticker": "005930", "gemini_recommendation": {"action": "HOLD"}},
                    {"ticker": "000660", "gemini_recommendation": {"action": "HOLD"}},
                ]
            }
        ),
        encoding="utf-8",
    )

    updated = update_vcp_ai_cache_files(
        target_date=None,
        updated_recommendations={"005930": {"action": "BUY"}},
        get_data_path=lambda filename: str(tmp_path / filename),
        load_json_file=lambda filename: json.loads((tmp_path / filename).read_text(encoding="utf-8")),
        logger=type("L", (), {"warning": lambda *_a, **_k: None})(),
    )

    assert updated == 1
    payload = json.loads(target_file.read_text(encoding="utf-8"))
    assert payload["signals"][0]["gemini_recommendation"]["action"] == "BUY"
    assert payload["signals"][1]["gemini_recommendation"]["action"] == "HOLD"
    assert "generated_at" in payload


def test_update_vcp_ai_cache_files_updates_second_ai_recommendations(tmp_path: Path):
    target_file = tmp_path / "ai_analysis_results.json"
    target_file.write_text(
        json.dumps(
            {
                "signals": [
                    {
                        "ticker": "005930",
                        "gemini_recommendation": {"action": "HOLD"},
                        "perplexity_recommendation": None,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    updated = update_vcp_ai_cache_files(
        target_date=None,
        updated_recommendations={},
        get_data_path=lambda filename: str(tmp_path / filename),
        load_json_file=lambda filename: json.loads((tmp_path / filename).read_text(encoding="utf-8")),
        logger=type("L", (), {"warning": lambda *_a, **_k: None})(),
        ai_results={
            "005930": {
                "perplexity_recommendation": {
                    "action": "BUY",
                    "confidence": 70,
                    "reason": "Second AI 채움",
                }
            }
        },
    )

    assert updated == 1
    payload = json.loads(target_file.read_text(encoding="utf-8"))
    assert payload["signals"][0]["perplexity_recommendation"]["action"] == "BUY"
