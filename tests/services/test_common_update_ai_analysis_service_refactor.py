#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Common Update AI Analysis Service 리팩토링 테스트
"""

from __future__ import annotations

import json
import sys
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


def test_run_ai_analysis_step_writes_empty_placeholder_when_no_signals(monkeypatch, tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "signals_log.csv").write_text("signal_date,ticker,score\n", encoding="utf-8")

    fake_module = types.ModuleType("engine.kr_ai_analyzer")
    fake_module.KrAiAnalyzer = type("KrAiAnalyzer", (), {})
    monkeypatch.setitem(sys.modules, "engine.kr_ai_analyzer", fake_module)
    monkeypatch.setattr(
        "services.common_update_ai_analysis_service.__file__",
        str(tmp_path / "services" / "common_update_ai_analysis_service.py"),
    )

    statuses: list[tuple[str, str]] = []
    logger = type(
        "L",
        (),
        {
            "info": lambda *_a, **_k: None,
            "warning": lambda *_a, **_k: None,
            "error": lambda *_a, **_k: None,
        },
    )()

    run_ai_analysis_step(
        target_date="2026-03-06",
        selected_items=["AI Analysis"],
        vcp_df=None,
        update_item_status=lambda name, status: statuses.append((name, status)),
        shared_state=types.SimpleNamespace(STOP_REQUESTED=False),
        logger=logger,
    )

    latest_payload = json.loads((data_dir / "kr_ai_analysis.json").read_text(encoding="utf-8"))
    dated_payload = json.loads((data_dir / "kr_ai_analysis_20260306.json").read_text(encoding="utf-8"))

    assert statuses == [("AI Analysis", "running"), ("AI Analysis", "done")]
    assert latest_payload["signal_date"] == "2026-03-06"
    assert latest_payload["signals"] == []
    assert dated_payload["signal_date"] == "2026-03-06"
    assert dated_payload["signals"] == []


def test_run_ai_analysis_step_writes_kr_ai_analysis_files_for_targets(monkeypatch, tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "signals_log.csv").write_text(
        "signal_date,ticker,score\n2026-03-06,5930,88\n",
        encoding="utf-8",
    )

    class _DummyAnalyzer:
        def analyze_multiple_stocks(self, tickers):
            assert tickers == ["005930"]
            return {
                "signals": [{"ticker": "005930", "name": "삼성전자"}],
                "market_indices": {"kospi": {"value": 1}},
            }

    fake_module = types.ModuleType("engine.kr_ai_analyzer")
    fake_module.KrAiAnalyzer = _DummyAnalyzer
    monkeypatch.setitem(sys.modules, "engine.kr_ai_analyzer", fake_module)
    monkeypatch.setattr(
        "services.common_update_ai_analysis_service.__file__",
        str(tmp_path / "services" / "common_update_ai_analysis_service.py"),
    )

    statuses: list[tuple[str, str]] = []
    logger = type(
        "L",
        (),
        {
            "info": lambda *_a, **_k: None,
            "warning": lambda *_a, **_k: None,
            "error": lambda *_a, **_k: None,
        },
    )()

    run_ai_analysis_step(
        target_date="2026-03-06",
        selected_items=["AI Analysis"],
        vcp_df=None,
        update_item_status=lambda name, status: statuses.append((name, status)),
        shared_state=types.SimpleNamespace(STOP_REQUESTED=False),
        logger=logger,
    )

    latest_payload = json.loads((data_dir / "kr_ai_analysis.json").read_text(encoding="utf-8"))
    dated_payload = json.loads((data_dir / "kr_ai_analysis_20260306.json").read_text(encoding="utf-8"))

    assert statuses == [("AI Analysis", "running"), ("AI Analysis", "done")]
    assert latest_payload["signal_date"] == "2026-03-06"
    assert latest_payload["signals"] == [{"ticker": "005930", "name": "삼성전자"}]
    assert dated_payload["signals"] == [{"ticker": "005930", "name": "삼성전자"}]
