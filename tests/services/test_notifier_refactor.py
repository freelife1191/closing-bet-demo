#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Notifier 리팩토링 회귀 테스트
"""

from __future__ import annotations

import services.notifier as notifier_module
from services.notifier import NotificationService, send_jongga_notification


def _set_notifier_env(monkeypatch) -> None:
    monkeypatch.setenv("NOTIFICATION_ENABLED", "true")
    monkeypatch.setenv("NOTIFICATION_CHANNELS", "discord,telegram,slack,email")
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://example.com/discord")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "bot-token")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "chat-id")
    monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://example.com/slack")
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_PORT", "587")
    monkeypatch.setenv("SMTP_USER", "sender@example.com")
    monkeypatch.setenv("SMTP_PASSWORD", "secret")
    monkeypatch.setenv("EMAIL_RECIPIENTS", "a@example.com,b@example.com")


def test_format_jongga_message_filters_d_grade_and_sorts(monkeypatch):
    _set_notifier_env(monkeypatch)
    service = NotificationService()
    signals = [
        {"name": "디등급", "code": "000001", "grade": "D", "score": {"total": 99}},
        {"name": "A저점수", "code": "000002", "grade": "A", "score": {"total": 10}, "market": "KOSPI"},
        {"name": "S최우선", "code": "000003", "grade": "S", "score": {"total": 5}, "market": "KOSDAQ"},
        {"name": "A고점수", "code": "000004", "grade": "A", "score": {"total": 20}, "market": "KOSPI"},
    ]

    message = service.format_jongga_message(signals, "2026-02-21")

    assert "선별된 신호: 3개 (D등급 1개 제외)" in message
    assert "1. [KOSDAQ] S최우선 (000003) - S등급 5점" in message
    assert "2. [KOSPI] A고점수 (000004) - A등급 20점" in message
    assert "3. [KOSPI] A저점수 (000002) - A등급 10점" in message
    assert "디등급 (000001)" not in message


def test_send_all_dispatches_channels_and_ignores_unknown(monkeypatch):
    _set_notifier_env(monkeypatch)
    monkeypatch.setenv("NOTIFICATION_CHANNELS", "discord,telegram,slack,email,unknown")
    service = NotificationService()

    calls: list[tuple[str, str]] = []
    monkeypatch.setattr(service, "format_jongga_message", lambda _signals, _date: "formatted")
    monkeypatch.setattr(
        service,
        "send_discord",
        lambda message: calls.append(("discord", message)) or True,
    )
    monkeypatch.setattr(
        service,
        "send_telegram",
        lambda message: calls.append(("telegram", message)) or True,
    )
    monkeypatch.setattr(
        service,
        "send_slack",
        lambda message: calls.append(("slack", message)) or True,
    )
    monkeypatch.setattr(
        service,
        "send_email",
        lambda _message, date_str=None: calls.append(("email", str(date_str))) or True,
    )

    result = service.send_all([{"grade": "A"}], "2026-02-21")

    assert result == {
        "discord": True,
        "telegram": True,
        "slack": True,
        "email": True,
    }
    assert calls == [
        ("discord", "formatted"),
        ("telegram", "formatted"),
        ("slack", "formatted"),
        ("email", "2026-02-21"),
    ]


def test_send_all_returns_empty_when_disabled_or_signal_empty(monkeypatch):
    _set_notifier_env(monkeypatch)
    monkeypatch.setenv("NOTIFICATION_ENABLED", "false")
    disabled_service = NotificationService()
    assert disabled_service.send_all([{"grade": "A"}], "2026-02-21") == {}

    monkeypatch.setenv("NOTIFICATION_ENABLED", "true")
    empty_service = NotificationService()
    monkeypatch.setattr(
        empty_service,
        "format_jongga_message",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("should not be called")),
    )
    assert empty_service.send_all([], "2026-02-21") == {}


def test_send_methods_delegate_to_channel_helpers(monkeypatch):
    _set_notifier_env(monkeypatch)
    service = NotificationService()

    captured: dict[str, tuple[str, str | None]] = {}
    def _fake_discord(webhook_url, message, logger):
        _ = logger
        captured["discord"] = (webhook_url, message)
        return True

    def _fake_telegram(bot_token, chat_id, message, logger):
        _ = logger
        captured["telegram"] = (f"{bot_token}:{chat_id}", message)
        return True

    def _fake_slack(webhook_url, message, logger):
        _ = logger
        captured["slack"] = (webhook_url, message)
        return True

    def _fake_email(
        smtp_host,
        smtp_port,
        smtp_user,
        smtp_password,
        email_recipients,
        message,
        logger,
        date_str=None,
    ):
        _ = smtp_user, smtp_password, email_recipients, message, logger
        captured["email"] = (f"{smtp_host}:{smtp_port}", date_str)
        return True

    monkeypatch.setattr(notifier_module, "send_discord_message", _fake_discord)
    monkeypatch.setattr(notifier_module, "send_telegram_message", _fake_telegram)
    monkeypatch.setattr(notifier_module, "send_slack_message", _fake_slack)
    monkeypatch.setattr(notifier_module, "send_email_message", _fake_email)

    assert service.send_discord("hello") is True
    assert service.send_telegram("hello") is True
    assert service.send_slack("hello") is True
    assert service.send_email("hello", "2026-02-21") is True

    assert captured["discord"] == ("https://example.com/discord", "hello")
    assert captured["telegram"] == ("bot-token:chat-id", "hello")
    assert captured["slack"] == ("https://example.com/slack", "hello")
    assert captured["email"] == ("smtp.example.com:587", "2026-02-21")


def test_send_jongga_notification_uses_notification_service(monkeypatch):
    class _DummyService:
        def send_all(self, signals, date_str=None):
            return {"count": len(signals), "date": date_str}

    monkeypatch.setattr(notifier_module, "NotificationService", _DummyService)

    result = send_jongga_notification([{"grade": "A"}, {"grade": "B"}], "2026-02-21")

    assert result == {"count": 2, "date": "2026-02-21"}
