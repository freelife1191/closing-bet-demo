#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""모의투자 HTTP 신원 경계: 공개 라우트가 저장소에 닿기 전에 차단되는지 확인한다."""

import base64
import hashlib
import hmac
import logging
import time
from types import SimpleNamespace
from urllib.parse import urlsplit

import pytest
from flask import Blueprint, Flask

from app.routes.common_portfolio_routes import register_common_portfolio_routes


KEY = "isolated-portfolio-test-key"
ROUTES = [
    ("GET", "/portfolio", None, "get_portfolio_valuation"),
    ("GET", "/portfolio/history", None, "get_trade_history"),
    ("GET", "/portfolio/history/asset", None, "get_asset_history"),
    ("POST", "/portfolio/reset", {}, "reset_account"),
    ("POST", "/portfolio/buy", {"ticker": "005930", "name": "삼성", "price": 100, "quantity": 1}, "buy_stock"),
    ("POST", "/portfolio/buy/bulk", {"orders": [{"ticker": "005930", "name": "삼성", "price": 100, "quantity": 1}]}, "buy_stocks_bulk"),
    ("POST", "/portfolio/sell", {"ticker": "005930", "price": 100, "quantity": 1}, "sell_stock"),
    ("POST", "/portfolio/deposit", {"amount": 100}, "deposit_cash"),
]


def signed_identity(email: str, expires: int | None = None, *, method: str = "GET", path: str = "/api/portfolio") -> str:
    encoded = base64.urlsafe_b64encode(email.encode()).decode().rstrip("=")
    expiry = int(time.time()) + 120 if expires is None else expires
    prefix = f"v2.{encoded}.{expiry}"
    encoded_path = base64.urlsafe_b64encode(path.encode()).decode().rstrip("=")
    payload = f"{prefix}.{method}.{encoded_path}"
    mac = hmac.new(KEY.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{prefix}.{mac}"


class RecordingService:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple, dict]] = []

    def __getattr__(self, name: str):
        def call(*args, **kwargs):
            self.calls.append((name, args, kwargs))
            if name == "get_asset_history":
                return []
            if name == "reset_account":
                return True
            return {"status": "success"}
        return call


@pytest.fixture
def client_and_service(monkeypatch):
    monkeypatch.setenv("INTERNAL_IDENTITY_SECRET", KEY)
    service = RecordingService()
    app = Flask(__name__)
    bp = Blueprint("portfolio_boundary", __name__)
    register_common_portfolio_routes(bp, SimpleNamespace(paper_trading=service, logger=logging.getLogger(__name__)))
    app.register_blueprint(bp, url_prefix="/api")
    return app.test_client(), service


@pytest.mark.parametrize("method,path,payload,operation", ROUTES)
@pytest.mark.parametrize("identity", [None, "forged.invalid.signature", "expired"])
def test_unverified_identity_never_reaches_service(client_and_service, method, path, payload, operation, identity):
    client, service = client_and_service
    headers = {"X-User-Email": "victim@example.test", "X-Session-Id": "victim@example.test"}
    if identity:
        headers["X-Auth-Identity"] = signed_identity("alice@example.test", expires=1, method=method, path="/api" + path) if identity == "expired" else identity
    response = client.open("/api" + path, method=method, json=payload, headers=headers)
    assert response.status_code == 401
    assert "로그인" in response.get_json()["message"]
    assert service.calls == []


@pytest.mark.parametrize("method,path,payload,operation", ROUTES)
def test_every_route_passes_only_verified_owner(client_and_service, method, path, payload, operation):
    client, service = client_and_service
    body = {**(payload or {}), "owner_id": "victim@example.test"} if method == "POST" else None
    response = client.open("/api" + path + "?owner_id=victim@example.test", method=method, json=body,
                           headers={"X-Auth-Identity": signed_identity("alice@example.test", method=method, path="/api" + path), "X-User-Email": "victim@example.test"})
    assert response.status_code == 200
    account_calls = [call for call in service.calls if call[0] == operation]
    assert len(account_calls) == 1
    assert account_calls[0][2]["owner_id"] == "alice@example.test"


def test_missing_secret_fails_closed(client_and_service, monkeypatch):
    client, service = client_and_service
    monkeypatch.delenv("INTERNAL_IDENTITY_SECRET")
    response = client.get("/api/portfolio", headers={"X-Auth-Identity": signed_identity("alice@example.test")})
    assert response.status_code == 401
    assert service.calls == []


def test_failed_reset_is_not_reported_as_success(client_and_service):
    client, service = client_and_service
    service.reset_account = lambda **kwargs: False
    response = client.post("/api/portfolio/reset", headers={"X-Auth-Identity": signed_identity("alice@example.test", method="POST", path="/api/portfolio/reset")})
    assert response.status_code == 500
    assert response.get_json()["status"] == "error"


