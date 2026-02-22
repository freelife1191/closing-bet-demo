#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PaperTrading lazy singleton 리팩토링 회귀 테스트
"""

from __future__ import annotations

import services.paper_trading as paper_trading_module


def test_get_paper_trading_service_creates_singleton_once(monkeypatch):
    created = {"count": 0}

    class _DummyService:
        def __init__(self):
            created["count"] += 1

    monkeypatch.setattr(paper_trading_module, "PaperTradingService", _DummyService)
    monkeypatch.setattr(paper_trading_module, "_paper_trading_instance", None)

    first = paper_trading_module.get_paper_trading_service()
    second = paper_trading_module.get_paper_trading_service()

    assert first is second
    assert created["count"] == 1


def test_paper_trading_proxy_delegates_to_lazy_singleton(monkeypatch):
    class _DummyService:
        def __init__(self):
            self.called = 0

        def get_portfolio(self):
            self.called += 1
            return {"status": "ok", "called": self.called}

    monkeypatch.setattr(paper_trading_module, "PaperTradingService", _DummyService)
    monkeypatch.setattr(paper_trading_module, "_paper_trading_instance", None)

    first = paper_trading_module.paper_trading.get_portfolio()
    second = paper_trading_module.paper_trading.get_portfolio()

    assert first["status"] == "ok"
    assert second["called"] == 2
