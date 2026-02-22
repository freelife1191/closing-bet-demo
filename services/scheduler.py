#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
스케줄러 런타임 오케스트레이션.
"""

from __future__ import annotations

import fcntl
import logging
import os
import threading
import time
from typing import TextIO

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


def _is_schedule_available() -> bool:
    return schedule is not None


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

    if _scheduler_lock_file is not None and not _scheduler_lock_file.closed:
        return True

    lock_file_path = os.path.join(os.path.dirname(__file__), "scheduler.lock")
    lock_handle: TextIO | None = None

    try:
        lock_handle = open(lock_file_path, "w")
        fcntl.lockf(lock_handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        _scheduler_lock_file = lock_handle
        logger.info("Scheduler lock acquired. Starting scheduler service...")
        return True
    except OSError:
        if lock_handle is not None and not lock_handle.closed:
            lock_handle.close()
        return False


def _scheduler_loop() -> None:
    if not _is_schedule_available():
        return
    while True:
        schedule.run_pending()
        idle_seconds = schedule.idle_seconds()
        time.sleep(compute_scheduler_sleep_seconds(idle_seconds))


def start_scheduler() -> None:
    """스케줄러 시작 (백그라운드 스레드) - Singleton 보장."""
    if not _is_schedule_available():
        logger.warning("Scheduler dependency 'schedule' is missing. Skipping scheduler start.")
        return

    if not _acquire_scheduler_lock():
        return

    if not app_config.SCHEDULER_ENABLED:
        logger.info("Scheduler is disabled in configuration. Skipping start.")
        return

    interval = app_config.MARKET_GATE_UPDATE_INTERVAL_MINUTES
    schedule.every(interval).minutes.do(run_market_gate_sync).tag("market_gate")
    logger.info(f"Scheduled Market Gate sync every {interval} minutes")

    closing_time = os.getenv("CLOSING_SCHEDULE_TIME", "16:00")
    schedule.every().day.at(closing_time).do(run_daily_closing_analysis)
    logger.info(f"Scheduled Daily Closing Analysis at {closing_time} (Chains Jongga V2)")

    threading.Thread(target=_scheduler_loop, daemon=True).start()
    logger.info("Scheduler started successfully")


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
