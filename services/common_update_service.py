#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Common Update Service

공통 라우트의 백그라운드 업데이트 파이프라인 오케스트레이션.
"""

from __future__ import annotations

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


def run_background_update_pipeline(
    *,
    target_date: str | None,
    selected_items: list[str] | None,
    force: bool,
    update_item_status: Callable[[str, str], None],
    finish_update: Callable[[], None],
    shared_state: Any,
    logger: Any,
) -> None:
    """백그라운드에서 순차적으로 데이터 업데이트 실행."""
    items = selected_items or list(DEFAULT_UPDATE_ITEMS)
    vcp_df: pd.DataFrame | None = None

    try:
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
            run_institutional_trend_step(
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
            vcp_df = run_vcp_signals_step(
                init_data=init_data,
                target_date=target_date,
                update_item_status=update_item_status,
                shared_state=shared_state,
                logger=logger,
            )

        if "AI Analysis" in items:
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
        finish_update()


__all__ = ["DEFAULT_UPDATE_ITEMS", "run_background_update_pipeline"]

