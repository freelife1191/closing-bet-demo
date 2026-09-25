#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KR Market Jongga Runtime Service

종가베팅 백그라운드 실행/알림 전송 로직.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import threading
from contextlib import AbstractContextManager, nullcontext
from datetime import datetime
from typing import Any, Callable

from services.kr_market_data_cache_service import atomic_write_text


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
    data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
    guard_key: str | None = None
    guard_claimed = False
    guard_marked = False
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

        from services.jongga_notification_guard_service import (
            claim_jongga_notification_send,
            mark_jongga_notification_sent,
        )
        from services.notifier import NotificationService

        notifier = NotificationService()
        if not notifier.enabled:
            logger.info("[Notification] 알림 비활성화 상태 - 발송 생략")
            return

        guard_claimed, guard_key = claim_jongga_notification_send(
            data_dir=data_dir,
            date_str=date_str,
            signals=signals,
            notification_type="daily",
        )
        if not guard_claimed:
            logger.info(f"[Notification] 중복 종가베팅 알림 생략: {guard_key}")
            return

        results = notifier.send_all(signals, date_str)
        mark_jongga_notification_sent(data_dir, guard_key)
        guard_marked = True
        logger.info(f"[Notification] 메신저 발송 결과: {results}")
    except Exception as e:
        if guard_claimed and guard_key and not guard_marked:
            try:
                from services.jongga_notification_guard_service import release_jongga_notification_claim

                release_jongga_notification_claim(data_dir, guard_key)
            except Exception:
                pass
        logger.error(f"[Notification] 메신저 발송 중 오류: {e}")


def run_jongga_v2_background_pipeline(
    capital: int,
    markets: list[str] | None,
    target_date: str | None,
    logger: logging.Logger,
) -> None:
    """종가베팅 v2 엔진 백그라운드 실행 파이프라인."""
    # [INFRA-118] 실행권은 launch_jongga_v2_screener 가 잡고 내린다. 여기서 한 번 더 내리면 그 사이 체인이 잡은 실행권을 덮는다
    selected_markets = markets or ["KOSPI", "KOSDAQ"]

    logger.info("[Background] Jongga V2 Engine Started...")
    if target_date:
        logger.info(f"[테스트 모드] 지정 날짜 기준 분석: {target_date}")

    _reload_engine_submodules()

    from engine.generator import run_screener

    result = _run_coro_in_fresh_loop(
        run_screener(
            capital=capital,
            markets=selected_markets,
            target_date=target_date,
        ),
        logger=logger,
    )

    if result:
        _send_jongga_notification_from_result(result, logger)

    logger.info("[Background] Jongga V2 Engine Completed Successfully.")


def read_v2_status_uncached(v2_status_file: str) -> dict[str, Any]:
    """[INFRA-115] 잠금 안의 판정용 읽기. (mtime, size) 캐시는 같은 틱·같은 크기의 다른 워커 저장을 놓친다."""
    try:
        with open(v2_status_file, "r", encoding="utf-8") as fp:
            loaded = json.load(fp)
    except (OSError, ValueError):
        return {"isRunning": False}
    return loaded if isinstance(loaded, dict) else {"isRunning": False}


def write_v2_status(v2_status_file: str, running: bool, logger: logging.Logger) -> bool:
    """[INFRA-116] 수동 실행과 스케줄러 체인이 같은 형식으로 V2 실행권을 기록한다. 저장 성공 여부를 돌려준다."""
    try:
        atomic_write_text(
            v2_status_file,
            json.dumps(
                {
                    "isRunning": running,
                    "updated_at": datetime.now().isoformat(),
                    # [INFRA-114] 기동 초기화가 소유 워커 생존을 판정하도록 남긴다
                    "ownerPid": os.getpid(),
                    "ownerPpid": os.getppid(),
                },
                ensure_ascii=False,
                indent=2,
            ),
        )
        return True
    except Exception as error:
        logger.error(f"Failed to save V2 status: {error}")
        return False


def launch_jongga_v2_screener(
    req_data: dict[str, Any],
    load_v2_status: Callable[[], dict[str, Any]],
    save_v2_status: Callable[[bool], bool | None],
    run_jongga_background: Callable[..., None],
    logger: logging.Logger,
    status_lock: Callable[[], AbstractContextManager[Any]] = nullcontext,
) -> tuple[int, dict[str, Any]]:
    """종가베팅 v2 백그라운드 스크리너 실행을 시작한다."""
    # [INFRA-115] 확인과 저장 사이에 다른 워커의 요청이 끼면 둘 다 통과해 분석이 두 번 돈다
    with status_lock():
        if load_v2_status().get("isRunning", False):
            return 409, {
                "status": "error",
                "message": "Engine is already running. Please wait.",
            }
        # [INFRA-114] 백그라운드가 곧바로 끝나 False 를 쓴 뒤에 True 가 덮여 409 로 굳지 않게 먼저 저장한다
        # [INFRA-119] 저장하지 못하면 실행권 없이 돌다가 끝날 때 남의 실행권을 덮으므로 시작하지 않는다
        if save_v2_status(True) is False:
            logger.error("[Background] Jongga V2 run refused: failed to save run claim")
            # 교체 뒤 캐시 무효화에서 실패했다면 True 가 이미 디스크에 있다. 잠금 안이라 남의 실행권을 덮지 않는다
            save_v2_status(False)
            return 500, {
                "status": "error",
                "message": "Failed to save engine status. Please retry.",
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
            logger.info("[Background] Jongga V2 Status reset to False")

    thread = threading.Thread(target=_run_wrapper, daemon=True)
    try:
        thread.start()
    except Exception:
        # 살아 있는 이 워커 pid 로 True 가 남으면 형제 재기동으로도 풀리지 않는다
        save_v2_status(False)
        raise

    message = "Engine started in background. Poll /jongga-v2/status for completion."
    if target_date:
        message = f"[테스트 모드] {target_date} 기준 분석 시작. Poll /jongga-v2/status for completion."

    return 200, {
        "status": "started",
        "message": message,
        "target_date": target_date,
    }
