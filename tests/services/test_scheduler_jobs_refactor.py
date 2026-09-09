#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Scheduler job 리팩토링 회귀 테스트
"""

from __future__ import annotations

import sys
import types

import pytest

import services.scheduler_jobs as scheduler_jobs


def test_run_jongga_v2_analysis_skips_when_market_closed(monkeypatch):
    monkeypatch.setattr(
        scheduler_jobs,
        "set_scheduler_runtime_status",
        lambda **_kwargs: None,
    )
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
        scheduler_jobs,
        "set_scheduler_runtime_status",
        lambda **_kwargs: None,
    )
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
        scheduler_jobs,
        "set_scheduler_runtime_status",
        lambda **_kwargs: None,
    )
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
            "send_jongga_notification": lambda: events.append(("send_jongga_notification", None)),
        },
    )
    monkeypatch.setattr(
        scheduler_jobs,
        "run_jongga_v2_analysis",
        lambda test_mode=False, send_notification=True: events.append(
            ("run_jongga_v2_analysis", (test_mode, send_notification))
        )
        or True,
    )

    scheduler_jobs.run_daily_closing_analysis(test_mode=True)

    assert events == [
        ("daily_prices", None),
        ("institutional_trend", None),
        ("create_signals_log", True),
        ("run_jongga_v2_analysis", (True, False)),
        ("send_jongga_notification", None),
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
            "send_jongga_notification": lambda: True,
        },
    )
    monkeypatch.setattr(
        scheduler_jobs,
        "run_jongga_v2_analysis",
        lambda test_mode=False, send_notification=True: True,
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


@pytest.mark.parametrize(
    ("failed_step", "daily_result", "institutional_result", "vcp_result", "jongga_result"),
    [
        ("일별 주가", False, True, True, True),
        ("기관/외인 수급", True, False, True, True),
        ("VCP", True, True, False, True),
        ("종가베팅", True, True, True, False),
        ("종가베팅", True, True, True, None),
    ],
)
def test_run_daily_closing_analysis_logs_each_failed_step_without_false_completion(
    monkeypatch,
    caplog,
    failed_step,
    daily_result,
    institutional_result,
    vcp_result,
    jongga_result,
):
    """단계별 실패를 전체 완료로 기록하는 회귀를 막는다."""
    caplog.set_level("INFO", logger=scheduler_jobs.__name__)
    monkeypatch.setattr(scheduler_jobs, "set_scheduler_runtime_status", lambda **_kwargs: None)
    events: list[str] = []
    monkeypatch.setattr(
        scheduler_jobs,
        "_load_init_data_functions",
        lambda: {
            "create_daily_prices": lambda: events.append("daily") or daily_result,
            "create_institutional_trend": lambda: events.append("institutional") or institutional_result,
            "create_signals_log": lambda run_ai: events.append("vcp") or vcp_result,
            "send_jongga_notification": lambda: events.append("notify"),
        },
    )
    monkeypatch.setattr(
        scheduler_jobs,
        "run_jongga_v2_analysis",
        lambda **_kwargs: events.append("jongga") or jongga_result,
    )

    scheduler_jobs.run_daily_closing_analysis(test_mode=True)

    assert events == (["daily", "institutional", "vcp", "jongga", "notify"] if jongga_result else ["daily", "institutional", "vcp", "jongga"])
    assert f"부분 실패: {failed_step}" in caplog.text
    assert "장 마감 정기 분석 및 종가베팅 완료" not in caplog.text


def test_run_daily_closing_analysis_notifies_after_compound_failure_before_partial_log(
    monkeypatch,
    caplog,
):
    """앞 단계가 복합 실패해도 종가 성공 알림 뒤에 부분 실패를 남긴다."""
    caplog.set_level("INFO", logger=scheduler_jobs.__name__)
    monkeypatch.setattr(scheduler_jobs, "set_scheduler_runtime_status", lambda **_kwargs: None)
    events: list[str] = []
    monkeypatch.setattr(
        scheduler_jobs,
        "_load_init_data_functions",
        lambda: {
            "create_daily_prices": lambda: events.append("daily") or False,
            "create_institutional_trend": lambda: events.append("institutional") or False,
            "create_signals_log": lambda run_ai: events.append("vcp") or False,
            "send_jongga_notification": lambda: events.append("notify"),
        },
    )
    monkeypatch.setattr(
        scheduler_jobs,
        "run_jongga_v2_analysis",
        lambda **_kwargs: events.append("jongga") or True,
    )

    scheduler_jobs.run_daily_closing_analysis(test_mode=True)

    messages = [record.getMessage() for record in caplog.records]
    notification_index = messages.index("<<< [Scheduler] 종가베팅 알림 처리 종료")
    partial_failure_index = next(
        index for index, message in enumerate(messages) if "부분 실패: 일별 주가, 기관/외인 수급, VCP" in message
    )
    assert events == ["daily", "institutional", "vcp", "jongga", "notify"]
    assert notification_index < partial_failure_index
    assert "장 마감 정기 분석 및 종가베팅 완료" not in caplog.text


def test_run_daily_closing_analysis_treats_none_from_first_three_steps_as_success(
    monkeypatch,
    caplog,
):
    """앞 세 단계의 None 호환을 False 판정으로 좁히는 회귀를 막는다."""
    caplog.set_level("INFO", logger=scheduler_jobs.__name__)
    monkeypatch.setattr(scheduler_jobs, "set_scheduler_runtime_status", lambda **_kwargs: None)
    monkeypatch.setattr(
        scheduler_jobs,
        "_load_init_data_functions",
        lambda: {
            "create_daily_prices": lambda: None,
            "create_institutional_trend": lambda: None,
            "create_signals_log": lambda run_ai: None,
            "send_jongga_notification": lambda: None,
        },
    )
    monkeypatch.setattr(scheduler_jobs, "run_jongga_v2_analysis", lambda **_kwargs: True)

    scheduler_jobs.run_daily_closing_analysis(test_mode=True)

    messages = [record.getMessage() for record in caplog.records]
    notification_index = messages.index("<<< [Scheduler] 종가베팅 알림 처리 종료")
    completion_index = messages.index("<<< [Scheduler] 장 마감 정기 분석 및 종가베팅 완료")
    assert notification_index < completion_index
    assert "장 마감 정기 분석 및 종가베팅 완료" in caplog.text
    assert "부분 실패" not in caplog.text


@pytest.mark.parametrize("failure", ["daily", "notification"])
def test_run_daily_closing_analysis_does_not_log_completion_after_exception_and_resets_status(
    monkeypatch,
    caplog,
    failure,
):
    """수집 또는 알림 예외 뒤에 완료를 기록하거나 실행 상태를 남기는 회귀를 막는다."""
    caplog.set_level("INFO", logger=scheduler_jobs.__name__)
    scheduler_updates: list[dict[str, object]] = []
    monkeypatch.setattr(
        scheduler_jobs,
        "set_scheduler_runtime_status",
        lambda **kwargs: scheduler_updates.append(kwargs),
    )

    def raise_failure() -> None:
        raise RuntimeError(f"{failure} failure")

    monkeypatch.setattr(
        scheduler_jobs,
        "_load_init_data_functions",
        lambda: {
            "create_daily_prices": raise_failure if failure == "daily" else lambda: True,
            "create_institutional_trend": lambda: True,
            "create_signals_log": lambda run_ai: True,
            "send_jongga_notification": raise_failure if failure == "notification" else lambda: None,
        },
    )
    monkeypatch.setattr(scheduler_jobs, "run_jongga_v2_analysis", lambda **_kwargs: True)

    scheduler_jobs.run_daily_closing_analysis(test_mode=True)

    assert "장 마감 정기 분석 및 종가베팅 완료" not in caplog.text
    assert f"장 마감 정기 분석 실패: {failure} failure" in caplog.text
    assert scheduler_updates[-1] == {
        "data_scheduling_running": False,
        "vcp_scheduling_running": False,
        "jongga_scheduling_running": False,
    }


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


def test_scheduler_path_resolves_init_data_through_scripts_package(monkeypatch):
    """scripts 패키지에 심은 대역이 스케줄러 잡에도 그대로 적용된다.

    임포트 경로를 통일하기 전에는 이 경로만 최상위 init_data 를 따로 열었다. 그래서
    다른 검사들이 쓰는 fake_scripts 대역이 스케줄러 잡에는 닿지 않았고, 그 경로만
    검증에서 빠져 있었다. 이 검사는 `_load_init_data_functions` 를 바꿔치기하지 않고
    실제 임포트를 그대로 태워서 그 구멍이 메워졌음을 고정한다.
    """
    monkeypatch.setattr(
        scheduler_jobs,
        "set_scheduler_runtime_status",
        lambda **_kwargs: None,
    )
    # 회귀가 나면 대역을 우회해 진짜 init_data 가 열리고 실제 수집과 알림 발송까지
    # 돌아 버린다. 최상위 이름을 미리 막아 그 전에 ImportError 로 끝나게 한다.
    monkeypatch.setitem(sys.modules, "init_data", None)

    calls = {"analyze": 0, "notify": 0}
    fake_scripts = types.ModuleType("scripts")
    fake_scripts.init_data = types.SimpleNamespace(
        create_signals_log=lambda **_k: None,
        create_jongga_v2_latest=lambda: calls.__setitem__("analyze", calls["analyze"] + 1) or True,
        create_daily_prices=lambda **_k: None,
        create_institutional_trend=lambda **_k: None,
        send_jongga_notification=lambda: calls.__setitem__("notify", calls["notify"] + 1),
    )
    monkeypatch.setitem(sys.modules, "scripts", fake_scripts)
    monkeypatch.setattr(
        scheduler_jobs.MarketSchedule,
        "is_market_open",
        lambda _date: True,
    )

    assert scheduler_jobs.run_jongga_v2_analysis(test_mode=False) is True
    assert calls == {"analyze": 1, "notify": 1}
