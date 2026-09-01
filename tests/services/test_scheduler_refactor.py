#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Scheduler 모듈 회귀 테스트
"""

from __future__ import annotations

import builtins
import errno
import logging
from types import SimpleNamespace

import schedule

import services.scheduler as scheduler_module


def test_acquire_scheduler_lock_is_idempotent_without_reopening():
    scheduler_module._scheduler_lock_file = None
    scheduler_module._lock_contention_log_emitted = False
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
    scheduler_module._lock_contention_log_emitted = False
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


def test_acquire_scheduler_lock_logs_warning_on_unexpected_lock_failure(monkeypatch, caplog):
    scheduler_module._scheduler_lock_file = None
    scheduler_module._lock_contention_log_emitted = False

    class _DummyFile:
        closed = False

        def close(self):
            self.closed = True

    monkeypatch.setattr(builtins, "open", lambda *_args, **_kwargs: _DummyFile())
    monkeypatch.setattr(
        scheduler_module.fcntl,
        "lockf",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError(errno.EBADF, "lock denied")),
    )

    with caplog.at_level(logging.WARNING):
        acquired = scheduler_module._acquire_scheduler_lock()

    assert acquired is False
    assert "lock denied" in caplog.text


def test_acquire_scheduler_lock_logs_info_when_lock_is_held(monkeypatch, caplog):
    scheduler_module._scheduler_lock_file = None
    scheduler_module._lock_contention_log_emitted = False

    class _DummyFile:
        closed = False

        def close(self):
            self.closed = True

    monkeypatch.setattr(builtins, "open", lambda *_args, **_kwargs: _DummyFile())
    monkeypatch.setattr(
        scheduler_module.fcntl,
        "lockf",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            OSError(errno.EAGAIN, "Resource temporarily unavailable")
        ),
    )

    with caplog.at_level(logging.INFO):
        acquired = scheduler_module._acquire_scheduler_lock()

    assert acquired is False
    assert "다른 프로세스가 Scheduler lock 보유 중" in caplog.text
    assert all(record.levelno < logging.WARNING for record in caplog.records)


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


def test_test_scheduler_runs_closing_chain_once(monkeypatch):
    calls: list[tuple[str, bool]] = []
    monkeypatch.setattr(
        scheduler_module,
        "run_jongga_v2_analysis",
        lambda test_mode=False: calls.append(("jongga", test_mode)),
    )
    monkeypatch.setattr(
        scheduler_module,
        "run_daily_closing_analysis",
        lambda test_mode=False: calls.append(("closing", test_mode)),
    )

    scheduler_module.test_scheduler()

    assert calls == [("closing", True)]


def test_start_scheduler_skips_lock_when_disabled(monkeypatch):
    monkeypatch.setenv("SCHEDULER_ENABLED", "false")
    monkeypatch.setattr(scheduler_module, "schedule", object())
    lock_calls = {"count": 0}
    monkeypatch.setattr(
        scheduler_module,
        "_acquire_scheduler_lock",
        lambda: lock_calls.__setitem__("count", lock_calls["count"] + 1) or True,
    )

    scheduler_module.start_scheduler()

    assert lock_calls["count"] == 0


def test_start_scheduler_starts_retry_thread_on_lock_contention(monkeypatch):
    monkeypatch.setenv("SCHEDULER_ENABLED", "true")
    monkeypatch.setattr(scheduler_module, "schedule", object())
    monkeypatch.setattr(scheduler_module, "_acquire_scheduler_lock", lambda: False)
    monkeypatch.setattr(scheduler_module, "_last_lock_error_errno", errno.EAGAIN, raising=False)
    retry_calls = {"count": 0}
    monkeypatch.setattr(
        scheduler_module,
        "_start_scheduler_retry_thread",
        lambda: retry_calls.__setitem__("count", retry_calls["count"] + 1),
        raising=False,
    )

    scheduler_module.start_scheduler()

    assert retry_calls["count"] == 1


def _make_fake_schedule(registered: list, cleared: list):
    """schedule 대역. 시각 형식은 진짜 라이브러리에 물어봐 같은 값만 통과시킨다."""

    class _FakeJob:
        def __init__(self, sink: dict):
            self._sink = sink
            self.next_run = "next"

        def do(self, job_func):
            self._sink["job"] = job_func
            return self

        def tag(self, name):
            self._sink["tag"] = name
            registered.append(self._sink)
            return self

    class _FakeDay:
        def __init__(self, sink: dict):
            self._sink = sink

        def at(self, time_str):
            schedule.every().day.at(time_str)
            schedule.clear()
            self._sink["at"] = time_str
            return _FakeJob(self._sink)

    class _FakeEvery:
        def __init__(self, sink: dict):
            self.day = _FakeDay(sink)
            self.minutes = _FakeJob(sink)

    def _every(interval=None):
        return _FakeEvery({"interval": interval})

    return SimpleNamespace(every=_every, clear=cleared.append)


def _bootstrap_with_fake_schedule(monkeypatch):
    registered: list[dict] = []
    cleared: list[str] = []
    monkeypatch.setattr(scheduler_module, "schedule", _make_fake_schedule(registered, cleared))
    monkeypatch.setattr(scheduler_module, "_apply_scheduler_timezone", lambda: "Asia/Seoul")
    monkeypatch.setattr(scheduler_module, "_scheduler_loop_started", True, raising=False)

    scheduler_module._bootstrap_scheduler_after_lock_acquired()

    return registered, cleared


def test_bootstrap_registers_each_job_once_with_the_configured_time(monkeypatch):
    monkeypatch.setenv("CLOSING_SCHEDULE_TIME", "16:05")

    registered, cleared = _bootstrap_with_fake_schedule(monkeypatch)

    assert [entry["tag"] for entry in registered] == ["market_gate", "closing_analysis"]
    assert cleared == ["market_gate", "closing_analysis"]
    closing = registered[1]
    assert closing["at"] == "16:05"
    assert closing["job"] is scheduler_module.run_daily_closing_analysis


def test_bootstrap_survives_a_schedule_time_the_library_rejects(monkeypatch):
    """시각 하나가 어긋나도 잡 등록과 루프 시작이 통째로 무산되면 안 된다."""
    monkeypatch.setenv("CLOSING_SCHEDULE_TIME", "9:05")

    registered, _ = _bootstrap_with_fake_schedule(monkeypatch)

    assert [entry["tag"] for entry in registered] == ["market_gate", "closing_analysis"]
    assert registered[1]["at"] == "17:00"


def test_resolve_daily_schedule_time_accepts_exactly_what_schedule_accepts(monkeypatch):
    """받아들이는 형식을 손으로 다시 정의하면 라이브러리와 어긋나므로 실제 규칙과 대조한다."""
    candidates = ["16:05", "17:00:30", "23:59", "9:05", "0:00", "25:00", "1:2", "bogus", "17:00  # 주석"]

    for configured in candidates:
        try:
            schedule.every().day.at(configured)
            accepted = True
        except Exception:
            accepted = False
        finally:
            schedule.clear()

        monkeypatch.setenv("CLOSING_SCHEDULE_TIME", configured)
        resolved = scheduler_module._resolve_daily_schedule_time("CLOSING_SCHEDULE_TIME", "17:00")
        assert resolved == (configured if accepted else "17:00"), configured
        assert not schedule.jobs, f"확인 과정에서 잡이 등록되면 안 된다: {configured!r}"

    for blank in ("", "   "):
        monkeypatch.setenv("CLOSING_SCHEDULE_TIME", blank)
        assert (
            scheduler_module._resolve_daily_schedule_time("CLOSING_SCHEDULE_TIME", "17:00")
            == "17:00"
        )

    monkeypatch.delenv("CLOSING_SCHEDULE_TIME", raising=False)
    assert (
        scheduler_module._resolve_daily_schedule_time("CLOSING_SCHEDULE_TIME", "17:00") == "17:00"
    )


def test_resolve_daily_schedule_time_warns_which_variable_was_ignored(monkeypatch, caplog):
    monkeypatch.setenv("CLOSING_SCHEDULE_TIME", "25:00")

    with caplog.at_level(logging.WARNING, logger=scheduler_module.logger.name):
        assert (
            scheduler_module._resolve_daily_schedule_time("CLOSING_SCHEDULE_TIME", "17:00")
            == "17:00"
        )

    assert "CLOSING_SCHEDULE_TIME" in caplog.text
    assert "25:00" in caplog.text
