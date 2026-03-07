#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Common Update Pipeline Step Services
"""

from __future__ import annotations

import asyncio
import os
from datetime import datetime
from typing import Any, Callable, TypeVar

import pandas as pd

T = TypeVar("T")
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def is_stop_requested(shared_state: Any) -> bool:
    return bool(getattr(shared_state, "STOP_REQUESTED", False))


def raise_if_stopped(shared_state: Any) -> None:
    if is_stop_requested(shared_state):
        raise RuntimeError("Stopped by user")


def _resolve_data_file_path(filename: str) -> str:
    return os.path.join(_BASE_DIR, "data", filename)


def _resolve_reference_datetime(target_date: str | None) -> datetime:
    if not target_date:
        return datetime.now()

    try:
        return datetime.strptime(str(target_date), "%Y-%m-%d")
    except (TypeError, ValueError):
        return datetime.now()


def _resolve_expected_trading_date_str(init_data: Any, target_date: str | None) -> str | None:
    get_last_trading_date = getattr(init_data, "get_last_trading_date", None)
    if not callable(get_last_trading_date):
        return None

    try:
        last_trading_date_str, _ = get_last_trading_date(
            reference_date=_resolve_reference_datetime(target_date),
        )
    except Exception:
        return None

    normalized = str(last_trading_date_str).strip().replace("-", "")
    if len(normalized) == 8 and normalized.isdigit():
        return f"{normalized[0:4]}-{normalized[4:6]}-{normalized[6:8]}"
    return None


def _validate_latest_date_not_stale(
    *,
    file_path: str,
    expected_date_str: str | None,
    step_name: str,
    logger: Any,
) -> bool:
    if not expected_date_str:
        return True
    if not os.path.exists(file_path):
        logger.error(f"{step_name} Failed: output file missing ({file_path})")
        return False

    try:
        latest_df = pd.read_csv(file_path, usecols=["date"], dtype={"date": str})
    except Exception as error:
        logger.error(f"{step_name} Failed: failed to read {file_path}: {error}")
        return False

    if latest_df.empty or "date" not in latest_df.columns:
        logger.error(f"{step_name} Failed: date column missing or empty in {file_path}")
        return False

    date_series = latest_df["date"].astype(str).str.slice(0, 10)
    latest_date = date_series.max()
    if not latest_date or latest_date < expected_date_str:
        logger.error(
            f"{step_name} Failed: stale data detected ({latest_date} < {expected_date_str})"
        )
        return False

    return True


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
        if result is False:
            logger.error(f"{step_name} Failed: step returned False")
            update_item_status(step_name, "error")
            return None
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
) -> bool:
    expected_date_str = _resolve_expected_trading_date_str(init_data, target_date)
    daily_prices_path = _resolve_data_file_path("daily_prices.csv")

    def _execute() -> bool:
        result = init_data.create_daily_prices(target_date, force=force)
        if result is False:
            return False
        return _validate_latest_date_not_stale(
            file_path=daily_prices_path,
            expected_date_str=expected_date_str,
            step_name="Daily Prices",
            logger=logger,
        )

    result = _run_update_step(
        step_name="Daily Prices",
        execute_fn=_execute,
        update_item_status=update_item_status,
        shared_state=shared_state,
        logger=logger,
    )
    return bool(result)


def run_institutional_trend_step(
    *,
    init_data: Any,
    target_date: str | None,
    force: bool,
    update_item_status: Callable[[str, str], None],
    shared_state: Any,
    logger: Any,
) -> bool:
    expected_date_str = _resolve_expected_trading_date_str(init_data, target_date)
    trend_file_path = _resolve_data_file_path("all_institutional_trend_data.csv")

    def _execute() -> bool:
        result = init_data.create_institutional_trend(target_date, force=force)
        if result is False:
            return False
        return _validate_latest_date_not_stale(
            file_path=trend_file_path,
            expected_date_str=expected_date_str,
            step_name="Institutional Trend",
            logger=logger,
        )

    result = _run_update_step(
        step_name="Institutional Trend",
        execute_fn=_execute,
        update_item_status=update_item_status,
        shared_state=shared_state,
        logger=logger,
    )
    return bool(result)


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
