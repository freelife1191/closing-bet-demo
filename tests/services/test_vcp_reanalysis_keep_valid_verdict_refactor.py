#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""[VCP-040] 자동 재분석은 유효한 기존 판정을 실패한 Gemini 재시도로 덮지 않는다."""

import json
import logging

import pandas as pd

import engine.vcp_ai_analyzer as vcp_ai_analyzer
from services.kr_market_vcp_reanalysis_service import execute_vcp_failed_ai_reanalysis

_GPT_REASON = "수급은 긍정적이나 돌파 확인이 필요합니다."


class _GeminiStillDown:
    second_provider = "gpt"

    def get_available_providers(self):
        return ["gemini", "gpt"]

    async def analyze_batch(self, stocks):
        assert all(s.get("skip_second") for s in stocks)  # Gemini 만 다시 부른다
        return {s["ticker"]: {"gemini_recommendation": None, "gpt_recommendation": None} for s in stocks}


def test_auto_reanalysis_keeps_the_gpt_verdict_written_by_collection(monkeypatch, tmp_path):
    monkeypatch.setattr(vcp_ai_analyzer, "get_vcp_analyzer", _GeminiStillDown)
    path = tmp_path / "signals_log.csv"
    frame = pd.DataFrame(
        {
            "ticker": ["033530"],
            "signal_date": ["2026-09-21"],
            "name": ["SJG세종"],
            "ai_action": ["HOLD"],
            "ai_confidence": [72],
            "ai_reason": [_GPT_REASON],
        }
    )
    frame.to_csv(path, index=False)
    # 수집이 남긴 캐시: gemini 칸은 비고 gpt 칸만 유효하다. 그래서 행은 Gemini 재시도 대상이 된다
    (tmp_path / "kr_ai_analysis_20260921.json").write_text(
        json.dumps({"signals": [{
            "ticker": "033530",
            "gemini_recommendation": None,
            "gpt_recommendation": {"action": "HOLD", "confidence": 72, "reason": _GPT_REASON},
        }]}),
        encoding="utf-8",
    )

    status, payload = execute_vcp_failed_ai_reanalysis(
        "2026-09-21",
        frame.copy(),
        str(path),
        update_cache_files=lambda *_a: 0,
        logger=logging.getLogger(__name__),
        load_csv_file_for_persist=lambda name, **_k: pd.read_csv(tmp_path / name, dtype={"ticker": str}),
    )

    assert status == 200
    assert payload["failed_targets"] == 1  # Gemini 재시도 대상이었다
    saved = pd.read_csv(path, dtype={"ticker": str}).iloc[0]
    assert (saved["ai_action"], saved["ai_confidence"], saved["ai_reason"]) == ("HOLD", 72, _GPT_REASON)
