#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Common Update Service

공통 라우트의 백그라운드 업데이트 파이프라인 오케스트레이션.
"""

from __future__ import annotations

import threading
from typing import Any, Callable

import pandas as pd

from services.common_update_ai_analysis_service import run_ai_analysis_step
from services.common_update_pipeline_steps import (
    is_stop_requested,
    run_ai_jongga_v2_step,
    run_daily_prices_step,
    run_institutional_trend_step,
    run_market_gate_step,
    run_vcp_signals_step,
)


DEFAULT_UPDATE_ITEMS = [
    "Daily Prices",
    "Institutional Trend",
    "Market Gate",
    "VCP Signals",
    "AI Analysis",
    "AI Jongga V2",
]

STOP_WATCH_INTERVAL_SECONDS = 1.0


def _read_start_time(load_update_status: Callable[[], dict] | None, logger: Any) -> Any:
    """현재 실행의 startTime. 읽지 못하면 None 이며, 호출자는 종전 동작(감시 없음, 항상 finish)으로 돌아간다."""
    if load_update_status is None:
        return None
    try:
        return load_update_status().get("startTime")
    except Exception as error:
        logger.warning(f"Update status read failed: {error}")
        return None


def _watch_stop_request(
    load_update_status: Callable[[], dict],
    start_time: Any,
    shared_state: Any,
    done: threading.Event,
    logger: Any,
) -> None:
    """[INFRA-097] 다른 워커가 공유 상태에 남긴 이 실행의 중단 요청을 이 워커의 플래그로 옮긴다."""
    while not done.wait(STOP_WATCH_INTERVAL_SECONDS):
        try:
            status = load_update_status()
        except Exception as error:
            logger.warning(f"Stop request watch failed: {error}")
            continue
        current = status.get("startTime")
        if current == start_time:
            stopped = bool(status.get("stopRequested"))
        else:
            # 새 실행이 시작됐다면 이 실행은 중단된 것이다. 감시가 읽기 전에 중단과 재시작이 끝난 경우다.
            # ponytail: 새 실행이 같은 워커면 플래그를 함께 쓰므로 건너뛰고, 옛 실행은 새 실행과 함께 돈다.
            # [INFRA-099] 뒤로 같은 워커의 새 시작은 거부되므로 시작 처리와 스레드 진입 사이 틈에서만 닿는다
            stopped = current is not None and current != getattr(shared_state, "LOCAL_RUN_START_TIME", None)
        # 매번 다시 켜므로 같은 워커의 옛 실행 finally 가 지운 값도 다음 주기에 되살아난다
        if stopped:
            shared_state.STOP_REQUESTED = True


def run_background_update_pipeline(
    *,
    target_date: str | None,
    selected_items: list[str] | None,
    force: bool,
    update_item_status: Callable[[str, str], None],
    finish_update: Callable[[], None],
    shared_state: Any,
    logger: Any,
    load_update_status: Callable[[], dict] | None = None,
) -> None:
    """백그라운드에서 순차적으로 데이터 업데이트 실행."""
    items = selected_items or list(DEFAULT_UPDATE_ITEMS)
    vcp_df: pd.DataFrame | None = None
    institutional_trend_ok = True
    vcp_step_blocked = False
    watch_done = threading.Event()
    watcher: threading.Thread | None = None
    start_time = None
    if load_update_status is not None:
        # start_update 가 이 워커에서 방금 정한 값이 우선이다. 두 워커가 함께 시작하면 파일에는 늦게 쓴 쪽만 남는다
        start_time = getattr(shared_state, "LOCAL_RUN_START_TIME", None) or _read_start_time(load_update_status, logger)
    if start_time is not None:
        watcher = threading.Thread(
            target=_watch_stop_request,
            args=(load_update_status, start_time, shared_state, watch_done, logger),
            daemon=True,
        )
        watcher.start()

    try:
        shared_state.LOCAL_PIPELINE_ACTIVE = True
        from scripts import init_data

        if "Daily Prices" in items:
            run_daily_prices_step(
                init_data=init_data,
                target_date=target_date,
                force=force,
                update_item_status=update_item_status,
                shared_state=shared_state,
                logger=logger,
            )

        if "Institutional Trend" in items:
            institutional_trend_ok = run_institutional_trend_step(
                init_data=init_data,
                target_date=target_date,
                force=force,
                update_item_status=update_item_status,
                shared_state=shared_state,
                logger=logger,
            )

        if "Market Gate" in items:
            run_market_gate_step(
                target_date=target_date,
                update_item_status=update_item_status,
                shared_state=shared_state,
                logger=logger,
            )

        if "VCP Signals" in items:
            if not institutional_trend_ok:
                vcp_step_blocked = True
                logger.error(
                    "VCP Signals skipped: Institutional Trend step failed; stale supply data cannot be used."
                )
                update_item_status("VCP Signals", "error")
            else:
                vcp_df = run_vcp_signals_step(
                    init_data=init_data,
                    target_date=target_date,
                    update_item_status=update_item_status,
                    shared_state=shared_state,
                    logger=logger,
                )

        if "AI Analysis" in items:
            if vcp_step_blocked:
                logger.error(
                    "AI Analysis skipped: VCP Signals step was blocked by Institutional Trend failure."
                )
                update_item_status("AI Analysis", "error")
            else:
                run_ai_analysis_step(
                    target_date=target_date,
                    selected_items=items,
                    vcp_df=vcp_df,
                    update_item_status=update_item_status,
                    shared_state=shared_state,
                    logger=logger,
                )

        if "AI Jongga V2" in items:
            run_ai_jongga_v2_step(
                target_date=target_date,
                update_item_status=update_item_status,
                shared_state=shared_state,
                logger=logger,
            )
    except Exception as e:
        if str(e) == "Stopped by user" or is_stop_requested(shared_state):
            logger.info(f"Background Update Stopped: {e}")
        else:
            logger.error(f"Background Update Failed: {e}")
    finally:
        try:
            watch_done.set()
            if watcher is not None:
                watcher.join()  # 읽는 중이던 감시가 아래 해제 뒤에 값을 다시 켜지 않게 한다
            # [INFRA-096] 중단의 대상이던 작업이 끝났으므로 중단 요청도 끝낸다. 남겨 두면 스케줄러와 개별 실행이 멈춘다
            # [INFRA-099] 이 실행이 도는 동안 같은 워커의 새 시작은 거부되므로 끌 대상은 이 실행의 요청뿐이다
            shared_state.STOP_REQUESTED = False
            # [INFRA-098] 대체된 실행인지는 finish_update 가 상태 파일 잠금 안에서 startTime 으로 가린다
            finish_update()
        finally:
            # [INFRA-099] 상태를 다 정리한 뒤에 끈다. 켜진 채 남으면 이 워커는 재기동 전까지 시작을 거부한다
            shared_state.LOCAL_PIPELINE_ACTIVE = False


__all__ = ["DEFAULT_UPDATE_ITEMS", "run_background_update_pipeline"]
