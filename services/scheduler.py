#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
스케줄러 런타임 오케스트레이션.
"""

from __future__ import annotations

import errno
import fcntl
import logging
import os
import sys
import threading
import time
from typing import TextIO

_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

try:
    import schedule
except ImportError:
    schedule = None

from engine.config import app_config
from services.scheduler_jobs import (
    run_daily_closing_analysis,
    run_jongga_v2_analysis,
    run_market_gate_sync,
)
from services.scheduler_loop import compute_scheduler_sleep_seconds

logger = logging.getLogger(__name__)

_scheduler_lock_file: TextIO | None = None
_lock_contention_log_emitted = False
_last_lock_error_errno: int | None = None
_scheduler_retry_thread: threading.Thread | None = None
_scheduler_retry_thread_lock = threading.Lock()
_scheduler_loop_started = False


def _is_schedule_available() -> bool:
    return schedule is not None


def _resolve_scheduler_timezone() -> str:
    configured_timezone = os.getenv("SCHEDULER_TIMEZONE", "").strip()
    if configured_timezone:
        return configured_timezone
    current_timezone = os.getenv("TZ", "").strip()
    if current_timezone:
        return current_timezone
    return "Asia/Seoul"


def _apply_scheduler_timezone() -> str:
    """스케줄러 기준 타임존을 프로세스에 적용한다."""
    scheduler_timezone = _resolve_scheduler_timezone()
    if os.getenv("TZ", "").strip() != scheduler_timezone:
        os.environ["TZ"] = scheduler_timezone

    tzset = getattr(time, "tzset", None)
    if callable(tzset):
        try:
            tzset()
        except Exception as e:
            logger.warning("[Scheduler] TZ 적용 실패(%s): %s", scheduler_timezone, e)
        else:
            logger.info("[Scheduler] Timezone applied: %s", scheduler_timezone)
    else:
        logger.info("[Scheduler] time.tzset unavailable; timezone=%s", scheduler_timezone)

    return scheduler_timezone


def update_market_gate_interval(minutes: int) -> None:
    """실시간으로 Market Gate 업데이트 주기를 변경한다."""
    if not _is_schedule_available():
        logger.warning("[Scheduler] python 'schedule' 모듈이 없어 주기 변경을 건너뜁니다.")
        return

    try:
        schedule.clear("market_gate")
        logger.info("[Scheduler] 기존 Market Gate 스케줄 제거됨")

        schedule.every(minutes).minutes.do(run_market_gate_sync).tag("market_gate")
        logger.info(f"[Scheduler] Market Gate 주기 변경 완료: {minutes}분")
    except Exception as e:
        logger.error(f"[Scheduler] 주기 변경 실패: {e}")


def _acquire_scheduler_lock() -> bool:
    """다중 워커 중 단일 스케줄러 인스턴스만 실행되도록 파일 잠금을 획득한다."""
    global _scheduler_lock_file
    global _lock_contention_log_emitted
    global _last_lock_error_errno

    if _scheduler_lock_file is not None and not _scheduler_lock_file.closed:
        _last_lock_error_errno = None
        return True

    lock_file_path = os.path.join(os.path.dirname(__file__), "scheduler.lock")
    lock_handle: TextIO | None = None

    try:
        lock_handle = open(lock_file_path, "w")
        fcntl.lockf(lock_handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        _scheduler_lock_file = lock_handle
        _lock_contention_log_emitted = False
        _last_lock_error_errno = None
        logger.info(
            "Scheduler lock acquired. Starting scheduler service... (pid=%s)",
            os.getpid(),
        )
        return True
    except OSError as error:
        if lock_handle is not None and not lock_handle.closed:
            lock_handle.close()
        _last_lock_error_errno = error.errno

        if error.errno in {errno.EAGAIN, errno.EACCES}:
            if not _lock_contention_log_emitted:
                logger.info(
                    "[Scheduler] 다른 프로세스가 Scheduler lock 보유 중이므로 현재 프로세스는 스케줄러를 시작하지 않습니다. (path=%s, pid=%s, error=%s)",
                    lock_file_path,
                    os.getpid(),
                    error,
                )
                _lock_contention_log_emitted = True
            else:
                logger.debug(
                    "[Scheduler] lock contention 지속: path=%s, pid=%s, error=%s",
                    lock_file_path,
                    os.getpid(),
                    error,
                )
            return False

        logger.warning(
            "[Scheduler] lock 획득 실패(%s): %s",
            lock_file_path,
            error,
        )
        return False


def _is_lock_contention_error() -> bool:
    contention_errnos = {errno.EAGAIN, errno.EACCES}
    ewo_block = getattr(errno, "EWOULDBLOCK", None)
    if ewo_block is not None:
        contention_errnos.add(ewo_block)
    return _last_lock_error_errno in contention_errnos


def _resolve_lock_retry_interval_seconds() -> float:
    raw = os.getenv("SCHEDULER_LOCK_RETRY_SECONDS", "15").strip()
    try:
        return max(1.0, float(raw))
    except (TypeError, ValueError):
        return 15.0


def _bootstrap_scheduler_after_lock_acquired() -> None:
    global _scheduler_loop_started
    scheduler_timezone = _apply_scheduler_timezone()

    interval = app_config.MARKET_GATE_UPDATE_INTERVAL_MINUTES
    schedule.clear("market_gate")
    schedule.clear("closing_analysis")
    market_gate_job = schedule.every(interval).minutes.do(run_market_gate_sync).tag("market_gate")
    logger.info(
        "Scheduled Market Gate sync every %s minutes (next_run=%s)",
        interval,
        market_gate_job.next_run,
    )

    closing_time = os.getenv("CLOSING_SCHEDULE_TIME", "17:00")
    closing_job = (
        schedule.every()
        .day.at(closing_time)
        .do(run_daily_closing_analysis)
        .tag("closing_analysis")
    )
    logger.info(
        "Scheduled Daily Closing Analysis at %s (timezone=%s, next_run=%s)",
        closing_time,
        scheduler_timezone,
        closing_job.next_run,
    )

    if _scheduler_loop_started:
        logger.info("[Scheduler] scheduler loop already running. skip new thread start.")
        return

    threading.Thread(target=_scheduler_loop, daemon=True).start()
    _scheduler_loop_started = True
    logger.info("Scheduler started successfully")


def _retry_scheduler_start_loop() -> None:
    global _scheduler_retry_thread
    retry_interval = _resolve_lock_retry_interval_seconds()

    try:
        while True:
            if not _is_schedule_available():
                logger.info("[Scheduler] schedule 모듈 미사용 상태로 lock 재시도를 중단합니다.")
                return

            if not app_config.SCHEDULER_ENABLED:
                logger.info("[Scheduler] 비활성화 상태로 lock 재시도를 중단합니다.")
                return

            if _acquire_scheduler_lock():
                logger.info("[Scheduler] lock 재시도 성공. 스케줄러를 시작합니다.")
                try:
                    _bootstrap_scheduler_after_lock_acquired()
                except Exception as error:
                    logger.error("[Scheduler] lock 재시도 후 시작 실패: %s", error)
                return

            time.sleep(retry_interval)
    finally:
        with _scheduler_retry_thread_lock:
            _scheduler_retry_thread = None


def _start_scheduler_retry_thread() -> None:
    global _scheduler_retry_thread
    with _scheduler_retry_thread_lock:
        if _scheduler_retry_thread is not None and _scheduler_retry_thread.is_alive():
            return

        retry_interval = _resolve_lock_retry_interval_seconds()
        _scheduler_retry_thread = threading.Thread(
            target=_retry_scheduler_start_loop,
            daemon=True,
            name="scheduler-lock-retry",
        )
        _scheduler_retry_thread.start()
        logger.info(
            "[Scheduler] lock 경쟁 감지로 재시도 스레드를 시작합니다. (pid=%s, interval=%.1fs)",
            os.getpid(),
            retry_interval,
        )


def _run_scheduler_tick() -> None:
    if not _is_schedule_available():
        time.sleep(compute_scheduler_sleep_seconds(None))
        return

    idle_seconds: float | None = None
    try:
        schedule.run_pending()
        idle_seconds = schedule.idle_seconds()
    except Exception as error:
        logger.exception("[Scheduler] scheduler tick failed: %s", error)

    time.sleep(compute_scheduler_sleep_seconds(idle_seconds))


def _scheduler_loop() -> None:
    if not _is_schedule_available():
        return
    while True:
        _run_scheduler_tick()


def start_scheduler() -> None:
    """스케줄러 시작 (백그라운드 스레드) - Singleton 보장."""
    if not _is_schedule_available():
        logger.warning("Scheduler dependency 'schedule' is missing. Skipping scheduler start.")
        return

    if not app_config.SCHEDULER_ENABLED:
        logger.info("Scheduler is disabled in configuration. Skipping start.")
        return

    if not _acquire_scheduler_lock():
        if _is_lock_contention_error():
            _start_scheduler_retry_thread()
        return

    _bootstrap_scheduler_after_lock_acquired()


def test_scheduler() -> None:
    """테스트 실행: 모든 잡을 즉시 1회 실행."""
    logger.info("========== [TEST MODE] 스케줄러 잡 테스트 시작 ==========")

    logger.info(">>> 테스트: run_jongga_v2_analysis()")
    try:
        run_jongga_v2_analysis(test_mode=True)
    except Exception as e:
        logger.error(f"FAILED: {e}")

    logger.info(">>> 테스트: run_daily_closing_analysis()")
    try:
        run_daily_closing_analysis(test_mode=True)
    except Exception as e:
        logger.error(f"FAILED: {e}")

    logger.info("========== [TEST MODE] 테스트 종료 ==========")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "test":
        test_scheduler()
    else:
        start_scheduler()
        while True:
            time.sleep(1)
