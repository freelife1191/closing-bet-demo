#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KR Market dependency builder 회귀 테스트
"""

import os
import sys


sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from app.routes.kr_market_dependency_builders import (
    build_market_data_route_deps,
    build_system_route_deps,
)


def _noop(*_args, **_kwargs):
    return None


def test_build_market_data_route_deps_preserves_required_contract_keys():
    deps = build_market_data_route_deps(
        data_dir_getter=lambda: "data",
        load_csv_file=lambda _f: [],
        load_json_file=lambda _f: {},
        get_data_path=lambda f: f"data/{f}",
        vcp_status={"running": False},
        run_vcp_background_pipeline=_noop,
        start_vcp_screener_run=lambda **_k: (200, {}),
        validate_vcp_reanalysis_source_frame=lambda _df: (0, None),
        execute_vcp_failed_ai_reanalysis=lambda **_k: (200, {}),
        update_vcp_ai_cache_files=lambda _d, _r: 0,
        build_market_status_payload=lambda **_k: {},
        build_vcp_signals_payload=lambda **_k: {},
        filter_signals_dataframe_by_date=lambda *_a, **_k: ([], ""),
        build_vcp_signals_from_dataframe=lambda *_a, **_k: [],
        load_latest_vcp_price_map=lambda: {},
        apply_latest_prices_to_jongga_signals=lambda *_a, **_k: 0,
        sort_and_limit_vcp_signals=lambda *_a, **_k: None,
        build_ai_data_map=lambda *_a, **_k: {},
        merge_legacy_ai_fields_into_map=lambda *_a, **_k: None,
        merge_ai_data_into_vcp_signals=lambda *_a, **_k: None,
        count_total_scanned_stocks=lambda _d: 0,
        build_stock_chart_payload=lambda **_k: {},
        resolve_chart_period_days=lambda _p: 90,
        build_ai_analysis_payload_for_target_date=lambda **_k: None,
        build_latest_ai_analysis_payload=lambda **_k: {},
        build_ai_signals_from_jongga_results=lambda *_a, **_k: [],
        normalize_ai_payload_tickers=lambda d: d,
        format_signal_date=lambda v: str(v),
        should_use_jongga_ai_payload=lambda *_a: True,
        load_jongga_result_payloads=lambda **_k: [],
        prepare_cumulative_price_dataframe=lambda _df: _df,
        build_ticker_price_index=lambda _df: {},
        extract_stats_date_from_results_filename=lambda *_a, **_k: "",
        build_cumulative_trade_record=lambda *_a, **_k: None,
        aggregate_cumulative_kpis=lambda *_a, **_k: {},
        paginate_items=lambda *_a, **_k: ([], {}),
        fetch_realtime_prices=lambda **_k: {},
        build_jongga_latest_payload=lambda **_k: {},
        collect_jongga_v2_dates=lambda **_k: [],
        build_jongga_history_payload=lambda **_k: (200, {}),
        recalculate_jongga_grades=lambda _d: False,
        sort_jongga_signals=lambda _s: None,
        normalize_jongga_signals_for_frontend=lambda _s: None,
        build_backtest_summary_payload=lambda **_k: {},
        load_backtest_price_snapshot=lambda: ([], {}),
        calculate_jongga_backtest_stats=lambda **_k: {},
        calculate_vcp_backtest_stats=lambda **_k: {},
        fetch_stock_detail_payload=lambda **_k: {},
    )

    assert "build_vcp_signals_payload" in deps
    assert "build_jongga_latest_payload" in deps
    assert "fetch_stock_detail_payload" in deps


def test_build_system_route_deps_preserves_required_contract_keys():
    deps = build_system_route_deps(
        resolve_market_gate_filename=lambda _d: "market_gate.json",
        load_json_file=lambda _f: {},
        evaluate_market_gate_validity=lambda *_a, **_k: (True, "ok", {}),
        apply_market_gate_snapshot_fallback=lambda *_a, **_k: {},
        trigger_market_gate_background_refresh=lambda: None,
        build_market_gate_initializing_payload=lambda **_k: {},
        build_market_gate_empty_payload=lambda **_k: {},
        normalize_market_gate_payload=lambda **_k: {},
        execute_market_gate_update=lambda **_k: (200, {}),
        execute_user_gemini_reanalysis_request=lambda **_k: (200, {}),
        run_user_gemini_reanalysis=lambda **_k: {},
        project_root_getter=lambda: ".",
        launch_background_update_job=lambda **_k: (True, ""),
        launch_init_data_update=lambda **_k: (True, ""),
        build_data_status_payload=lambda **_k: {},
        get_data_path=lambda _f: "data/x",
        load_csv_file=lambda _f: [],
    )

    assert "resolve_market_gate_filename" in deps
    assert "execute_market_gate_update" in deps
    assert "build_data_status_payload" in deps
