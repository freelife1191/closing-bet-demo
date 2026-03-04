#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Scheduler 모듈 회귀 테스트
"""

from __future__ import annotations

import builtins
import logging
from types import SimpleNamespace

import services.scheduler as scheduler_module


def test_acquire_scheduler_lock_is_idempotent_without_reopening():
    scheduler_module._scheduler_lock_file = None
    opened_handles: list[object] = []
    lock_calls = {"count": 0}

    class _DummyFile:
        def __init__(self):
            self.closed = False

        def close(self):
            self.closed = True

    def _fake_open(*_args, **_kwargs):
        handle = _DummyFile()
        opened_handles.append(handle)
        return handle

    def _fake_lockf(*_args, **_kwargs):
        lock_calls["count"] += 1

    original_open = builtins.open
    original_lockf = scheduler_module.fcntl.lockf
    builtins.open = _fake_open
    scheduler_module.fcntl.lockf = _fake_lockf

    try:
        acquired = scheduler_module._acquire_scheduler_lock()
        assert acquired is True

        first_handle = scheduler_module._scheduler_lock_file
        assert first_handle is not None
        assert first_handle.closed is False

        acquired_again = scheduler_module._acquire_scheduler_lock()
        assert acquired_again is True
        assert scheduler_module._scheduler_lock_file is first_handle
        assert len(opened_handles) == 1
        assert lock_calls["count"] == 1

        first_handle.close()
        scheduler_module._scheduler_lock_file = None
    finally:
        builtins.open = original_open
        scheduler_module.fcntl.lockf = original_lockf


def test_acquire_scheduler_lock_closes_handle_on_lock_failure(monkeypatch):
    scheduler_module._scheduler_lock_file = None
    opened_handles: list[object] = []

    class _DummyFile:
        def __init__(self):
            self.closed = False

        def close(self):
            self.closed = True

    def _fake_open(*_args, **_kwargs):
        handle = _DummyFile()
        opened_handles.append(handle)
        return handle

    monkeypatch.setattr(builtins, "open", _fake_open)
    monkeypatch.setattr(scheduler_module.fcntl, "lockf", lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError()))

    acquired = scheduler_module._acquire_scheduler_lock()

    assert acquired is False
    assert scheduler_module._scheduler_lock_file is None
    assert len(opened_handles) == 1
    assert opened_handles[0].closed is True


def test_acquire_scheduler_lock_logs_warning_on_lock_failure(monkeypatch, caplog):
    scheduler_module._scheduler_lock_file = None

    class _DummyFile:
        closed = False

        def close(self):
            self.closed = True

    monkeypatch.setattr(builtins, "open", lambda *_args, **_kwargs: _DummyFile())
    monkeypatch.setattr(
        scheduler_module.fcntl,
        "lockf",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("lock denied")),
    )

    with caplog.at_level(logging.WARNING):
        acquired = scheduler_module._acquire_scheduler_lock()

    assert acquired is False
    assert "lock denied" in caplog.text


def test_apply_scheduler_timezone_uses_asia_seoul_by_default(monkeypatch):
    monkeypatch.delenv("SCHEDULER_TIMEZONE", raising=False)
    monkeypatch.delenv("TZ", raising=False)
    tzset_calls: list[bool] = []
    monkeypatch.setattr(
        scheduler_module.time,
        "tzset",
        lambda: tzset_calls.append(True),
        raising=False,
    )

    scheduler_module._apply_scheduler_timezone()

    assert scheduler_module.os.environ.get("TZ") == "Asia/Seoul"
    assert tzset_calls == [True]


def test_run_scheduler_tick_survives_run_pending_error(monkeypatch):
    sleep_calls: list[float] = []

    monkeypatch.setattr(
        scheduler_module,
        "schedule",
        SimpleNamespace(
            run_pending=lambda: (_ for _ in ()).throw(RuntimeError("boom")),
            idle_seconds=lambda: None,
        ),
    )
    monkeypatch.setattr(scheduler_module.time, "sleep", lambda seconds: sleep_calls.append(seconds))

    scheduler_module._run_scheduler_tick()

    assert sleep_calls == [1.0]
