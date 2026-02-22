#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Scheduler 옵션 의존성(schedule) 회귀 테스트
"""

from __future__ import annotations

import services.scheduler as scheduler_module


def test_start_scheduler_skips_when_schedule_dependency_missing(monkeypatch):
    lock_calls = {"count": 0}

    monkeypatch.setattr(scheduler_module, "schedule", None)
    monkeypatch.setattr(
        scheduler_module,
        "_acquire_scheduler_lock",
        lambda: lock_calls.__setitem__("count", lock_calls["count"] + 1) or True,
    )

    scheduler_module.start_scheduler()

    assert lock_calls["count"] == 0


def test_update_market_gate_interval_returns_cleanly_when_schedule_missing(monkeypatch):
    monkeypatch.setattr(scheduler_module, "schedule", None)

    scheduler_module.update_market_gate_interval(30)
