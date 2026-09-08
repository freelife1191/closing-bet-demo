#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
신원 게이트 회귀 테스트

`g.user_email` 이 검증을 거치지 않으면 헤더 한 줄이 그대로 신원이 된다.
"""

import base64
import hashlib
import hmac
import os
import sys

from flask import Flask, g, jsonify

sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from app import _register_request_context


SECRET = "test-identity-secret"


def _sign(email: str, exp: int, *, method: str = "GET", path: str = "/probe") -> str:
    encoded = base64.urlsafe_b64encode(email.encode("utf-8")).decode("ascii").rstrip("=")
    prefix = f"v2.{encoded}.{exp}"
    encoded_path = base64.urlsafe_b64encode(path.encode("utf-8")).decode("ascii").rstrip("=")
    payload = f"{prefix}.{method}.{encoded_path}"
    mac = hmac.new(SECRET.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{prefix}.{mac}"


def _create_client():
    app = Flask(__name__)
    app.testing = True
    _register_request_context(app)

    @app.route("/probe")
    def probe():
        return jsonify({"email": g.get("user_email"), "session": g.get("session_id")})

    return app.test_client()


def test_forged_user_email_header_is_ignored(monkeypatch):
    monkeypatch.setenv("INTERNAL_IDENTITY_SECRET", SECRET)
    client = _create_client()

    res = client.get("/probe", headers={"X-User-Email": "victim@example.com"})

    assert res.get_json()["email"] is None


def test_forged_identity_header_is_ignored(monkeypatch):
    monkeypatch.setenv("INTERNAL_IDENTITY_SECRET", SECRET)
    client = _create_client()

    res = client.get("/probe", headers={"X-Auth-Identity": "abc.2000.deadbeef"})

    assert res.get_json()["email"] is None


def test_signed_identity_is_accepted(monkeypatch):
    monkeypatch.setenv("INTERNAL_IDENTITY_SECRET", SECRET)
    client = _create_client()

    far_future = 4102444800  # 2100-01-01
    res = client.get("/probe", headers={"X-Auth-Identity": _sign("owner@example.com", far_future)})

    assert res.get_json()["email"] == "owner@example.com"


def test_session_id_still_passes_through(monkeypatch):
    """익명 사용자의 챗봇 조회가 계속 동작해야 한다."""
    monkeypatch.setenv("INTERNAL_IDENTITY_SECRET", SECRET)
    client = _create_client()

    res = client.get("/probe", headers={"X-Session-Id": "anon_abc"})

    payload = res.get_json()
    assert payload["email"] is None
    assert payload["session"] == "anon_abc"


def test_email_shaped_session_id_is_dropped(monkeypatch):
    """X-Session-Id 로 남의 네임스페이스에 들어가지 못한다.

    챗봇 owner_id 와 쿼터 키는 검증된 이메일과 익명 ID 를 같은 문자열 공간에 담는다.
    이 헤더를 거르지 않으면 서명 게이트를 만들어 두고도 헤더 이름 하나로 우회된다.
    """
    monkeypatch.setenv("INTERNAL_IDENTITY_SECRET", SECRET)
    client = _create_client()

    res = client.get("/probe", headers={"X-Session-Id": "victim@example.com"})

    payload = res.get_json()
    assert payload["email"] is None
    assert payload["session"] is None
