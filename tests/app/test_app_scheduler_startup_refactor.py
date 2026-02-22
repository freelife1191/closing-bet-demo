#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
app scheduler startup 리팩토링 회귀 테스트
"""

from __future__ import annotations

import logging
import os
import sys
from types import SimpleNamespace


sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

import app as app_module


def test_start_scheduler_logs_warning_when_schedule_dependency_missing(monkeypatch, caplog):
    monkeypatch.setattr(
        app_module.importlib,
        "import_module",
        lambda _name: (_ for _ in ()).throw(ImportError("No module named 'schedule'")),
    )

    with caplog.at_level(logging.WARNING):
        app_module._start_scheduler()

    assert "Scheduler dependency 'schedule' is missing. Skipping scheduler start." in caplog.text


def test_start_scheduler_logs_error_when_scheduler_start_fails(monkeypatch, caplog):
    scheduler_module = SimpleNamespace(
        start_scheduler=lambda: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    monkeypatch.setattr(
        app_module.importlib,
        "import_module",
        lambda _name: scheduler_module,
    )

    with caplog.at_level(logging.ERROR):
        app_module._start_scheduler()

    assert "Failed to start scheduler: boom" in caplog.text


def test_start_scheduler_calls_scheduler_start_once(monkeypatch):
    calls = {"count": 0}

    def _start_scheduler() -> None:
        calls["count"] += 1

    scheduler_module = SimpleNamespace(start_scheduler=_start_scheduler)
    monkeypatch.setattr(
        app_module.importlib,
        "import_module",
        lambda _name: scheduler_module,
    )

    app_module._start_scheduler()

    assert calls["count"] == 1
