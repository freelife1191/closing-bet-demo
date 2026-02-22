#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KR Market Quota HTTP Routes 리팩토링 회귀 테스트
"""

from __future__ import annotations

import importlib
import logging
from types import SimpleNamespace
from typing import Callable

from flask import Blueprint, Flask

import app.routes.kr_market_quota_http_routes as quota_routes


engine_config_module = importlib.import_module("engine.config")


def _create_client(
    *,
    max_free_usage: int = 10,
    get_user_usage_fn: Callable[[str | None], int] | None = None,
    recharge_usage_fn: Callable[[str | None, int], int] | None = None,
):
    app = Flask(__name__)
    app.testing = True

    bp = Blueprint("kr_test_quota_routes", __name__)
    quota_routes.register_quota_routes(
        bp,
        logger=logging.getLogger("test.kr_market_quota_routes"),
        max_free_usage=max_free_usage,
        get_user_usage_fn=get_user_usage_fn or (lambda _usage_key: 0),
        recharge_usage_fn=recharge_usage_fn or (lambda _usage_key, _amount: 0),
    )
    app.register_blueprint(bp, url_prefix="/api/kr")
    return app.test_client()


def test_get_user_quota_info_returns_expected_payload(monkeypatch):
    monkeypatch.setattr(
        engine_config_module,
        "app_config",
        SimpleNamespace(GOOGLE_API_KEY="", ZAI_API_KEY="zai-key"),
    )
    client = _create_client(get_user_usage_fn=lambda _usage_key: 3)

    response = client.get("/api/kr/user/quota?session_id=session-1")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["usage"] == 3
    assert payload["remaining"] == 7
    assert payload["server_key_configured"] is True


def test_get_user_quota_info_returns_error_payload_on_exception(monkeypatch):
    monkeypatch.setattr(
        engine_config_module,
        "app_config",
        SimpleNamespace(GOOGLE_API_KEY="", ZAI_API_KEY=""),
    )
    client = _create_client(
        get_user_usage_fn=lambda _usage_key: (_ for _ in ()).throw(RuntimeError("quota boom"))
    )

    response = client.get("/api/kr/user/quota?session_id=session-1")

    assert response.status_code == 500
    assert response.get_json() == {"error": "quota boom"}


def test_recharge_user_quota_requires_usage_key():
    client = _create_client()

    response = client.post("/api/kr/user/quota/recharge", json={})

    assert response.status_code == 400
    assert response.get_json() == {"error": "세션 정보가 없습니다."}


def test_recharge_user_quota_returns_success_payload():
    client = _create_client(recharge_usage_fn=lambda _usage_key, _amount: 4)

    response = client.post("/api/kr/user/quota/recharge", json={"session_id": "session-1"})

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] == "success"
    assert payload["usage"] == 4
    assert payload["remaining"] == 6


def test_recharge_user_quota_returns_error_payload_on_exception():
    client = _create_client(
        recharge_usage_fn=lambda _usage_key, _amount: (
            (_ for _ in ()).throw(RuntimeError("recharge boom"))
        )
    )

    response = client.post("/api/kr/user/quota/recharge", json={"session_id": "session-1"})

    assert response.status_code == 500
    assert response.get_json() == {"error": "recharge boom"}
