#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KR Market Route Service

라우트에서 공통으로 사용하는 서비스 함수들을 조합/재노출한다.
"""

from __future__ import annotations

import logging
import sys
from typing import Any, Callable

from services.kr_market_analytics_service import (
    build_backtest_summary_payload,
    build_data_status_payload,
    build_stock_chart_payload,
    resolve_chart_period_days,
)
from services.kr_market_jongga_service import (
    _send_jongga_notification_from_result,
    _run_coro_in_fresh_loop,
    build_jongga_history_payload,
    build_jongga_latest_payload,
    build_screener_result_for_message,
    execute_jongga_gemini_reanalysis,
    launch_jongga_v2_screener,
    load_jongga_signals_for_reanalysis,
    load_market_status_for_reanalysis,
    parse_jongga_reanalyze_request_options,
    persist_reanalyze_payload,
    resolve_jongga_message_filename,
    run_jongga_news_reanalysis_batch,
)
from services.kr_market_market_gate_service import (
    apply_market_gate_snapshot_fallback,
    build_ai_analysis_payload_for_target_date,
    build_latest_ai_analysis_payload,
    build_market_gate_empty_payload,
    evaluate_market_gate_validity,
    normalize_market_gate_payload,
    resolve_market_gate_filename,
)
from services.kr_market_realtime_service import (
    fetch_realtime_prices,
    fetch_stock_detail_payload,
)
from services.kr_market_vcp_service import (
    build_vcp_reanalysis_no_targets_payload,
    build_vcp_reanalysis_success_payload,
    build_vcp_signals_payload,
    collect_failed_vcp_rows,
    execute_vcp_failed_ai_reanalysis,
    prepare_vcp_signals_scope,
    run_async_analyzer_batch,
    run_vcp_background_pipeline,
    validate_vcp_reanalysis_source_frame,
)
from services.kr_market_vcp_cache_update_service import (
    update_vcp_ai_cache_files as update_vcp_ai_cache_files_service,
)
from services.kr_market_single_stock_service import (
    execute_single_stock_analysis as execute_single_stock_analysis_service,
)


def _reload_engine_submodules() -> None:
    for module_name in [name for name in list(sys.modules.keys()) if name.startswith("engine.")]:
        del sys.modules[module_name]


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


def update_vcp_ai_cache_files(
    target_date: str | None,
    updated_recommendations: dict[str, Any],
    get_data_path: Callable[[str], str],
    load_json_file: Callable[[str], dict[str, Any]],
    logger: logging.Logger,
    ai_results: dict[str, Any] | None = None,
) -> int:
    return update_vcp_ai_cache_files_service(
        target_date=target_date,
        updated_recommendations=updated_recommendations,
        ai_results=ai_results,
        get_data_path=get_data_path,
        load_json_file=load_json_file,
        logger=logger,
    )


def execute_single_stock_analysis(code: str | None, logger: logging.Logger) -> tuple[int, dict[str, Any]]:
    return execute_single_stock_analysis_service(
        code=code,
        logger=logger,
        run_coro_in_fresh_loop_fn=_run_coro_in_fresh_loop,
    )
