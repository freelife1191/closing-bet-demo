#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KR Market 라우트 등록 레지스트리

kr_market 모듈의 의존성 조립/라우트 등록 블록을 분리한다.
"""

from __future__ import annotations

from typing import Any, Callable

from app.routes.kr_market_data_http_routes import register_market_data_routes
from app.routes.kr_market_dependency_builders import (
    build_market_data_route_deps,
    build_system_route_deps,
)
from app.routes.kr_market_helpers import (
    _aggregate_cumulative_kpis,
    _apply_gemini_reanalysis_results,
    _apply_latest_prices_to_jongga_signals,
    _build_ai_data_map,
    _build_ai_signals_from_jongga_results,
    _build_cumulative_trade_record,
    _build_jongga_news_analysis_items,
    _build_ticker_price_index,
    _build_vcp_signals_from_dataframe,
    _calculate_jongga_backtest_stats,
    _calculate_vcp_backtest_stats,
    _extract_stats_date_from_results_filename,
    _filter_signals_dataframe_by_date,
    _format_signal_date,
    _merge_ai_data_into_vcp_signals,
    _merge_legacy_ai_fields_into_map,
    _normalize_ai_payload_tickers,
    _normalize_jongga_signals_for_frontend,
    _paginate_items,
    _prepare_cumulative_price_dataframe,
    _recalculate_jongga_grades,
    _select_signals_for_gemini_reanalysis,
    _should_use_jongga_ai_payload,
    _sort_and_limit_vcp_signals,
    _sort_jongga_signals,
)
from app.routes.kr_market_jongga_execution_routes import register_jongga_execution_routes
from app.routes.kr_market_system_http_routes import register_system_routes
from services.kr_market_flow_service import (
    build_market_status_payload,
    collect_jongga_v2_dates,
    execute_market_gate_update,
    launch_background_update_job,
    launch_init_data_update,
    start_vcp_screener_run,
)
from services.kr_market_route_service import (
    apply_market_gate_snapshot_fallback,
    build_ai_analysis_payload_for_target_date,
    build_backtest_summary_payload,
    build_data_status_payload,
    build_jongga_history_payload,
    build_jongga_latest_payload,
    build_latest_ai_analysis_payload,
    build_market_gate_empty_payload,
    build_market_gate_initializing_payload,
    build_screener_result_for_message,
    build_stock_chart_payload,
    build_vcp_signals_payload,
    execute_jongga_gemini_reanalysis,
    execute_single_stock_analysis,
    execute_user_gemini_reanalysis_request,
    execute_vcp_failed_ai_reanalysis,
    evaluate_market_gate_validity,
    fetch_realtime_prices,
    fetch_stock_detail_payload,
    launch_jongga_v2_screener,
    normalize_market_gate_payload,
    resolve_chart_period_days,
    resolve_jongga_message_filename,
    resolve_market_gate_filename,
    run_jongga_v2_background_pipeline,
    run_vcp_background_pipeline,
    validate_vcp_reanalysis_source_frame,
)


def register_market_data_http_route_group(
    kr_bp: Any,
    *,
    logger: Any,
    data_dir_getter: Callable[[], str],
    load_csv_file_fn: Callable[[str], Any],
    load_json_file_fn: Callable[[str], dict[str, Any]],
    get_data_path_fn: Callable[[str], str],
    vcp_status: dict[str, Any],
    update_vcp_ai_cache_files_fn: Callable[[str, dict[str, Any], dict[str, Any] | None], int],
    load_latest_vcp_price_map_fn: Callable[[], dict[str, float]],
    count_total_scanned_stocks_fn: Callable[[str], int],
    load_jongga_result_payloads_fn: Callable[..., list[Any]],
    load_backtest_price_snapshot_fn: Callable[[], tuple[Any, dict[str, Any]]],
) -> None:
    """시장 데이터 조회 라우트 그룹을 등록한다."""

    register_market_data_routes(
        kr_bp,
        logger=logger,
        deps=build_market_data_route_deps(
            data_dir_getter=data_dir_getter,
            load_csv_file=load_csv_file_fn,
            load_json_file=load_json_file_fn,
            get_data_path=get_data_path_fn,
            vcp_status=vcp_status,
            run_vcp_background_pipeline=run_vcp_background_pipeline,
            start_vcp_screener_run=start_vcp_screener_run,
            validate_vcp_reanalysis_source_frame=validate_vcp_reanalysis_source_frame,
            execute_vcp_failed_ai_reanalysis=execute_vcp_failed_ai_reanalysis,
            update_vcp_ai_cache_files=update_vcp_ai_cache_files_fn,
            build_market_status_payload=build_market_status_payload,
            build_vcp_signals_payload=build_vcp_signals_payload,
            filter_signals_dataframe_by_date=_filter_signals_dataframe_by_date,
            build_vcp_signals_from_dataframe=_build_vcp_signals_from_dataframe,
            load_latest_vcp_price_map=load_latest_vcp_price_map_fn,
            apply_latest_prices_to_jongga_signals=_apply_latest_prices_to_jongga_signals,
            sort_and_limit_vcp_signals=_sort_and_limit_vcp_signals,
            build_ai_data_map=_build_ai_data_map,
            merge_legacy_ai_fields_into_map=_merge_legacy_ai_fields_into_map,
            merge_ai_data_into_vcp_signals=_merge_ai_data_into_vcp_signals,
            count_total_scanned_stocks=count_total_scanned_stocks_fn,
            build_stock_chart_payload=build_stock_chart_payload,
            resolve_chart_period_days=resolve_chart_period_days,
            build_ai_analysis_payload_for_target_date=build_ai_analysis_payload_for_target_date,
            build_latest_ai_analysis_payload=build_latest_ai_analysis_payload,
            build_ai_signals_from_jongga_results=_build_ai_signals_from_jongga_results,
            normalize_ai_payload_tickers=_normalize_ai_payload_tickers,
            format_signal_date=_format_signal_date,
            should_use_jongga_ai_payload=_should_use_jongga_ai_payload,
            load_jongga_result_payloads=load_jongga_result_payloads_fn,
            prepare_cumulative_price_dataframe=_prepare_cumulative_price_dataframe,
            build_ticker_price_index=_build_ticker_price_index,
            extract_stats_date_from_results_filename=_extract_stats_date_from_results_filename,
            build_cumulative_trade_record=_build_cumulative_trade_record,
            aggregate_cumulative_kpis=_aggregate_cumulative_kpis,
            paginate_items=_paginate_items,
            fetch_realtime_prices=fetch_realtime_prices,
            build_jongga_latest_payload=build_jongga_latest_payload,
            collect_jongga_v2_dates=collect_jongga_v2_dates,
            build_jongga_history_payload=build_jongga_history_payload,
            recalculate_jongga_grades=_recalculate_jongga_grades,
            sort_jongga_signals=_sort_jongga_signals,
            normalize_jongga_signals_for_frontend=_normalize_jongga_signals_for_frontend,
            build_backtest_summary_payload=build_backtest_summary_payload,
            load_backtest_price_snapshot=load_backtest_price_snapshot_fn,
            calculate_jongga_backtest_stats=_calculate_jongga_backtest_stats,
            calculate_vcp_backtest_stats=_calculate_vcp_backtest_stats,
            fetch_stock_detail_payload=fetch_stock_detail_payload,
        ),
    )


def register_system_and_execution_route_groups(
    kr_bp: Any,
    *,
    logger: Any,
    data_dir: str,
    load_json_file_fn: Callable[[str], dict[str, Any]],
    load_csv_file_fn: Callable[[str], Any],
    get_data_path_fn: Callable[[str], str],
    trigger_market_gate_background_refresh_fn: Callable[[], bool],
    run_user_gemini_reanalysis_fn: Callable[..., dict[str, Any]],
    project_root_getter: Callable[[], str],
) -> None:
    """시스템/실행 라우트 그룹을 등록한다."""

    register_system_routes(
        kr_bp,
        logger=logger,
        deps=build_system_route_deps(
            resolve_market_gate_filename=resolve_market_gate_filename,
            load_json_file=load_json_file_fn,
            evaluate_market_gate_validity=evaluate_market_gate_validity,
            apply_market_gate_snapshot_fallback=apply_market_gate_snapshot_fallback,
            trigger_market_gate_background_refresh=trigger_market_gate_background_refresh_fn,
            build_market_gate_initializing_payload=build_market_gate_initializing_payload,
            build_market_gate_empty_payload=build_market_gate_empty_payload,
            normalize_market_gate_payload=normalize_market_gate_payload,
            execute_market_gate_update=execute_market_gate_update,
            execute_user_gemini_reanalysis_request=execute_user_gemini_reanalysis_request,
            run_user_gemini_reanalysis=run_user_gemini_reanalysis_fn,
            project_root_getter=project_root_getter,
            launch_background_update_job=launch_background_update_job,
            launch_init_data_update=launch_init_data_update,
            build_data_status_payload=build_data_status_payload,
            get_data_path=get_data_path_fn,
            load_csv_file=load_csv_file_fn,
        ),
    )

    register_jongga_execution_routes(
        kr_bp,
        data_dir=data_dir,
        logger=logger,
        load_json_file=load_json_file_fn,
        launch_jongga_v2_screener=launch_jongga_v2_screener,
        run_jongga_v2_background_pipeline=run_jongga_v2_background_pipeline,
        execute_single_stock_analysis=execute_single_stock_analysis,
        execute_jongga_gemini_reanalysis=execute_jongga_gemini_reanalysis,
        resolve_jongga_message_filename=resolve_jongga_message_filename,
        build_screener_result_for_message=build_screener_result_for_message,
        select_signals_for_reanalysis=_select_signals_for_gemini_reanalysis,
        build_jongga_news_analysis_items=_build_jongga_news_analysis_items,
        apply_gemini_reanalysis_results=_apply_gemini_reanalysis_results,
    )


__all__ = [
    "register_market_data_http_route_group",
    "register_system_and_execution_route_groups",
]
