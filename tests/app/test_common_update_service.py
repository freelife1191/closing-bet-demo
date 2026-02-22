#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Common Update Service 단위 테스트
"""

import sys
import types

from services.common_update_service import run_background_update_pipeline


def _noop_logger():
    return types.SimpleNamespace(
        info=lambda *_a, **_k: None,
        warning=lambda *_a, **_k: None,
        error=lambda *_a, **_k: None,
    )


def test_run_background_update_pipeline_daily_prices_and_finish(monkeypatch):
    calls = {"daily_prices": 0, "finish": 0}
    statuses: list[tuple[str, str]] = []

    fake_scripts = types.ModuleType("scripts")
    fake_scripts.init_data = types.SimpleNamespace(
        create_daily_prices=lambda *_a, **_k: calls.__setitem__("daily_prices", calls["daily_prices"] + 1),
        create_institutional_trend=lambda *_a, **_k: None,
        create_signals_log=lambda *_a, **_k: None,
    )
    monkeypatch.setitem(sys.modules, "scripts", fake_scripts)

    shared_state = types.SimpleNamespace(STOP_REQUESTED=False)

    run_background_update_pipeline(
        target_date="2026-02-21",
        selected_items=["Daily Prices"],
        force=False,
        update_item_status=lambda name, status: statuses.append((name, status)),
        finish_update=lambda: calls.__setitem__("finish", calls["finish"] + 1),
        shared_state=shared_state,
        logger=_noop_logger(),
    )

    assert calls["daily_prices"] == 1
    assert calls["finish"] == 1
    assert statuses == [("Daily Prices", "running"), ("Daily Prices", "done")]


def test_run_background_update_pipeline_honors_stop_request(monkeypatch):
    calls = {"finish": 0}
    statuses: list[tuple[str, str]] = []

    fake_scripts = types.ModuleType("scripts")
    fake_scripts.init_data = types.SimpleNamespace(
        create_daily_prices=lambda *_a, **_k: None,
        create_institutional_trend=lambda *_a, **_k: None,
        create_signals_log=lambda *_a, **_k: None,
    )
    monkeypatch.setitem(sys.modules, "scripts", fake_scripts)

    shared_state = types.SimpleNamespace(STOP_REQUESTED=True)

    run_background_update_pipeline(
        target_date="2026-02-21",
        selected_items=["Daily Prices"],
        force=False,
        update_item_status=lambda name, status: statuses.append((name, status)),
        finish_update=lambda: calls.__setitem__("finish", calls["finish"] + 1),
        shared_state=shared_state,
        logger=_noop_logger(),
    )

    assert calls["finish"] == 1
    assert statuses == []


def test_run_background_update_pipeline_ai_jongga_marks_ai_analysis_done(monkeypatch):
    statuses: list[tuple[str, str]] = []
    calls = {"finish": 0, "screener": 0}

    fake_scripts = types.ModuleType("scripts")
    fake_scripts.init_data = types.SimpleNamespace(
        create_daily_prices=lambda *_a, **_k: None,
        create_institutional_trend=lambda *_a, **_k: None,
        create_signals_log=lambda *_a, **_k: None,
    )
    monkeypatch.setitem(sys.modules, "scripts", fake_scripts)

    async def _run_screener(*_a, **_k):
        calls["screener"] += 1

    fake_generator = types.ModuleType("engine.generator")
    fake_generator.run_screener = _run_screener
    monkeypatch.setitem(sys.modules, "engine.generator", fake_generator)

    shared_state = types.SimpleNamespace(STOP_REQUESTED=False)

    run_background_update_pipeline(
        target_date=None,
        selected_items=["AI Jongga V2"],
        force=False,
        update_item_status=lambda name, status: statuses.append((name, status)),
        finish_update=lambda: calls.__setitem__("finish", calls["finish"] + 1),
        shared_state=shared_state,
        logger=_noop_logger(),
    )

    assert calls["screener"] == 1
    assert calls["finish"] == 1
    assert ("AI Jongga V2", "running") in statuses
    assert ("AI Jongga V2", "done") in statuses
    assert ("AI Analysis", "done") in statuses