@pytest.fixture
def real_portfolio_client(tmp_path, monkeypatch):
    from services.paper_trading import PaperTradingService

    monkeypatch.setenv("INTERNAL_IDENTITY_SECRET", KEY)
    service = PaperTradingService(db_path=str(tmp_path / "accounts.sqlite3"), auto_start_sync=False)
    monkeypatch.setattr(service, "start_background_sync", lambda: None)
    monkeypatch.setattr(service, "_wait_for_initial_price_sync", lambda holdings, prices: prices)
    service.price_cache["005930"] = 100
    app = Flask(__name__)
    bp = Blueprint("real_portfolio_boundary", __name__)
    register_common_portfolio_routes(bp, SimpleNamespace(paper_trading=service, logger=logging.getLogger(__name__)))
    app.register_blueprint(bp, url_prefix="/api")
    return app.test_client(), service


def test_two_signed_users_have_separate_balances_trades_and_reset(real_portfolio_client):
    client, service = real_portfolio_client
    alice, bob = "alice@example.test", "bob@example.test"

    def send(owner, method, path, **kwargs):
        headers = {"X-Auth-Identity": signed_identity(owner, method=method, path=urlsplit(path).path)}
        return client.open(path, method=method, headers=headers, **kwargs)

    def portfolio(owner):
        response = send(owner, "GET", "/api/portfolio")
        assert response.status_code == 200
        return response.get_json()

    assert portfolio(alice)["cash"] == portfolio(bob)["cash"] == 100_000_000
    assert send(alice, "POST", "/api/portfolio/deposit", json={"amount": 1000, "owner_id": bob}).get_json()["status"] == "success"
    assert send(alice, "POST", "/api/portfolio/buy", json={"ticker": "005930", "name": "A 종목", "price": 100, "quantity": 2}).get_json()["status"] == "success"
    assert send(bob, "POST", "/api/portfolio/buy/bulk", json={"orders": [{"ticker": "005930", "name": "B 종목", "price": 100, "quantity": 3}]}).get_json()["summary"]["success"] == 1
    assert send(alice, "POST", "/api/portfolio/sell", json={"ticker": "005930", "price": 100, "quantity": 1}).get_json()["status"] == "success"
    a, b = portfolio(alice), portfolio(bob)
    assert a["cash"] == 100_000_900
    assert b["cash"] == 99_999_700
    assert a["holdings"][0]["quantity"] == 1
    assert b["holdings"][0]["quantity"] == 3
    for owner, name, cash in [(alice, "A 종목", a["cash"]), (bob, "B 종목", b["cash"])]:
        trades = send(owner, "GET", "/api/portfolio/history?ticker=005930").get_json()["trades"]
        assert trades and all(row["name"] == name for row in trades)
        history = send(owner, "GET", "/api/portfolio/history/asset?days=30").get_json()["history"]
        assert history[-1]["cash"] == cash
    b_history = send(bob, "GET", "/api/portfolio/history").get_json()
    assert send(alice, "POST", "/api/portfolio/reset", json={"owner_id": bob}).get_json()["status"] == "success"
    assert portfolio(alice)["cash"] == 100_000_000
    assert portfolio(alice)["holdings"] == []
    assert portfolio(bob)["cash"] == b["cash"]
    assert send(bob, "GET", "/api/portfolio/history").get_json() == b_history
    assert service.price_cache["005930"] == 100


def test_unverified_requests_do_not_create_an_account(real_portfolio_client):
    client, service = real_portfolio_client
    response = client.post("/api/portfolio/deposit", json={"amount": 100, "owner_id": "alice@example.test"})
    assert response.status_code == 401
    with service.get_read_context() as conn:
        assert conn.execute("SELECT COUNT(*) FROM balance").fetchone()[0] == 0


def test_personal_portfolio_response_cannot_be_shared_cached(client_and_service):
    client, _ = client_and_service
    response = client.get("/api/portfolio", headers={"X-Auth-Identity": signed_identity("alice@example.test")})
    assert response.cache_control.no_store is True
    assert response.cache_control.private is True


@pytest.mark.parametrize("method,path", [("GET", "/api/portfolio/history"), ("POST", "/api/portfolio/reset")])
def test_replayed_portfolio_signature_never_reaches_service(client_and_service, method, path):
    client, service = client_and_service
    headers = {"X-Auth-Identity": signed_identity("alice@example.test")}
    response = client.open(path, method=method, headers=headers)
    assert response.status_code == 401
    assert service.calls == []
