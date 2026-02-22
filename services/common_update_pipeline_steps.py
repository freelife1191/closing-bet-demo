#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Common Update Pipeline Step Services
"""

from __future__ import annotations

import asyncio
from typing import Any, Callable, TypeVar

import pandas as pd

T = TypeVar("T")


def is_stop_requested(shared_state: Any) -> bool:
    return bool(getattr(shared_state, "STOP_REQUESTED", False))


def raise_if_stopped(shared_state: Any) -> None:
    if is_stop_requested(shared_state):
        raise RuntimeError("Stopped by user")


def _run_update_step(
    *,
    step_name: str,
    execute_fn: Callable[[], T],
    update_item_status: Callable[[str, str], None],
    shared_state: Any,
    logger: Any,
) -> T | None:
    """업데이트 step 실행/상태 전환/예외 처리를 공통화한다."""
    raise_if_stopped(shared_state)
    update_item_status(step_name, "running")
    try:
        result = execute_fn()
        update_item_status(step_name, "done")
        return result
    except Exception as error:
        logger.error(f"{step_name} Failed: {error}", exc_info=True)
        update_item_status(step_name, "error")
        if is_stop_requested(shared_state):
            raise
        return None


def run_daily_prices_step(
    *,
    init_data: Any,
    target_date: str | None,
    force: bool,
    update_item_status: Callable[[str, str], None],
    shared_state: Any,
    logger: Any,
) -> None:
    _run_update_step(
        step_name="Daily Prices",
        execute_fn=lambda: init_data.create_daily_prices(target_date, force=force),
        update_item_status=update_item_status,
        shared_state=shared_state,
        logger=logger,
    )


def run_institutional_trend_step(
    *,
    init_data: Any,
    target_date: str | None,
    force: bool,
    update_item_status: Callable[[str, str], None],
    shared_state: Any,
    logger: Any,
) -> None:
    _run_update_step(
        step_name="Institutional Trend",
        execute_fn=lambda: init_data.create_institutional_trend(target_date, force=force),
        update_item_status=update_item_status,
        shared_state=shared_state,
        logger=logger,
    )


def run_market_gate_step(
    *,
    target_date: str | None,
    update_item_status: Callable[[str, str], None],
    shared_state: Any,
    logger: Any,
) -> None:
    def _execute() -> None:
        from engine.market_gate import MarketGate

        market_gate = MarketGate()
        result = market_gate.analyze(target_date)
        market_gate.save_analysis(result, target_date)

    _run_update_step(
        step_name="Market Gate",
        execute_fn=_execute,
        update_item_status=update_item_status,
        shared_state=shared_state,
        logger=logger,
    )


def run_vcp_signals_step(
    *,
    init_data: Any,
    target_date: str | None,
    update_item_status: Callable[[str, str], None],
    shared_state: Any,
    logger: Any,
) -> pd.DataFrame | None:
    def _execute() -> pd.DataFrame | None:
        vcp_df = init_data.create_signals_log(target_date)

        try:
            from engine.signal_tracker import SignalTracker

            tracker = SignalTracker()
            tracker.update_open_signals()
            logger.info("SignalTracker: Open signals updated")
        except Exception as tracker_error:
            logger.warning(f"SignalTracker update failed (non-critical): {tracker_error}")

        return vcp_df

    return _run_update_step(
        step_name="VCP Signals",
        execute_fn=_execute,
        update_item_status=update_item_status,
        shared_state=shared_state,
        logger=logger,
    )


def run_ai_jongga_v2_step(
    *,
    target_date: str | None,
    update_item_status: Callable[[str, str], None],
    shared_state: Any,
    logger: Any,
) -> None:
    def _execute() -> None:
        from engine.generator import run_screener

        async def run_async_screener() -> None:
            await run_screener(capital=50_000_000, target_date=target_date)

        asyncio.run(run_async_screener())
        update_item_status("AI Analysis", "done")

    _run_update_step(
        step_name="AI Jongga V2",
        execute_fn=_execute,
        update_item_status=update_item_status,
        shared_state=shared_state,
        logger=logger,
    )


__all__ = [
    "is_stop_requested",
    "raise_if_stopped",
    "run_ai_jongga_v2_step",
    "run_daily_prices_step",
    "run_institutional_trend_step",
    "run_market_gate_step",
    "run_vcp_signals_step",
]
