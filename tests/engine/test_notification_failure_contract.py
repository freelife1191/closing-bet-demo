#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""INFRA-043: 실제 발송 경계의 차단, 반환값, 비밀 비노출 계약."""

import logging
from unittest.mock import Mock

import pytest
import requests
from flask import Flask, g

from app.routes.common_notification_routes import register_common_notification_routes
from app.routes.common_route_context import CommonRouteContext
from engine.messenger import Messenger
from engine.messenger_config import MessengerConfig
from services import notifier_channels


SECRET = "FAKE_PRIVATE_NOTIFICATION_CANARY"


@pytest.fixture
def messenger(monkeypatch):
    values = {
        "NOTIFICATION_ENABLED": "true", "TELEGRAM_BOT_TOKEN": SECRET,
        "TELEGRAM_CHAT_ID": "123", "DISCORD_WEBHOOK_URL": "https://invalid.test/" + SECRET,
        "SMTP_HOST": "smtp.invalid.test", "SMTP_USER": "sender@example.test",
        "SMTP_PASSWORD": SECRET, "EMAIL_RECIPIENTS": "receiver@example.test",
    }
    for key, value in values.items():
        monkeypatch.setenv(key, value)
    return Messenger(MessengerConfig())


@pytest.fixture
def transport(monkeypatch):
    post = Mock(return_value=Mock(ok=True, status_code=200))
    smtp = Mock()
    smtp.return_value.__enter__ = Mock(return_value=smtp)
    smtp.return_value.__exit__ = Mock(return_value=False)
    monkeypatch.setattr("requests.post", post)
    monkeypatch.setattr("smtplib.SMTP", smtp)
    return post, smtp


@pytest.mark.parametrize("platform", ["discord", "telegram", "email"])
@pytest.mark.parametrize("disabled", [True, False])
def test_sender_and_facade_preserve_result_and_disabled(messenger, transport, platform, disabled):
    messenger.config.disabled = disabled
    result = getattr(messenger, "_send_" + platform)({"title": "QA", "signals": []})
    assert result is (not disabled)
    post, smtp = transport
    assert post.call_count + smtp.call_count == (0 if disabled else 1)


@pytest.mark.parametrize("platform", ["discord", "telegram", "email"])
def test_direct_sender_cannot_bypass_disabled(messenger, transport, platform):
    messenger.config.disabled = True
    data = messenger._build_message_data_from_payload({"title": "QA", "signals": []})
    assert messenger.senders[platform].send(data) is False
    assert sum(call.call_count for call in transport) == 0


@pytest.mark.parametrize("platform", ["discord", "telegram", "email"])
def test_sender_exception_is_false_without_secret(messenger, transport, caplog, platform):
    for call in transport:
        call.side_effect = requests.ConnectionError(SECRET)
    with caplog.at_level(logging.ERROR):
        assert getattr(messenger, "_send_" + platform)({"title": "QA"}) is False
    assert caplog.records
    assert SECRET not in caplog.text


@pytest.mark.parametrize("platform", ["discord", "telegram"])
def test_remote_error_body_never_enters_logs(messenger, transport, caplog, platform):
    transport[0].return_value = Mock(ok=False, status_code=502, text=SECRET)
    with caplog.at_level(logging.ERROR):
        assert getattr(messenger, "_send_" + platform)({"title": "QA"}) is False
    assert caplog.records
    assert SECRET not in caplog.text


@pytest.mark.parametrize("platform", ["discord", "telegram"])
@pytest.mark.parametrize("disabled", [True, False])
def test_custom_sender_disabled_and_safe_exception(messenger, transport, caplog, platform, disabled):
    messenger.config.disabled = disabled
    transport[0].side_effect = requests.ConnectionError(SECRET)
    with caplog.at_level(logging.INFO):
        assert getattr(messenger, "_send_" + platform + "_custom")("QA", "message") is False
    assert transport[0].call_count == (0 if disabled else 1)
    assert SECRET not in caplog.text


