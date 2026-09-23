#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""[VCP-039] 취소한 재분석은 실제로 처리한 행만 기록한다."""

import logging

import pandas as pd

import engine.vcp_ai_analyzer as vcp_ai_analyzer
from services.kr_market_vcp_reanalysis_service import execute_vcp_failed_ai_reanalysis


class _Analyzer:
    second_provider = "gpt"

    def get_available_providers(self):
        return ["gemini", "gpt"]

    async def analyze_stock(self, _name, stock):
        if stock["ticker"] == "000002":
            raise RuntimeError("provider down")
        rec = {"action": "BUY", "confidence": 80, "reason": "ok"}
        return {"gemini_recommendation": rec, "gpt_recommendation": rec}


def _run_cancelled_after_two(monkeypatch, tmp_path, force_provider):
    monkeypatch.setattr(vcp_ai_analyzer, "get_vcp_analyzer", _Analyzer)
    path = tmp_path / "signals_log.csv"
    frame = pd.DataFrame(
        {
            "ticker": ["000001", "000002", "000003"],
            "signal_date": ["2026-09-22"] * 3,
            "name": ["a", "b", "c"],
            "ai_action": ["HOLD"] * 3,
            "ai_confidence": [50] * 3,
            "ai_reason": ["prev"] * 3,
        }
    )
    frame.to_csv(path, index=False)
    seen = []

    status, payload = execute_vcp_failed_ai_reanalysis(
        "2026-09-22",
        frame.copy(),
        str(path),
        update_cache_files=lambda *_a: 0,
        logger=logging.getLogger(__name__),
        force_provider=force_provider,
        load_csv_file_for_persist=lambda name, **_k: pd.read_csv(tmp_path / name, dtype={"ticker": str}),
        should_stop=lambda: len(seen) >= 2,  # 두 종목을 처리한 뒤 취소
        on_progress=lambda _i, _t, ticker: seen.append(ticker),
    )

    assert status == 200 and payload["status"] == "cancelled"
    assert (payload["updated_count"], payload["still_failed_count"]) == (1, 1)
    return path


def test_cancelled_reanalysis_keeps_rows_it_never_reached(monkeypatch, tmp_path):
    path = _run_cancelled_after_two(monkeypatch, tmp_path, "gemini")
    saved = pd.read_csv(path, dtype={"ticker": str}).set_index("ticker")
    assert saved.loc["000001", "ai_action"] == "BUY"
    assert saved.loc["000002", "ai_reason"] == "분석 실패"  # 처리했지만 실패한 행은 실패로 기록한다
    assert (saved.loc["000003", "ai_action"], saved.loc["000003", "ai_reason"]) == ("HOLD", "prev")


def test_cancelled_second_only_reanalysis_counts_only_processed_rows(monkeypatch, tmp_path):
    """second 강제 재분석은 CSV 를 쓰지 않으므로 집계만 본다."""
    _run_cancelled_after_two(monkeypatch, tmp_path, "second")
