#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Common Update Pipeline Steps 리팩토링 테스트
"""

from __future__ import annotations

import datetime
import sys
import types

import pandas as pd

from services.common_update_pipeline_steps import (
    run_institutional_trend_step,
    run_ai_jongga_v2_step,
    run_daily_prices_step,
    run_vcp_signals_step,
)


def _logger():
    return types.SimpleNamespace(
        info=lambda *_a, **_k: None,
        warning=lambda *_a, **_k: None,
        error=lambda *_a, **_k: None,
    )


def test_run_daily_prices_step_sets_error_on_failure():
    statuses: list[tuple[str, str]] = []

    class _InitData:
        @staticmethod
        def create_daily_prices(*_a, **_k):
            raise RuntimeError("fail")

    run_daily_prices_step(
        init_data=_InitData(),
        target_date="2026-02-21",
        force=False,
        update_item_status=lambda name, status: statuses.append((name, status)),
        shared_state=types.SimpleNamespace(STOP_REQUESTED=False),
        logger=_logger(),
    )

    assert statuses == [("Daily Prices", "running"), ("Daily Prices", "error")]


def test_run_daily_prices_step_sets_error_when_step_returns_false():
    statuses: list[tuple[str, str]] = []

    class _InitData:
        @staticmethod
        def create_daily_prices(*_a, **_k):
            return False

    run_daily_prices_step(
        init_data=_InitData(),
        target_date="2026-02-21",
        force=False,
        update_item_status=lambda name, status: statuses.append((name, status)),
        shared_state=types.SimpleNamespace(STOP_REQUESTED=False),
        logger=_logger(),
    )

    assert statuses == [("Daily Prices", "running"), ("Daily Prices", "error")]


def test_run_daily_prices_step_sets_error_when_latest_date_is_stale(tmp_path, monkeypatch):
    statuses: list[tuple[str, str]] = []
    daily_prices_path = tmp_path / "daily_prices.csv"
    pd.DataFrame(
        [{"date": "2026-03-03", "ticker": "005930", "open": 1, "high": 1, "low": 1, "close": 1, "volume": 1}]
    ).to_csv(daily_prices_path, index=False, encoding="utf-8-sig")

    class _InitData:
        @staticmethod
        def create_daily_prices(*_a, **_k):
            return True

        @staticmethod
        def get_last_trading_date(reference_date=None):
            _ = reference_date
            return "20260304", datetime.datetime(2026, 3, 4)

    from services import common_update_pipeline_steps as step_module

    monkeypatch.setattr(
        step_module,
        "_resolve_data_file_path",
        lambda filename: str(daily_prices_path) if filename == "daily_prices.csv" else filename,
    )

    run_daily_prices_step(
        init_data=_InitData(),
        target_date="2026-03-04",
        force=False,
        update_item_status=lambda name, status: statuses.append((name, status)),
        shared_state=types.SimpleNamespace(STOP_REQUESTED=False),
        logger=_logger(),
    )

    assert statuses == [("Daily Prices", "running"), ("Daily Prices", "error")]


def test_run_institutional_trend_step_sets_error_when_latest_date_is_stale(tmp_path, monkeypatch):
    statuses: list[tuple[str, str]] = []
    trend_path = tmp_path / "all_institutional_trend_data.csv"
    pd.DataFrame(
        [{"date": "2026-03-03", "ticker": "005930", "foreign_buy": 0, "inst_buy": 0}]
    ).to_csv(trend_path, index=False, encoding="utf-8-sig")

    class _InitData:
        @staticmethod
        def create_institutional_trend(*_a, **_k):
            return True

        @staticmethod
        def get_last_trading_date(reference_date=None):
            _ = reference_date
            return "20260304", datetime.datetime(2026, 3, 4)

    from services import common_update_pipeline_steps as step_module

    monkeypatch.setattr(
        step_module,
        "_resolve_data_file_path",
        lambda filename: str(trend_path) if filename == "all_institutional_trend_data.csv" else filename,
    )

    run_institutional_trend_step(
        init_data=_InitData(),
        target_date="2026-03-04",
        force=False,
        update_item_status=lambda name, status: statuses.append((name, status)),
        shared_state=types.SimpleNamespace(STOP_REQUESTED=False),
        logger=_logger(),
    )

    assert statuses == [("Institutional Trend", "running"), ("Institutional Trend", "error")]


def test_run_vcp_signals_step_returns_dataframe_and_marks_done(monkeypatch):
    statuses: list[tuple[str, str]] = []
    expected = pd.DataFrame([{"ticker": "005930"}])

    class _InitData:
        @staticmethod
        def create_signals_log(_target_date):
            return expected

    class _DummyTracker:
        def update_open_signals(self):
            return None

    fake_signal_tracker = types.ModuleType("engine.signal_tracker")
    fake_signal_tracker.SignalTracker = _DummyTracker
    monkeypatch.setitem(sys.modules, "engine.signal_tracker", fake_signal_tracker)

    result = run_vcp_signals_step(
        init_data=_InitData(),
        target_date="2026-02-21",
        update_item_status=lambda name, status: statuses.append((name, status)),
        shared_state=types.SimpleNamespace(STOP_REQUESTED=False),
        logger=_logger(),
    )

    assert result is expected
    assert statuses == [("VCP Signals", "running"), ("VCP Signals", "done")]


def test_run_ai_jongga_v2_step_marks_only_ai_jongga_status(monkeypatch):
    statuses: list[tuple[str, str]] = []

    async def _run_screener(*_a, **_k):
        return None

    fake_generator = types.ModuleType("engine.generator")
    fake_generator.run_screener = _run_screener
    monkeypatch.setitem(sys.modules, "engine.generator", fake_generator)

    run_ai_jongga_v2_step(
        target_date=None,
        update_item_status=lambda name, status: statuses.append((name, status)),
        shared_state=types.SimpleNamespace(STOP_REQUESTED=False),
        logger=_logger(),
    )

    assert statuses == [("AI Jongga V2", "running"), ("AI Jongga V2", "done")]