@pytest.mark.parametrize("platform", ["discord", "telegram", "slack", "email"])
def test_notifier_channel_exception_never_logs_credentials(transport, caplog, platform):
    for call in transport:
        call.side_effect = requests.ConnectionError(SECRET)
    logger = logging.getLogger("notification-contract")
    args = {
        "discord": ["https://invalid.test/" + SECRET, "QA", logger],
        "telegram": [SECRET, "123", "QA", logger],
        "slack": ["https://invalid.test/" + SECRET, "QA", logger],
        "email": ["smtp.invalid.test", 587, "sender@example.test", SECRET,
                  ["receiver@example.test"], "QA", logger],
    }
    with caplog.at_level(logging.ERROR):
        assert getattr(notifier_channels, "send_" + platform + "_message")(*args[platform]) is False
    assert caplog.records
    assert SECRET not in caplog.text


@pytest.mark.parametrize("platform", ["discord", "telegram", "email"])
@pytest.mark.parametrize("mode", ["success", "disabled", "exception"])
def test_actual_route_reports_transport_result(monkeypatch, messenger, transport, platform, mode, caplog):
    from flask import Blueprint

    monkeypatch.setenv("ADMIN_EMAILS", "admin@example.test")
    monkeypatch.setenv("NOTIFICATION_ENABLED", "false" if mode == "disabled" else "true")
    if mode == "exception":
        for call in transport:
            call.side_effect = requests.ConnectionError(SECRET)
    app = Flask(__name__)
    app.before_request(lambda: setattr(g, "user_email", "admin@example.test"))
    bp = Blueprint("notification-contract", __name__)
    context = Mock(spec=CommonRouteContext)
    context.logger = logging.getLogger("notification-route-contract")
    register_common_notification_routes(bp, context)
    app.register_blueprint(bp, url_prefix="/api")
    response = app.test_client().post("/api/notification/send", json={"platform": platform})
    assert response.status_code == (200 if mode == "success" else 503 if mode == "disabled" else 502)
    assert response.get_json()["status"] == ("success" if mode == "success" else "error")
    assert SECRET not in response.get_data(as_text=True) + caplog.text
    if mode == "disabled":
        assert sum(call.call_count for call in transport) == 0


@pytest.mark.parametrize("platform", ["discord", "telegram"])
@pytest.mark.parametrize("ok", [True, False])
def test_custom_sender_uses_http_result(messenger, transport, caplog, platform, ok):
    transport[0].return_value = Mock(ok=ok, status_code=200 if ok else 502, text=SECRET)
    assert getattr(messenger, "_send_" + platform + "_custom")("QA", "message") is ok
    assert SECRET not in caplog.text


def test_route_outer_exception_keeps_secret_out_of_response_and_log(monkeypatch, caplog):
    from flask import Blueprint

    monkeypatch.setenv("ADMIN_EMAILS", "admin@example.test")
    monkeypatch.setattr("engine.messenger.Messenger", Mock(side_effect=RuntimeError(SECRET)))
    app = Flask(__name__)
    app.before_request(lambda: setattr(g, "user_email", "admin@example.test"))
    bp = Blueprint("outer-error", __name__)
    context = Mock(spec=CommonRouteContext)
    context.logger = logging.getLogger("outer-error")
    register_common_notification_routes(bp, context)
    app.register_blueprint(bp, url_prefix="/api")
    with caplog.at_level(logging.ERROR):
        response = app.test_client().post("/api/notification/send", json={"platform": "discord"})
    assert response.status_code == 500
    assert response.get_json() == {"status": "error", "message": "Notification request failed"}
    assert caplog.records
    assert SECRET not in response.get_data(as_text=True) + caplog.text


def test_notifier_outer_exception_returns_failure_without_secret(monkeypatch, caplog):
    from services.notifier import NotificationService

    monkeypatch.setenv("NOTIFICATION_ENABLED", "true")
    monkeypatch.setenv("NOTIFICATION_CHANNELS", "discord")
    service = NotificationService()
    monkeypatch.setattr(service, "format_jongga_message", lambda *_: "QA")
    monkeypatch.setattr(service, "send_discord", Mock(side_effect=RuntimeError(SECRET)))
    with caplog.at_level(logging.ERROR):
        result = service.send_all([{"name": "QA"}])
    assert result == {"discord": False}
    assert caplog.records
    assert SECRET not in caplog.text


def test_screener_outer_exception_does_not_log_secret(messenger, monkeypatch, caplog):
    monkeypatch.setattr("engine.messenger.MessageDataBuilder.build", Mock(side_effect=RuntimeError(SECRET)))
    result = Mock(signals=[{"name": "QA"}])
    with caplog.at_level(logging.ERROR):
        messenger.send_screener_result(result)
    assert caplog.records
    assert SECRET not in caplog.text
