#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
/api/system/env 관리자 게이트 회귀 테스트

이 경로는 서버 .env 를 읽고 쓴다. 게이트가 사라지면 마스킹을 벗어난 값이 그대로
나가고 .env 를 아무나 덮어쓸 수 있으므로, 통과 조건을 여기에 고정한다.
"""

import os
import sys

import pytest
from flask import Flask


sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from app.routes import common
from app.routes import common_update_routes
from services.admin_helpers import verify_admin_api_token


def _create_client():
    app = Flask(__name__)
    app.testing = True
    app.register_blueprint(common.common_bp, url_prefix="/api")
    return app.test_client()


def test_verify_admin_api_token_rejects_when_unset(monkeypatch):
    monkeypatch.delenv("ADMIN_API_TOKEN", raising=False)

    assert verify_admin_api_token("anything") is False
    assert verify_admin_api_token(None) is False


def test_verify_admin_api_token_matches_exact_value(monkeypatch):
    monkeypatch.setenv("ADMIN_API_TOKEN", "s3cret-token")

    assert verify_admin_api_token("s3cret-token") is True
    assert verify_admin_api_token(" s3cret-token ") is True
    assert verify_admin_api_token("s3cret-toke") is False
    assert verify_admin_api_token("") is False
    assert verify_admin_api_token(None) is False


def test_verify_admin_api_token_rejects_non_ascii_without_raising(monkeypatch):
    """비ASCII 헤더가 403 이 아니라 500 을 만들지 않는지 고정한다.

    hmac.compare_digest 는 str 인자에 비ASCII 문자가 있으면 TypeError 를 던진다.
    그 예외가 그대로 흐르면 헤더에 한글 한 글자를 넣는 것만으로 500 과 스택
    트레이스가 나온다.
    """
    monkeypatch.setenv("ADMIN_API_TOKEN", "s3cret-token")

    assert verify_admin_api_token("토큰") is False
    assert verify_admin_api_token("s3cret-tokené") is False


@pytest.mark.parametrize("method", ["get", "post"])
def test_manage_env_rejects_request_without_token(monkeypatch, method):
    monkeypatch.setenv("ADMIN_API_TOKEN", "s3cret-token")
    client = _create_client()

    response = getattr(client, method)("/api/system/env", json={})

    assert response.status_code == 403
    assert response.get_json() == {"error": "Forbidden"}


@pytest.mark.parametrize("method", ["get", "post"])
def test_manage_env_rejects_wrong_token(monkeypatch, method):
    monkeypatch.setenv("ADMIN_API_TOKEN", "s3cret-token")
    client = _create_client()

    response = getattr(client, method)(
        "/api/system/env", json={}, headers={"X-Admin-Token": "wrong"}
    )

    assert response.status_code == 403


def test_manage_env_rejects_non_ascii_token_with_403(monkeypatch):
    """헤더에 한글을 넣어도 500 이 아니라 403 이 나가는지 고정한다."""
    monkeypatch.setenv("ADMIN_API_TOKEN", "s3cret-token")
    client = _create_client()

    response = client.get("/api/system/env", headers={"X-Admin-Token": "토큰"})

    assert response.status_code == 403


def test_manage_env_rejects_every_request_when_token_unset(monkeypatch):
    monkeypatch.delenv("ADMIN_API_TOKEN", raising=False)
    client = _create_client()

    response = client.get("/api/system/env", headers={"X-Admin-Token": ""})

    assert response.status_code == 403


def test_manage_env_allows_get_with_valid_token(monkeypatch, tmp_path):
    monkeypatch.setenv("ADMIN_API_TOKEN", "s3cret-token")
    env_file = tmp_path / ".env"
    env_file.write_text("AI_PROVIDER=gemini\n", encoding="utf-8")
    monkeypatch.setattr(
        common_update_routes, "resolve_env_path", lambda: str(env_file)
    )
    client = _create_client()

    response = client.get("/api/system/env", headers={"X-Admin-Token": "s3cret-token"})

    assert response.status_code == 200
    assert response.get_json() == {"AI_PROVIDER": "gemini"}


def test_manage_env_no_longer_accepts_delete(monkeypatch):
    monkeypatch.setenv("ADMIN_API_TOKEN", "s3cret-token")
    client = _create_client()

    response = client.delete(
        "/api/system/env", headers={"X-Admin-Token": "s3cret-token"}
    )

    assert response.status_code == 405
