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

from flask import Blueprint, Flask, g

import app.routes.kr_market_quota_http_routes as quota_routes


engine_config_module = importlib.import_module("engine.config")


def _create_client(
    *,
    max_free_usage: int = 10,
    get_user_usage_fn: Callable[[str | None], int] | None = None,
    recharge_usage_fn: Callable[[str | None, int], tuple[int, bool]] | None = None,
    user_email: str | None = None,
    session_id: str | None = None,
):
    app = Flask(__name__)
    app.testing = True

    # [INFRA-027] 신원은 before_request 가 확정한다. 라우트가 쿼리나 바디에서 신원을
    # 읽지 않는지 보려면 여기서 g 를 채워 주어야 한다.
    @app.before_request
    def _inject_identity():
        g.user_email = user_email
        g.session_id = session_id

    bp = Blueprint("kr_test_quota_routes", __name__)
    quota_routes.register_quota_routes(
        bp,
        logger=logging.getLogger("test.kr_market_quota_routes"),
        max_free_usage=max_free_usage,
        get_user_usage_fn=get_user_usage_fn or (lambda _usage_key: 0),
        recharge_usage_fn=recharge_usage_fn or (lambda _usage_key, _amount: (0, True)),
    )
    app.register_blueprint(bp, url_prefix="/api/kr")
    return app.test_client()


def test_get_user_quota_info_returns_expected_payload(monkeypatch):
    monkeypatch.setattr(
        engine_config_module,
        "app_config",
        SimpleNamespace(
            GOOGLE_GENAI_USE_VERTEXAI=True,
            GOOGLE_CLOUD_PROJECT="vertex-project",
            ZAI_API_KEY="zai-key",
        ),
    )
    client = _create_client(get_user_usage_fn=lambda _usage_key: 3, session_id="anon_1")

    # 쿼리 파라미터로 신원을 넘겨도 무시되어야 한다.
    response = client.get("/api/kr/user/quota?email=victim@example.com")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["usage"] == 3
    assert payload["remaining"] == 7
    assert payload["server_key_configured"] is True


def test_get_user_quota_info_returns_error_payload_on_exception(monkeypatch):
    monkeypatch.setattr(
        engine_config_module,
        "app_config",
        SimpleNamespace(
            GOOGLE_GENAI_USE_VERTEXAI=False,
            GOOGLE_CLOUD_PROJECT="",
            ZAI_API_KEY="",
        ),
    )
    client = _create_client(
        get_user_usage_fn=lambda _usage_key: (_ for _ in ()).throw(RuntimeError("quota boom")),
        session_id="anon_1",
    )

    response = client.get("/api/kr/user/quota")

    assert response.status_code == 500
    assert response.get_json() == {"error": "quota boom"}


def test_recharge_user_quota_requires_identity():
    """[INFRA-027] 신원 없이는 충전할 수 없다. 종전에는 바디의 session_id 로 충분했다."""
    client = _create_client()

    response = client.post("/api/kr/user/quota/recharge", json={"session_id": "anon_1"})

    assert response.status_code == 401
    assert response.get_json() == {"error": "로그인이 필요합니다."}


def test_recharge_user_quota_returns_success_payload():
    client = _create_client(
        recharge_usage_fn=lambda _usage_key, _amount: (4, True),
        user_email="owner@example.com",
    )

    response = client.post("/api/kr/user/quota/recharge", json={})

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] == "success"
    assert payload["usage"] == 4
    assert payload["remaining"] == 6


def test_recharge_user_quota_returns_error_payload_on_exception():
    client = _create_client(
        recharge_usage_fn=lambda _usage_key, _amount: (
            (_ for _ in ()).throw(RuntimeError("recharge boom"))
        ),
        user_email="owner@example.com",
    )

    response = client.post("/api/kr/user/quota/recharge", json={})

    assert response.status_code == 500
    assert response.get_json() == {"error": "recharge boom"}
