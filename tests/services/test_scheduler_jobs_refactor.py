#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Scheduler job 리팩토링 회귀 테스트
"""

from __future__ import annotations

import services.scheduler_jobs as scheduler_jobs


def test_run_jongga_v2_analysis_skips_when_market_closed(monkeypatch):
    monkeypatch.setattr(
        scheduler_jobs.MarketSchedule,
        "is_market_open",
        lambda _date: False,
    )
    calls = {"analyze": 0, "notify": 0}
    monkeypatch.setattr(
        scheduler_jobs,
        "_load_init_data_functions",
        lambda: {
            "create_jongga_v2_latest": lambda: calls.__setitem__("analyze", calls["analyze"] + 1),
            "send_jongga_notification": lambda: calls.__setitem__("notify", calls["notify"] + 1),
        },
    )

    scheduler_jobs.run_jongga_v2_analysis(test_mode=False)

    assert calls == {"analyze": 0, "notify": 0}


def test_run_jongga_v2_analysis_runs_analysis_and_notification(monkeypatch):
    monkeypatch.setattr(
        scheduler_jobs.MarketSchedule,
        "is_market_open",
        lambda _date: True,
    )
    calls = {"analyze": 0, "notify": 0}
    monkeypatch.setattr(
        scheduler_jobs,
        "_load_init_data_functions",
        lambda: {
            "create_jongga_v2_latest": lambda: calls.__setitem__("analyze", calls["analyze"] + 1) or True,
            "send_jongga_notification": lambda: calls.__setitem__("notify", calls["notify"] + 1),
        },
    )

    scheduler_jobs.run_jongga_v2_analysis(test_mode=False)

    assert calls == {"analyze": 1, "notify": 1}


def test_run_daily_closing_analysis_chains_jongga(monkeypatch):
    monkeypatch.setattr(
        scheduler_jobs.MarketSchedule,
        "is_market_open",
        lambda _date: True,
    )
    events: list[tuple[str, object]] = []
    monkeypatch.setattr(
        scheduler_jobs,
        "_load_init_data_functions",
        lambda: {
            "create_daily_prices": lambda: events.append(("daily_prices", None)) or True,
            "create_institutional_trend": lambda: events.append(("institutional_trend", None)) or True,
            "create_signals_log": lambda run_ai: events.append(("create_signals_log", run_ai)) or True,
        },
    )
    monkeypatch.setattr(
        scheduler_jobs,
        "run_jongga_v2_analysis",
        lambda test_mode=False: events.append(("run_jongga_v2_analysis", test_mode)),
    )

    scheduler_jobs.run_daily_closing_analysis(test_mode=True)

    assert events == [
        ("daily_prices", None),
        ("institutional_trend", None),
        ("create_signals_log", True),
        ("run_jongga_v2_analysis", True),
    ]


def test_run_daily_closing_analysis_updates_scheduler_runtime_status(monkeypatch):
    monkeypatch.setattr(
        scheduler_jobs.MarketSchedule,
        "is_market_open",
        lambda _date: True,
    )
    monkeypatch.setattr(
        scheduler_jobs,
        "_load_init_data_functions",
        lambda: {
            "create_daily_prices": lambda: True,
            "create_institutional_trend": lambda: True,
            "create_signals_log": lambda run_ai: True,
        },
    )
    monkeypatch.setattr(
        scheduler_jobs,
        "run_jongga_v2_analysis",
        lambda test_mode=False: None,
    )

    scheduler_updates: list[dict[str, object]] = []
    monkeypatch.setattr(
        scheduler_jobs,
        "set_scheduler_runtime_status",
        lambda **kwargs: scheduler_updates.append(kwargs),
    )

    scheduler_jobs.run_daily_closing_analysis(test_mode=True)

    assert scheduler_updates[0]["data_scheduling_running"] is True
    assert scheduler_updates[0]["vcp_scheduling_running"] is False
    assert any(update.get("vcp_scheduling_running") is True for update in scheduler_updates)
    assert scheduler_updates[-1]["data_scheduling_running"] is False
    assert scheduler_updates[-1]["vcp_scheduling_running"] is False
    assert scheduler_updates[-1]["jongga_scheduling_running"] is False


def test_run_market_gate_sync_skips_when_market_closed(monkeypatch):
    monkeypatch.setattr(
        scheduler_jobs.MarketSchedule,
        "is_market_open",
        lambda _date: False,
    )
    called = {"market_gate": 0}
    monkeypatch.setattr(
        scheduler_jobs,
        "_run_market_gate_analysis",
        lambda: called.__setitem__("market_gate", called["market_gate"] + 1),
    )

    scheduler_jobs.run_market_gate_sync()

    assert called["market_gate"] == 0


def test_run_market_gate_sync_runs_when_market_open(monkeypatch):
    monkeypatch.setattr(
        scheduler_jobs.MarketSchedule,
        "is_market_open",
        lambda _date: True,
    )
    called = {"market_gate": 0}
    monkeypatch.setattr(
        scheduler_jobs,
        "_run_market_gate_analysis",
        lambda: called.__setitem__("market_gate", called["market_gate"] + 1),
    )

    scheduler_jobs.run_market_gate_sync()

    assert called["market_gate"] == 1
