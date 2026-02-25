#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Common Portfolio Routes 리팩토링 회귀 테스트
"""

from __future__ import annotations

import os
import sys
import types

from flask import Blueprint, Flask

sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from app.routes.common_portfolio_routes import register_common_portfolio_routes
from app.routes.common_route_context import CommonRouteContext


class _DummyPaperTrading:
    def __init__(self):
        self.started = 0

    def start_background_sync(self):
        self.started += 1

    def get_portfolio_valuation(self):
        return {"status": "ok", "cash": 100}

    def buy_stock(self, ticker, name, price, quantity):
        return {
            "status": "success",
            "ticker": ticker,
            "name": name,
            "price": price,
            "quantity": quantity,
        }

    def sell_stock(self, ticker, price, quantity):
        return {"status": "success", "ticker": ticker, "price": price, "quantity": quantity}

    def reset_account(self):
        return True

    def deposit_cash(self, amount):
        return {"status": "success", "amount": amount}

    def get_trade_history(self, limit):
        return {"trades": [], "limit": limit}

    def get_asset_history(self, limit):
        return [{"value": 1, "limit": limit}]


class _FailingPaperTrading(_DummyPaperTrading):
    def buy_stock(self, *_a, **_k):
        raise RuntimeError("buy failed")

    def get_trade_history(self, *_a, **_k):
        raise RuntimeError("history failed")


def _build_ctx(paper_trading):
    return CommonRouteContext(
        logger=types.SimpleNamespace(
            info=lambda *_a, **_k: None,
            warning=lambda *_a, **_k: None,
            error=lambda *_a, **_k: None,
        ),
        update_lock=None,
        update_status_file="",
        load_update_status=lambda: {},
        start_update=lambda _items: None,
        update_item_status=lambda _name, _status: None,
        stop_update=lambda: None,
        finish_update=lambda: None,
        run_background_update=lambda *_a, **_k: None,
        paper_trading=paper_trading,
    )


def _create_client(ctx: CommonRouteContext):
    app = Flask(__name__)
    app.testing = True
    bp = Blueprint("common_test", __name__)
    register_common_portfolio_routes(bp, ctx)
    app.register_blueprint(bp, url_prefix="/api")
    return app.test_client()


def test_get_portfolio_data_starts_sync_and_returns_payload():
    service = _DummyPaperTrading()
    client = _create_client(_build_ctx(service))

    response = client.get("/api/portfolio")

    assert response.status_code == 200
    assert response.get_json()["status"] == "ok"
    assert service.started == 1


def test_buy_stock_returns_400_when_required_fields_missing():
    client = _create_client(_build_ctx(_DummyPaperTrading()))

    response = client.post("/api/portfolio/buy", json={"ticker": "005930"})

    assert response.status_code == 400
    payload = response.get_json()
    assert payload["status"] == "error"
    assert payload["message"] == "Missing data"


def test_buy_stock_returns_error_shape_on_exception():
    client = _create_client(_build_ctx(_FailingPaperTrading()))

    response = client.post(
        "/api/portfolio/buy",
        json={"ticker": "005930", "name": "삼성전자", "price": 1000, "quantity": 1},
    )

    assert response.status_code == 500
    payload = response.get_json()
    assert payload["status"] == "error"
    assert "buy failed" in payload["message"]


def test_get_trade_history_returns_error_payload_on_exception():
    client = _create_client(_build_ctx(_FailingPaperTrading()))

    response = client.get("/api/portfolio/history")

    assert response.status_code == 500
    payload = response.get_json()
    assert "history failed" in payload["error"]


def test_buy_stock_returns_400_when_quantity_is_not_numeric():
    client = _create_client(_build_ctx(_DummyPaperTrading()))

    response = client.post(
        "/api/portfolio/buy",
        json={"ticker": "005930", "name": "삼성전자", "price": 1000, "quantity": "abc"},
    )

    assert response.status_code == 400
    payload = response.get_json()
    assert payload["status"] == "error"
    assert payload["message"] == "Missing data"


def test_buy_stock_returns_400_when_price_is_not_numeric():
    client = _create_client(_build_ctx(_DummyPaperTrading()))

    response = client.post(
        "/api/portfolio/buy",
        json={"ticker": "005930", "name": "삼성전자", "price": "abc", "quantity": 1},
    )

    assert response.status_code == 400
    payload = response.get_json()
    assert payload["status"] == "error"
    assert payload["message"] == "Missing data"


def test_sell_stock_returns_400_when_price_is_not_numeric():
    client = _create_client(_build_ctx(_DummyPaperTrading()))

    response = client.post(
        "/api/portfolio/sell",
        json={"ticker": "005930", "price": "abc", "quantity": 1},
    )

    assert response.status_code == 400
    payload = response.get_json()
    assert payload["status"] == "error"
    assert payload["message"] == "Missing data"


def test_trade_history_limit_is_normalized_and_capped():
    client = _create_client(_build_ctx(_DummyPaperTrading()))

    invalid_limit_response = client.get("/api/portfolio/history?limit=abc")
    assert invalid_limit_response.status_code == 200
    assert invalid_limit_response.get_json()["limit"] == 50

    capped_limit_response = client.get("/api/portfolio/history?limit=999999")
    assert capped_limit_response.status_code == 200
    assert capped_limit_response.get_json()["limit"] == 500


def test_asset_history_limit_is_normalized_and_capped():
    client = _create_client(_build_ctx(_DummyPaperTrading()))

    invalid_limit_response = client.get("/api/portfolio/history/asset?limit=abc")
    assert invalid_limit_response.status_code == 200
    assert invalid_limit_response.get_json()["history"][0]["limit"] == 30

    capped_limit_response = client.get("/api/portfolio/history/asset?limit=999999")
    assert capped_limit_response.status_code == 200
    assert capped_limit_response.get_json()["history"][0]["limit"] == 500
