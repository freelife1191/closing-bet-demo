#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""관리자 라우트 게이트 회귀 테스트

화면이 버튼을 감추는 것과 서버가 요청을 거부하는 것은 다른 일이다. [INFRA-042] 이전에는
앞의 것만 있었다.
"""

import os
import sys

from flask import Flask, g, jsonify, request

sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from app.routes.route_guards import require_admin


def _create_client(monkeypatch, *, identity_email: str | None):
    """신원이 이미 확정된 상태를 만들어 게이트만 잰다.

    before_request 의 서명 검증은 tests/app/test_identity_gate.py 가 따로 잰다. 여기서
    그것까지 세우면 게이트가 아니라 서명을 재게 된다.
    """
    app = Flask(__name__)
    app.testing = True

    @app.before_request
    def _seed_identity():
        # 실제 before_request 와 같이 OPTIONS 에서 일찍 빠진다(app/__init__.py:171).
        # 이 한 줄이 preflight 검사의 전제다.
        if request.method == "OPTIONS":
            return
        g.user_email = identity_email

    @app.route("/probe", methods=["POST", "OPTIONS"])
    @require_admin
    def probe():
        if request.method == "OPTIONS":
            return jsonify({"status": "ok"}), 200
        return jsonify({"status": "ran"})

    monkeypatch.setenv("ADMIN_EMAILS", "admin@example.com")
    return app.test_client()


def test_request_without_identity_is_refused(monkeypatch):
    client = _create_client(monkeypatch, identity_email=None)
    res = client.post("/probe")
    assert res.status_code == 403
    assert res.get_json() == {"error": "Forbidden"}


def test_non_admin_identity_is_refused(monkeypatch):
    client = _create_client(monkeypatch, identity_email="someone@example.com")
    res = client.post("/probe")
    assert res.status_code == 403


def test_admin_identity_passes(monkeypatch):
    """막는 것만 재면 게이트가 전부를 막아도 통과한다. 정상 경로를 함께 잰다."""
    client = _create_client(monkeypatch, identity_email="admin@example.com")
    res = client.post("/probe")
    assert res.status_code == 200
    assert res.get_json() == {"status": "ran"}


def test_options_preflight_passes_without_identity(monkeypatch):
    """preflight 를 막으면 브라우저가 본 요청을 아예 보내지 않는다.

    before_request 가 OPTIONS 에서 일찍 반환해 g.user_email 을 세우지 않으므로
    (app/__init__.py:171), 예외가 없으면 관리자의 preflight 도 403 을 받는다. 그러면
    jongga-v2/reanalyze-gemini 를 쓰는 화면이 통째로 멈춘다.
    """
    client = _create_client(monkeypatch, identity_email=None)
    res = client.open("/probe", method="OPTIONS")
    assert res.status_code == 200


def test_decorator_keeps_view_name(monkeypatch):
    """functools.wraps 가 없으면 두 번째 라우트 등록이 터진다.

    Flask 는 뷰 함수의 __name__ 을 엔드포인트 이름으로 삼는다. 감싼 함수의 이름이
    전부 같으면 두 번째 add_url_rule 에서
    AssertionError: View function mapping is overwriting an existing endpoint 가 난다.
    여섯 자리에 붙일 데코레이터이므로 이 성질이 필수다.
    """
    # 이름만 재면 wraps 를 흉내 낸 구현도 통과한다. 실제로 두 라우트를 등록해 본다.
    app = Flask(__name__)

    @app.route("/a", methods=["POST"])
    @require_admin
    def view_a():
        return jsonify({"which": "a"})

    @app.route("/b", methods=["POST"])
    @require_admin
    def view_b():
        return jsonify({"which": "b"})

    assert {"view_a", "view_b"} <= set(app.view_functions)
