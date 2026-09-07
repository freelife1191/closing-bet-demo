#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
/api/notification/send 관리자 게이트 회귀 테스트

이 경로는 서버 .env 에 저장된 운영자의 봇 토큰·웹훅·SMTP 계정으로 실제 발송을
수행한다. 게이트가 사라지면 누구든 POST 한 번으로 운영자 채널에 메시지를 보낼 수
있으므로, 통과 조건과 「막힐 때는 발송이 시작되지도 않는다」를 여기에 고정한다.
"""

import base64
import hashlib
import hmac
import os
import sys

import pytest
from flask import Flask

sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from app import _register_request_context
from app.routes import common


SECRET = "test-identity-secret"
ADMIN = "admin@example.com"
OUTSIDER = "outsider@example.com"


def _sign(email: str, exp: int) -> str:
    encoded = base64.urlsafe_b64encode(email.encode("utf-8")).decode("ascii").rstrip("=")
    payload = f"{encoded}.{exp}"
    mac = hmac.new(
        SECRET.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256
    ).hexdigest()
    return f"{payload}.{mac}"


def _identity_headers(email: str) -> dict:
    # 만료를 넉넉히 미래로 둔다. 만료 판정 자체는 test_identity_helpers.py 가 본다.
    return {"X-Auth-Identity": _sign(email, 4_000_000_000)}


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("INTERNAL_IDENTITY_SECRET", SECRET)
    monkeypatch.setenv("ADMIN_EMAILS", ADMIN)
    app = Flask(__name__)
    app.testing = True
    _register_request_context(app)
    app.register_blueprint(common.common_bp, url_prefix="/api")
    return app.test_client()


@pytest.fixture
def sent(monkeypatch):
    """Messenger 를 세우는 대신 발송 호출만 기록한다.

    라우트가 `from engine.messenger import Messenger` 를 함수 안에서 하므로
    모듈 속성을 갈아 끼우면 그대로 잡힌다. 게이트가 열려 버리면 이 목록에 값이
    쌓이고, 닫혀 있으면 비어 있다.
    """
    calls: list[tuple[str, dict]] = []

    class _FakeMessenger:
        discord_url = "https://discord.example/webhook"

        def _send_discord(self, data):
            calls.append(("discord", data))

    import engine.messenger

    monkeypatch.setattr(engine.messenger, "Messenger", _FakeMessenger)
    return calls


def test_request_without_identity_is_rejected(client, sent):
    response = client.post("/api/notification/send", json={"platform": "discord"})

    assert response.status_code == 403
    assert response.get_json()["message"] == "Forbidden"
    assert sent == []


def test_forged_identity_header_is_rejected(client, sent):
    response = client.post(
        "/api/notification/send",
        json={"platform": "discord"},
        headers={"X-Auth-Identity": "abc.4000000000.deadbeef"},
    )

    assert response.status_code == 403
    assert sent == []


def test_non_admin_identity_is_rejected(client, sent):
    """서명이 유효해도 ADMIN_EMAILS 밖이면 막는다."""
    response = client.post(
        "/api/notification/send",
        json={"platform": "discord"},
        headers=_identity_headers(OUTSIDER),
    )

    assert response.status_code == 403
    assert sent == []


def test_forged_user_email_header_is_rejected(client, sent):
    """종전의 X-User-Email 로는 관리자가 되지 못한다."""
    response = client.post(
        "/api/notification/send",
        json={"platform": "discord"},
        headers={"X-User-Email": ADMIN},
    )

    assert response.status_code == 403
    assert sent == []


def test_gate_runs_before_payload_validation(client, sent):
    """플랫폼 이름이 없어도 400 이 아니라 403 이 나간다.

    순서가 뒤집히면 게이트 밖에서 어떤 플랫폼 이름이 유효한지 떠볼 수 있다.
    """
    response = client.post("/api/notification/send", json={})

    assert response.status_code == 403
    assert sent == []


def test_rejects_admin_identity_when_admin_emails_unset(monkeypatch, sent):
    """관리자 목록이 비면 유효한 서명도 통과하지 못한다.

    설정을 빠뜨린 배포가 그대로 인증 없는 배포가 되지 않게 고정한다.
    tests/app/test_system_env_admin_gate.py 가 X-Admin-Token 쪽에 두고 있는
    같은 성격의 검사다.
    """
    monkeypatch.setenv("INTERNAL_IDENTITY_SECRET", SECRET)
    monkeypatch.delenv("ADMIN_EMAILS", raising=False)
    app = Flask(__name__)
    app.testing = True
    _register_request_context(app)
    app.register_blueprint(common.common_bp, url_prefix="/api")

    response = app.test_client().post(
        "/api/notification/send",
        json={"platform": "discord"},
        headers=_identity_headers(ADMIN),
    )

    assert response.status_code == 403
    assert sent == []


def test_rejects_valid_signature_when_secret_unset(monkeypatch, sent):
    """서명 비밀이 비면 어떤 헤더도 신원이 되지 못한다."""
    monkeypatch.delenv("INTERNAL_IDENTITY_SECRET", raising=False)
    monkeypatch.setenv("ADMIN_EMAILS", ADMIN)
    app = Flask(__name__)
    app.testing = True
    _register_request_context(app)
    app.register_blueprint(common.common_bp, url_prefix="/api")

    response = app.test_client().post(
        "/api/notification/send",
        json={"platform": "discord"},
        headers=_identity_headers(ADMIN),
    )

    assert response.status_code == 403
    assert sent == []


def test_admin_identity_sends(client, sent):
    response = client.post(
        "/api/notification/send",
        json={"platform": "discord"},
        headers=_identity_headers(ADMIN),
    )

    assert response.status_code == 200
    assert response.get_json()["status"] == "success"
    assert [platform for platform, _ in sent] == ["discord"]


def test_admin_identity_still_rejects_unknown_platform(client, sent, monkeypatch):
    """알 수 없는 플랫폼은 Messenger 를 세우기 전에 걸러진다.

    뒤에서 걸러내면 400 으로 끝날 요청 하나에도 서버 자격 증명으로 Messenger 가
    만들어진다. 생성자가 네트워크를 타는 날 그것이 곧 사고가 된다.
    """
    import engine.messenger

    def _explode():
        raise AssertionError("알 수 없는 플랫폼에서 Messenger 를 만들면 안 된다")

    monkeypatch.setattr(engine.messenger, "Messenger", _explode)

    response = client.post(
        "/api/notification/send",
        json={"platform": "carrier-pigeon"},
        headers=_identity_headers(ADMIN),
    )

    assert response.status_code == 400
    assert "Unknown platform" in response.get_json()["message"]
    assert sent == []
