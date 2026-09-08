#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""실제 request-context 경계에서 legacy와 다른 요청으로의 서명 재생을 검사한다."""

import base64
import hashlib
import hmac
import time

import pytest
from flask import Flask, g, jsonify

from app import _register_request_context

KEY = "identity-replay-fixture-only"
EMAIL = "owner@example.test"


def _header(*, legacy: bool = False, method: str = "GET", path: str = "/api/a") -> str:
    email = base64.urlsafe_b64encode(EMAIL.encode()).decode().rstrip("=")
    expiry = int(time.time()) + 120
    prefix = f"{email}.{expiry}" if legacy else f"v2.{email}.{expiry}"
    encoded_path = base64.urlsafe_b64encode(path.encode()).decode().rstrip("=")
    payload = prefix if legacy else f"{prefix}.{method}.{encoded_path}"
    mac = hmac.new(KEY.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{prefix}.{mac}"


def _app(monkeypatch):
    monkeypatch.setenv("INTERNAL_IDENTITY_SECRET", KEY)
    app = Flask(__name__)
    app.config["accepted"] = 0
    _register_request_context(app)

    @app.route("/api/a", methods=["GET", "POST"])
    @app.route("/api/b", methods=["GET", "POST"])
    def protected():
        if not g.get("user_email"):
            return jsonify(error="Unauthorized"), 401
        app.config["accepted"] += 1
        return jsonify(email=g.user_email)

    return app


def test_legacy_signature_cannot_authorize_a_protected_request(monkeypatch):
    app = _app(monkeypatch)
    response = app.test_client().get("/api/a", headers={"X-Auth-Identity": _header(legacy=True)})
    assert response.status_code == 401
    assert app.config["accepted"] == 0


@pytest.mark.parametrize("method,path", [("GET", "/api/b"), ("POST", "/api/a")])
def test_signature_replay_cannot_cross_path_or_method(monkeypatch, method, path):
    app = _app(monkeypatch)
    client = app.test_client()
    headers = {"X-Auth-Identity": _header()}
    assert client.get("/api/a", headers=headers).status_code == 200
    assert app.config["accepted"] == 1
    assert client.open(path, method=method, headers=headers).status_code == 401
    assert app.config["accepted"] == 1


def test_same_request_replay_and_query_policy_remain_explicit(monkeypatch):
    app = _app(monkeypatch)
    client = app.test_client()
    headers = {"X-Auth-Identity": _header()}
    for path in ["/api/a", "/api/a", "/api/a?mode=other"]:
        assert client.get(path, headers=headers).status_code == 200
    assert app.config["accepted"] == 3


def test_options_does_not_require_identity_or_trigger_handler(monkeypatch):
    app = _app(monkeypatch)
    assert app.test_client().options("/api/a").status_code == 200
    assert app.config["accepted"] == 0


def test_head_requires_its_own_method_signature(monkeypatch):
    app = _app(monkeypatch)
    client = app.test_client()
    assert client.head("/api/a", headers={"X-Auth-Identity": _header()}).status_code == 401
    assert client.head("/api/a", headers={"X-Auth-Identity": _header(method="HEAD")}).status_code == 200
    assert app.config["accepted"] == 1
