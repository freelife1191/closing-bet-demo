#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KR Market route registry 분해 회귀 테스트
"""

import os
import sys


sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

import app.routes.kr_market_route_registry as registry_module


def test_register_market_data_http_route_group_builds_deps_and_registers(monkeypatch):
    built_kwargs = {}
    register_calls = []

    def _fake_build_market_data_route_deps(**kwargs):
        built_kwargs["kwargs"] = kwargs
        return {"deps": "ok"}

    monkeypatch.setattr(
        registry_module,
        "build_market_data_route_deps",
        _fake_build_market_data_route_deps,
    )
    monkeypatch.setattr(
        registry_module,
        "register_market_data_routes",
        lambda kr_bp, *, logger, deps: register_calls.append((kr_bp, logger, deps)),
    )

    sentinel_bp = object()
    sentinel_logger = object()

    registry_module.register_market_data_http_route_group(
        sentinel_bp,
        logger=sentinel_logger,
        data_dir_getter=lambda: "data",
        load_csv_file_fn=lambda _filename: [],
        load_json_file_fn=lambda _filename: {},
        get_data_path_fn=lambda filename: f"data/{filename}",
        vcp_status={"running": False},
        update_vcp_ai_cache_files_fn=lambda _target_date, _payload: 0,
        load_latest_vcp_price_map_fn=lambda: {},
        count_total_scanned_stocks_fn=lambda _data_dir: 0,
        load_jongga_result_payloads_fn=lambda **_kwargs: [],
        load_backtest_price_snapshot_fn=lambda: ([], {}),
    )

    assert register_calls
    assert register_calls[0][0] is sentinel_bp
    assert register_calls[0][1] is sentinel_logger
    assert register_calls[0][2] == {"deps": "ok"}
    assert built_kwargs["kwargs"]["vcp_status"] == {"running": False}


def test_register_system_and_execution_route_groups_registers_both(monkeypatch):
    built_system_kwargs = {}
    system_register_calls = []
    execution_register_calls = []

    def _fake_build_system_route_deps(**kwargs):
        built_system_kwargs["kwargs"] = kwargs
        return {"system": "ok"}

    monkeypatch.setattr(
        registry_module,
        "build_system_route_deps",
        _fake_build_system_route_deps,
    )
    monkeypatch.setattr(
        registry_module,
        "register_system_routes",
        lambda kr_bp, *, logger, deps: system_register_calls.append((kr_bp, logger, deps)),
    )
    monkeypatch.setattr(
        registry_module,
        "register_jongga_execution_routes",
        lambda kr_bp, **kwargs: execution_register_calls.append((kr_bp, kwargs)),
    )

    run_user = lambda **_kwargs: {"count": 1}
    sentinel_bp = object()
    sentinel_logger = object()

    registry_module.register_system_and_execution_route_groups(
        sentinel_bp,
        logger=sentinel_logger,
        data_dir="data",
        load_json_file_fn=lambda _filename: {},
        load_csv_file_fn=lambda _filename: [],
        get_data_path_fn=lambda filename: f"data/{filename}",
        trigger_market_gate_background_refresh_fn=lambda: None,
        run_user_gemini_reanalysis_fn=run_user,
        project_root_getter=lambda: "/tmp/project",
    )

    assert system_register_calls
    assert system_register_calls[0][0] is sentinel_bp
    assert system_register_calls[0][1] is sentinel_logger
    assert system_register_calls[0][2] == {"system": "ok"}
    assert built_system_kwargs["kwargs"]["run_user_gemini_reanalysis"] is run_user

    assert execution_register_calls
    assert execution_register_calls[0][0] is sentinel_bp
    assert execution_register_calls[0][1]["data_dir"] == "data"
