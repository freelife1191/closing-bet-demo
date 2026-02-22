#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KR Market Jongga Runtime Service

종가베팅 백그라운드 실행/알림 전송 로직.
"""

from __future__ import annotations

import asyncio
import logging
import sys
import threading
from datetime import datetime
from typing import Any, Callable


def _reload_engine_submodules() -> None:
    for module_name in [name for name in list(sys.modules.keys()) if name.startswith("engine.")]:
        del sys.modules[module_name]


def _run_coro_in_fresh_loop(coro: Any, logger: logging.Logger) -> Any:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        try:
            loop.run_until_complete(loop.shutdown_asyncgens())
        except Exception as e:
            logger.warning(f"Error shutting down async generators: {e}")
        loop.close()
        asyncio.set_event_loop(None)


def _send_jongga_notification_from_result(result: Any, logger: logging.Logger) -> None:
    try:
        raw_signals = getattr(result, "signals", []) or []
        signals = []
        for signal in raw_signals:
            to_dict = getattr(signal, "to_dict", None)
            if callable(to_dict):
                signals.append(to_dict())

        if not signals:
            logger.info("[Notification] 발송할 시그널 없음 (0개)")
            return

        result_date = getattr(result, "date", None)
        if hasattr(result_date, "strftime"):
            date_str = result_date.strftime("%Y-%m-%d")
        else:
            date_str = str(result_date or datetime.now().date())

        from services.notifier import send_jongga_notification

        results = send_jongga_notification(signals, date_str)
        logger.info(f"[Notification] 메신저 발송 결과: {results}")
    except Exception as e:
        logger.error(f"[Notification] 메신저 발송 중 오류: {e}")


def run_jongga_v2_background_pipeline(
    capital: int,
    markets: list[str] | None,
    target_date: str | None,
    save_status: Callable[[bool], None],
    logger: logging.Logger,
) -> None:
    """종가베팅 v2 엔진 백그라운드 실행 파이프라인."""
    selected_markets = markets or ["KOSPI", "KOSDAQ"]
    save_status(True)

    logger.info("[Background] Jongga V2 Engine Started...")
    if target_date:
        logger.info(f"[테스트 모드] 지정 날짜 기준 분석: {target_date}")

    try:
        _reload_engine_submodules()

        from engine.generator import run_screener, save_result_to_json

        result = _run_coro_in_fresh_loop(
            run_screener(
                capital=capital,
                markets=selected_markets,
                target_date=target_date,
            ),
            logger=logger,
        )

        if result:
            save_result_to_json(result)
            _send_jongga_notification_from_result(result, logger)

        logger.info("[Background] Jongga V2 Engine Completed Successfully.")
    finally:
        save_status(False)
        logger.info("[Background] Jongga V2 Status reset to False")


def launch_jongga_v2_screener(
    req_data: dict[str, Any],
    load_v2_status: Callable[[], dict[str, Any]],
    save_v2_status: Callable[[bool], None],
    run_jongga_background: Callable[..., None],
    logger: logging.Logger,
) -> tuple[int, dict[str, Any]]:
    """종가베팅 v2 백그라운드 스크리너 실행을 시작한다."""
    status = load_v2_status()
    if status.get("isRunning", False):
        return 409, {
            "status": "error",
            "message": "Engine is already running. Please wait.",
        }

    capital = req_data.get("capital", 50_000_000)
    markets = req_data.get("markets", ["KOSPI", "KOSDAQ"])
    target_date = req_data.get("target_date")

    def _run_wrapper() -> None:
        try:
            run_jongga_background(capital=capital, markets=markets, target_date=target_date)
        except Exception as e:
            logger.error(f"Background Engine Failed: {e}")
        finally:
            save_v2_status(False)

    thread = threading.Thread(target=_run_wrapper, daemon=True)
    thread.start()
    save_v2_status(True)

    message = "Engine started in background. Poll /jongga-v2/status for completion."
    if target_date:
        message = f"[테스트 모드] {target_date} 기준 분석 시작. Poll /jongga-v2/status for completion."

    return 200, {
        "status": "started",
        "message": message,
        "target_date": target_date,
    }
