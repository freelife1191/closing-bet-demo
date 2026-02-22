#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KR Market 데이터 라우트 오케스트레이터 회귀 테스트
"""

import os
import sys


sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

import app.routes.kr_market_data_http_routes as data_routes_module


def test_register_market_data_routes_delegates_all_groups(monkeypatch):
    calls: list[tuple[str, object, object, dict]] = []
    sentinel_bp = object()
    sentinel_logger = object()
    sentinel_deps = {"sample": 1}

    def _record(name: str):
        def _inner(kr_bp, *, logger, deps):
            calls.append((name, kr_bp, logger, deps))

        return _inner

    monkeypatch.setattr(
        data_routes_module,
        "register_market_data_signal_routes",
        _record("signals"),
    )
    monkeypatch.setattr(
        data_routes_module,
        "register_market_data_ai_routes",
        _record("ai"),
    )
    monkeypatch.setattr(
        data_routes_module,
        "register_market_data_jongga_routes",
        _record("jongga"),
    )
    monkeypatch.setattr(
        data_routes_module,
        "register_market_data_backtest_stock_routes",
        _record("backtest_stock"),
    )

    data_routes_module.register_market_data_routes(
        sentinel_bp,
        logger=sentinel_logger,
        deps=sentinel_deps,
    )

    assert [name for name, *_ in calls] == ["signals", "ai", "jongga", "backtest_stock"]
    assert all(bp is sentinel_bp for _, bp, _, _ in calls)
    assert all(logger is sentinel_logger for _, _, logger, _ in calls)
    assert all(deps is sentinel_deps for _, _, _, deps in calls)

