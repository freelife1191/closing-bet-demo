#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Peer audit metadata and cached-only portfolio regression."""
import importlib
from types import SimpleNamespace

from flask import Flask
import pytest


@pytest.mark.parametrize("peer", ["127.0.0.1", None])
def test_activity_hook_does_not_promote_forwarded_header(monkeypatch, peer):
    from app import _register_activity_logging
    events = []
    logger_module = importlib.import_module("services.activity_logger")
    monkeypatch.setattr(logger_module, "activity_logger", SimpleNamespace(log_action=lambda **kw: events.append(kw)))
    app = Flask(__name__)
    app.post("/qa/audit")(lambda: {"ok": True})
    _register_activity_logging(app)
    response = app.test_client().post("/qa/audit", headers={"X-Forwarded-For": "198.51.100.77, 203.0.113.1"}, environ_overrides={"REMOTE_ADDR": peer})
    assert response.status_code == 200
    assert len(events) == 1
    assert events[0]["ip_address"] == peer


def test_non_sync_worker_reloads_shared_price_cache_between_reads(tmp_path, monkeypatch):
    from services.paper_trading import PaperTradingService
    calls = []

    def forbidden(*args, **kwargs):
        calls.append(True)
        raise AssertionError("external provider forbidden")

    for name in ["_fetch_prices_toss", "_fetch_prices_naver", "_fetch_prices_yfinance", "_fetch_prices_pykrx"]:
        monkeypatch.setattr(PaperTradingService, name, forbidden)
    path = str(tmp_path / "shared.sqlite3")
    reader = PaperTradingService(db_path=path, auto_start_sync=False)
    assert reader.buy_stock("005930", "합성", 70_000, 1, owner_id="alice@example.test")["status"] == "success"
    assert reader.price_cache.get("005930") != 71_000
    writer = PaperTradingService(db_path=path, auto_start_sync=False)
    writer._persist_price_cache({"005930": 71_000})
    first = reader.get_portfolio_valuation(owner_id="alice@example.test")
    assert first["holdings"][0]["current_price"] == 71_000
    writer._persist_price_cache({"005930": 72_000})
    second = reader.get_portfolio_valuation(owner_id="alice@example.test")
    assert second["holdings"][0]["current_price"] == 72_000
    assert calls == []
    assert reader.bg_thread is None and writer.bg_thread is None
