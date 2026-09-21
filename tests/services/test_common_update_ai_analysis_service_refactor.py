#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Common Update AI Analysis Service 리팩토링 테스트
"""

from __future__ import annotations

import json
import types

import pandas as pd

from services.common_update_ai_analysis_service import (
    _normalize_ai_target_dataframe,
    _resolve_ai_target_limit,
    _resolve_ai_target_dataframe,
    _select_top_ai_targets,
    run_ai_analysis_step,
)


def test_select_top_ai_targets_uses_score_order():
    df = pd.DataFrame(
        [
            {"ticker": "000001", "score": "10"},
            {"ticker": "000002", "score": "42"},
            {"ticker": "000003", "score": None},
            {"ticker": "000004", "score": "30"},
        ]
    )

    selected = _select_top_ai_targets(df, limit=2)

    assert selected["ticker"].tolist() == ["000002", "000004"]


def test_select_top_ai_targets_without_score_falls_back_to_head():
    df = pd.DataFrame([{"ticker": f"{i:06d}"} for i in range(5)])

    selected = _select_top_ai_targets(df, limit=3)

    assert selected["ticker"].tolist() == ["000000", "000001", "000002"]


def test_normalize_ai_target_dataframe_deduplicates_padded_ticker():
    df = pd.DataFrame(
        [
            {"ticker": "5930", "score": 10},
            {"ticker": "005930", "score": 7},
            {"ticker": "660", "score": 20},
        ]
    )

    normalized = _normalize_ai_target_dataframe(
        df,
        logger=type("L", (), {"warning": lambda *_a, **_k: None})(),
    )

    assert normalized["ticker"].tolist() == ["005930", "000660"]


def test_normalize_ai_target_dataframe_returns_empty_when_ticker_missing():
    df = pd.DataFrame([{"code": "005930"}])
    warnings: list[str] = []

    logger = type(
        "L",
        (),
        {"warning": lambda _self, message: warnings.append(str(message))},
    )()

    normalized = _normalize_ai_target_dataframe(df, logger=logger)

    assert normalized.empty
    assert warnings


def test_resolve_ai_target_dataframe_loads_minimum_columns_from_signal_file(tmp_path):
    signals_path = tmp_path / "signals_log.csv"
    signals_path.write_text(
        "signal_date,ticker,score,extra\n"
        "2026-02-20,5930,10,unused\n"
        "2026-02-21,660,30,unused\n",
        encoding="utf-8",
    )

    target_df, analysis_date = _resolve_ai_target_dataframe(
        target_date=None,
        selected_items=[],
        vcp_df=None,
        signals_path=str(signals_path),
        logger=type("L", (), {"info": lambda *_a, **_k: None})(),
    )

    assert analysis_date == "2026-02-21"
    assert set(target_df.columns) == {"signal_date", "ticker", "score"}
    assert len(target_df) == 1


def test_resolve_ai_target_limit_delegates_to_runtime_parser(monkeypatch):
    monkeypatch.setattr(
        "services.common_update_ai_analysis_service.resolve_vcp_signals_to_show",
        lambda **_kwargs: 17,
    )

    assert _resolve_ai_target_limit() == 17


def test_empty_signals_preserve_existing_payload(monkeypatch, tmp_path):
    import logging
    (tmp_path / "signals_log.csv").write_text("signal_date,ticker,score\n")
    path = tmp_path / "kr_ai_analysis.json"
    path.write_text("preserved")
    statuses = []
    result = run_ai_analysis_step(
        target_date="2026-03-06", selected_items=["AI Analysis"], vcp_df=None,
        update_item_status=lambda *args: statuses.append(args),
        shared_state=types.SimpleNamespace(STOP_REQUESTED=False),
        logger=logging.getLogger("test"), data_dir=str(tmp_path),
    )
    assert result == {"count": 0}
    assert path.read_text() == "preserved"
    assert statuses[-1][1] == "done"


def test_first_analysis_creates_both_dated_signal_payloads(monkeypatch, tmp_path):
    import logging
    from services import common_update_ai_analysis_service as service
    (tmp_path / "signals_log.csv").write_text("signal_date,ticker,name,score\n2026-03-06,5930,삼성전자,88\n")
    good = {"action": "HOLD", "confidence": 75, "reason": "변동성 축소 뒤 거래량 확인이 필요합니다."}
    monkeypatch.setattr(service, "get_vcp_analyzer", lambda: object())
    monkeypatch.setattr(service, "run_async_analyzer_batch", lambda *_args: {"005930": {"gemini_recommendation": good}})
    result = run_ai_analysis_step(
        target_date="20260306", selected_items=["AI Analysis"], vcp_df=None,
        update_item_status=lambda *_args: None, shared_state=types.SimpleNamespace(STOP_REQUESTED=False),
        logger=logging.getLogger("test"), data_dir=str(tmp_path),
    )
    assert result["count"] == 1
    for prefix in ["ai_analysis_results", "kr_ai_analysis"]:
        payload = json.loads((tmp_path / f"{prefix}_20260306.json").read_text())
        assert payload["signal_date"] == "2026-03-06"
        assert payload["signals"][0]["ticker"] == "005930"
        assert payload["signals"][0]["gemini_recommendation"] == good
        assert not (tmp_path / f"{prefix}.json").exists()
