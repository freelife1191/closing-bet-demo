#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Common Notification Routes
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from flask import g, jsonify, request

from app.routes.common_route_context import CommonRouteContext
from services.admin_helpers import is_admin_email


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
    spec: _NotificationPlatformSpec,
    messenger: object,
    test_data: dict,
) -> tuple[object, int] | None:
    if not spec.config_validator(messenger):
        return _build_error_response(spec.missing_config_message, 400)

    sender = getattr(messenger, spec.sender_attr)
    sender(test_data)
    return None


def register_common_notification_routes(common_bp, ctx: CommonRouteContext) -> None:
    """알림 테스트 발송 라우트를 등록한다."""

    @common_bp.route("/notification/send", methods=["POST"])
    def send_test_notification():
        """알림 테스트 발송. 관리자로 확인된 요청만 처리한다."""
        # 발송에 쓰는 것은 서버 .env 에 저장된 운영자의 봇 토큰·웹훅·SMTP 계정이고
        # 도착지도 운영자가 정한 채널이다. 게이트가 없으면 이 경로 자체가 아무나 쓸 수
        # 있는 스팸 통로가 된다. 화면 쪽 `handleTestNotification` 의 `if (!isAdmin)` 은
        # 버튼을 감출 뿐이고 엔드포인트를 닫지 못한다.
        #
        # `g.user_email` 은 `frontend/src/proxy.ts` 가 NextAuth 세션을 확인해 서명한
        # 헤더를 `app/__init__.py` 의 `before_request` 가 검증한 값이다. 브라우저는
        # INTERNAL_IDENTITY_SECRET 을 모르므로 헤더를 지어내도 여기까지 오지 못하고,
        # 서명이 없으면 None 이라 관리자 판정에서 떨어진다. 다만 이 게이트의 강도는
        # 그 비밀의 기밀성과 Flask 포트의 접근 통제에 묶여 있다. 근거와 남은 과제는
        # services/identity_helpers.py 의 verify_identity_header ponytail 주석에 있다.
        if not is_admin_email(g.get("user_email")):
            return _build_error_response("Forbidden", 403)

        def _handler():
            # `silent=True` 를 붙이지 않는다. 이 저장소의 다른 라우트는 대부분 그것을
            # 쓰지만, 여기서는 그 차이가 CSRF 를 막는다. 신원이 NextAuth 쿠키에서
            # 파생되므로 관리자 브라우저를 지나는 교차 사이트 POST 는 proxy 가 서명해
            # 준다. preflight 를 피할 수 있는 유일한 형태인 폼 인코딩 요청을 세우는
            # 것이 `get_json()` 의 415 다. 일관성을 맞춘다며 이 한 줄을 고치면 그
            # 경로가 열린다. 전체 대책은 `[INFRA-040]` 이다.
            data = request.get_json() or {}
            platform = data.get("platform")
            if not platform:
                return _build_error_response("Platform not specified", 400)

            # 플랫폼 판정을 Messenger 생성보다 앞에 둔다. 뒤에 두면 알 수 없는
            # 플랫폼 요청 하나에도 서버 자격 증명으로 Messenger 가 세워진다. 지금은
            # 그 생성자가 네트워크를 타지 않지만, 연결 확인이 한 줄 들어오는 순간
            # 400 으로 끝날 요청이 운영 채널을 건드리게 된다.
            spec = _PLATFORM_SPECS.get(platform)
            if spec is None:
                return _build_error_response(f"Unknown platform: {platform}", 400)

            from engine.messenger import Messenger

            messenger = Messenger()
            test_data = _build_test_notification_data(platform)
            error_response = _send_platform_test_notification(spec, messenger, test_data)
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
