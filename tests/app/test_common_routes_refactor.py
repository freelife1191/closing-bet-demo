#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Common 라우트 분해 회귀 테스트
"""

import os
import sys

from flask import Flask


sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from app.routes import common
from app.routes import common_update_routes


def _create_client():
    app = Flask(__name__)
    app.testing = True
    app.register_blueprint(common.common_bp, url_prefix="/api")
    return app.test_client()


def test_admin_check_reads_admin_emails_from_env(monkeypatch):
    monkeypatch.setenv("ADMIN_EMAILS", "alpha@example.com, beta@example.com")
    client = _create_client()

    response = client.get("/api/admin/check?email=BETA@example.com")
    assert response.status_code == 200
    assert response.get_json() == {"isAdmin": True}


def test_system_update_status_returns_debug_fields():
    client = _create_client()
    response = client.get("/api/system/update-status")

    assert response.status_code == 200
    payload = response.get_json()
    assert "_debug_path" in payload
    assert "_debug_exists" in payload


def test_system_update_status_merges_scheduler_running_message(monkeypatch):
    monkeypatch.setattr(
        common_update_routes,
        "get_scheduler_runtime_status",
        lambda data_dir="data": {
            "is_data_scheduling_running": True,
            "is_jongga_scheduling_running": False,
            "is_vcp_scheduling_running": False,
        },
    )

    client = _create_client()
    response = client.get("/api/system/update-status")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["isRunning"] is True
    assert payload["currentItem"] == "전체 스케쥴링 작업 진행 중인 상태"


def test_system_update_status_passes_context_data_dir_to_scheduler_status(monkeypatch):
    captured = {"data_dir": None}

    def _get_scheduler_runtime_status(*, data_dir="data"):
        captured["data_dir"] = data_dir
        return {
            "is_data_scheduling_running": False,
            "is_jongga_scheduling_running": False,
            "is_vcp_scheduling_running": False,
        }

    monkeypatch.setattr(
        common_update_routes,
        "get_scheduler_runtime_status",
        _get_scheduler_runtime_status,
    )

    client = _create_client()
    response = client.get("/api/system/update-status")

    assert response.status_code == 200
    assert captured["data_dir"] == os.path.dirname(common.route_context.update_status_file)


def test_system_update_status_requests_readonly_status_load(monkeypatch):
    captured = {"kwargs": None}

    def _load_update_status(**kwargs):
        captured["kwargs"] = dict(kwargs)
        return {
            "isRunning": False,
            "startTime": None,
            "currentItem": None,
            "items": [],
        }

    monkeypatch.setattr(common.route_context, "load_update_status", _load_update_status)

    client = _create_client()
    response = client.get("/api/system/update-status")

    assert response.status_code == 200
    assert captured["kwargs"]["deep_copy"] is False


def test_send_test_notification_uses_messenger_compat_interface(monkeypatch):
    created = []

    class _DummyMessenger:
        def __init__(self):
            self.discord_url = "https://example.com/webhook"
            self.telegram_token = "token"
            self.telegram_chat_id = "chat"
            self.smtp_user = "tester@example.com"
            self.calls = []
            created.append(self)

        def _send_discord(self, payload):
            self.calls.append(("discord", payload))

        def _send_telegram(self, payload):
            self.calls.append(("telegram", payload))

        def _send_email(self, payload):
            self.calls.append(("email", payload))

    import engine.messenger as messenger_module

    monkeypatch.setattr(messenger_module, "Messenger", _DummyMessenger)

    client = _create_client()
    response = client.post("/api/notification/send", json={"platform": "discord"})

    assert response.status_code == 200
    assert response.get_json()["status"] == "success"
    assert created
    assert created[0].calls[0][0] == "discord"
    assert created[0].calls[0][1]["title"].startswith("[Test] DISCORD")


def test_send_test_notification_rejects_unknown_platform():
    client = _create_client()
    response = client.post("/api/notification/send", json={"platform": "slack"})

    assert response.status_code == 400
    payload = response.get_json()
    assert payload["status"] == "error"
    assert "Unknown platform" in payload["message"]


def test_send_test_notification_requires_platform():
    client = _create_client()
    response = client.post("/api/notification/send", json={})

    assert response.status_code == 400
    assert response.get_json() == {
        "status": "error",
        "message": "Platform not specified",
    }


def test_send_test_notification_returns_config_error_for_unconfigured_platform(monkeypatch):
    class _DummyMessenger:
        def __init__(self):
            self.discord_url = ""
            self.telegram_token = "token"
            self.telegram_chat_id = "chat"
            self.smtp_user = "tester@example.com"

        def _send_discord(self, payload):
            raise AssertionError("should not be called")

        def _send_telegram(self, payload):
            raise AssertionError("should not be called")

        def _send_email(self, payload):
            raise AssertionError("should not be called")

    import engine.messenger as messenger_module

    monkeypatch.setattr(messenger_module, "Messenger", _DummyMessenger)

    client = _create_client()
    response = client.post("/api/notification/send", json={"platform": "discord"})

    assert response.status_code == 400
    assert response.get_json() == {
        "status": "error",
        "message": "Discord Webhook URL not set in server env",
    }


def test_send_test_notification_handles_send_exception(monkeypatch):
    class _DummyMessenger:
        def __init__(self):
            self.discord_url = "https://example.com/webhook"
            self.telegram_token = "token"
            self.telegram_chat_id = "chat"
            self.smtp_user = "tester@example.com"

        def _send_discord(self, payload):
            raise RuntimeError("send failed")

        def _send_telegram(self, payload):
            raise RuntimeError("send failed")

        def _send_email(self, payload):
            raise RuntimeError("send failed")

    import engine.messenger as messenger_module

    monkeypatch.setattr(messenger_module, "Messenger", _DummyMessenger)

    client = _create_client()
    response = client.post("/api/notification/send", json={"platform": "discord"})

    assert response.status_code == 500
    assert response.get_json() == {
        "status": "error",
        "message": "send failed",
    }


def test_system_log_event_injects_session_id_and_extracts_forwarded_ip(monkeypatch):
    captured = {}

    class _DummyActivityLogger:
        def log_action(self, user_id, action, details, ip_address):
            captured["user_id"] = user_id
            captured["action"] = action
            captured["details"] = details
            captured["ip_address"] = ip_address

    monkeypatch.setattr(
        common_update_routes,
        "_resolve_activity_logger",
        lambda: _DummyActivityLogger(),
    )

    client = _create_client()
    response = client.post(
        "/api/system/log-event",
        json={"action": "LOGIN", "details": {}},
        headers={
            "X-Session-Id": "session-123",
            "X-Forwarded-For": "10.0.0.1, 192.168.0.1",
        },
    )

    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}
    assert captured["user_id"] == "session-123"
    assert captured["action"] == "LOGIN"
    assert captured["details"]["session_id"] == "session-123"
    assert captured["ip_address"] == "10.0.0.1"


def test_system_log_event_returns_500_when_activity_logger_fails(monkeypatch):
    class _FailingActivityLogger:
        def log_action(self, user_id, action, details, ip_address):
            raise RuntimeError("log failed")

    monkeypatch.setattr(
        common_update_routes,
        "_resolve_activity_logger",
        lambda: _FailingActivityLogger(),
    )

    client = _create_client()
    response = client.post("/api/system/log-event", json={"action": "LOGIN", "details": {}})

    assert response.status_code == 500
    assert response.get_json() == {"error": "log failed"}


def test_system_env_get_returns_500_on_read_error(monkeypatch):
    def _raise_read_error(_env_path):
        raise RuntimeError("env read fail")

    monkeypatch.setattr(common_update_routes, "read_masked_env_vars", _raise_read_error)

    client = _create_client()
    response = client.get("/api/system/env")

    assert response.status_code == 500
    assert response.get_json() == {"error": "env read fail"}
