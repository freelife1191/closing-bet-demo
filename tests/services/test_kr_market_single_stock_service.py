#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KR Market single stock service 테스트
"""

from __future__ import annotations

import sys
import types

from services.kr_market_single_stock_service import execute_single_stock_analysis


def test_execute_single_stock_analysis_requires_code():
    status, payload = execute_single_stock_analysis(
        code=None,
        logger=type("L", (), {"error": lambda *_a, **_k: None, "warning": lambda *_a, **_k: None})(),
        run_coro_in_fresh_loop_fn=lambda *_a, **_k: None,
    )
    assert status == 400
    assert payload["error"] == "Stock code is required"


def test_execute_single_stock_analysis_returns_success_with_fake_generator(monkeypatch):
    fake_module = types.ModuleType("engine.generator")

    class _Grade:
        value = "A"

    class _Score:
        total = 9

    class _Signal:
        stock_code = "005930"
        stock_name = "삼성전자"
        grade = _Grade()
        score = _Score()

    async def _analyze(_code):
        return _Signal()

    def _update(_code, _signal):
        return None

    fake_module.analyze_single_stock_by_code = _analyze
    fake_module.update_single_signal_json = _update
    monkeypatch.setitem(sys.modules, "engine.generator", fake_module)

    status, payload = execute_single_stock_analysis(
        code="005930",
        logger=type("L", (), {"error": lambda *_a, **_k: None, "warning": lambda *_a, **_k: None})(),
        run_coro_in_fresh_loop_fn=lambda coro, **_k: __import__("asyncio").run(coro),
    )

    assert status == 200
    assert payload["status"] == "success"
    assert payload["signal"]["stock_code"] == "005930"
    assert payload["signal"]["grade"] == "A"

