#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Common Notification Routes
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from flask import jsonify, request

from app.routes.common_route_context import CommonRouteContext


@dataclass(frozen=True)
class _NotificationPlatformSpec:
    """플랫폼별 발송 전 검증/전송 핸들러 정의."""

    sender_attr: str
    config_validator: Callable[[object], bool]
    missing_config_message: str


def _has_discord_config(messenger: object) -> bool:
    return bool(getattr(messenger, "discord_url", None))


def _has_telegram_config(messenger: object) -> bool:
    return bool(getattr(messenger, "telegram_token", None)) and bool(
        getattr(messenger, "telegram_chat_id", None)
    )


def _has_email_config(messenger: object) -> bool:
    return bool(getattr(messenger, "smtp_user", None))


_PLATFORM_SPECS: dict[str, _NotificationPlatformSpec] = {
    "discord": _NotificationPlatformSpec(
        sender_attr="_send_discord",
        config_validator=_has_discord_config,
        missing_config_message="Discord Webhook URL not set in server env",
    ),
    "telegram": _NotificationPlatformSpec(
        sender_attr="_send_telegram",
        config_validator=_has_telegram_config,
        missing_config_message="Telegram Token or Chat ID not set",
    ),
    "email": _NotificationPlatformSpec(
        sender_attr="_send_email",
        config_validator=_has_email_config,
        missing_config_message="SMTP settings not configured",
    ),
}


def _build_test_notification_data(platform: str) -> dict:
    return {
        "title": f"[Test] {platform.upper()} Notification",
        "gate_info": "System Status: Online",
        "summary_title": "테스트 발송입니다",
        "summary_desc": "설정된 정보로 알림이 정상적으로 수신되는지 확인하세요.",
        "signals": [
            {
                "index": 1,
                "name": "테스트종목",
                "code": "005930",
                "market_icon": "🔵",
                "grade": "A",
                "score": 85.5,
                "change_pct": 1.2,
                "volume_ratio": 2.5,
                "trading_value": 5_000_000_000,
                "f_buy": 1_000_000_000,
                "i_buy": 500_000_000,
                "entry": 70_000,
                "target": 75_000,
                "stop": 68_000,
                "ai_reason": "AI 분석 테스트 메시지입니다. 시스템이 정상 동작 중입니다.",
            }
        ],
    }


def _build_error_response(message: str, status_code: int) -> tuple[object, int]:
    return jsonify({"status": "error", "message": message}), status_code


def _execute_notification_route(
    *,
    handler: Callable[[], object],
    ctx: CommonRouteContext,
    error_label: str,
) -> object:
    try:
        return handler()
    except Exception as error:
        ctx.logger.error(f"{error_label}: {error}")
        return _build_error_response(str(error), 500)


def _send_platform_test_notification(
    platform: str,
    messenger: object,
    test_data: dict,
) -> tuple[object, int] | None:
    spec = _PLATFORM_SPECS.get(platform)
    if spec is None:
        return _build_error_response(f"Unknown platform: {platform}", 400)
    if not spec.config_validator(messenger):
        return _build_error_response(spec.missing_config_message, 400)

    sender = getattr(messenger, spec.sender_attr)
    sender(test_data)
    return None


def register_common_notification_routes(common_bp, ctx: CommonRouteContext) -> None:
    """알림 테스트 발송 라우트를 등록한다."""

    @common_bp.route("/notification/send", methods=["POST"])
    def send_test_notification():
        """알림 테스트 발송."""
        def _handler():
            data = request.get_json() or {}
            platform = data.get("platform")
            if not platform:
                return _build_error_response("Platform not specified", 400)

            from engine.messenger import Messenger

            messenger = Messenger()
            test_data = _build_test_notification_data(platform)
            error_response = _send_platform_test_notification(platform, messenger, test_data)
            if error_response is not None:
                return error_response

            return jsonify(
                {
                    "status": "success",
                    "message": f"{platform} test message sent",
                }
            )

        return _execute_notification_route(
            handler=_handler,
            ctx=ctx,
            error_label="Test notification failed",
        )
