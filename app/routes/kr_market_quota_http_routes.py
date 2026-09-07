#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KR Market Quota HTTP Routes

쿼터 관련 엔드포인트 등록을 담당한다.
"""

from __future__ import annotations

from typing import Any, Callable

from flask import g, jsonify, request

from app.routes.route_execution import execute_json_route as _execute_json_route
from services.kr_market_quota_service import (
    build_quota_info_payload,
    resolve_quota_usage_key,
)


def register_quota_routes(
    kr_bp: Any,
    *,
    logger: Any,
    max_free_usage: int,
    get_user_usage_fn: Callable[[str | None], int],
    recharge_usage_fn: Callable[[str | None, int], tuple[int, bool]],
) -> None:
    @kr_bp.route("/user/quota")
    def get_user_quota_info():
        def _handler():
            from engine.config import app_config

            # 신원은 before_request 가 확정한다. 종전에는 쿼리 파라미터로도 받았는데,
            # 그러면 헤더를 막아도 URL 한 줄로 남의 쿼터를 조회할 수 있었다.
            usage_key = resolve_quota_usage_key(
                user_email=g.get("user_email"),
                session_id=g.get("session_id"),
            )
            payload = build_quota_info_payload(
                usage_key=usage_key,
                max_free_usage=max_free_usage,
                get_user_usage_fn=get_user_usage_fn,
                server_key_available=bool(
                    (app_config.GOOGLE_GENAI_USE_VERTEXAI and app_config.GOOGLE_CLOUD_PROJECT)
                    or app_config.ZAI_API_KEY
                ),
            )
            return jsonify(payload)

        return _execute_json_route(
            handler=_handler,
            logger=logger,
            error_label="Get user quota info error",
        )

    @kr_bp.route("/user/quota/recharge", methods=["POST"])
    def recharge_user_quota():
        def _handler():
            # 충전은 익명에게 열지 않는다. 익명 ID 는 브라우저가 지우면 새로 발급되므로
            # 하루 1회 제한이 성립하지 않는다.
            usage_key = g.get("user_email")

            if not usage_key:
                return jsonify({"error": "로그인이 필요합니다."}), 401

            new_usage, recharged = recharge_usage_fn(usage_key, 5)
            remaining = max(0, max_free_usage - new_usage)
            if not recharged:
                return (
                    jsonify(
                        {
                            "status": "error",
                            "code": "ALREADY_RECHARGED_TODAY",
                            "usage": new_usage,
                            "limit": max_free_usage,
                            "remaining": remaining,
                            "message": f"충전은 하루 한 번만 가능합니다. (남은 횟수: {remaining}회)",
                        }
                    ),
                    429,
                )
            return jsonify(
                {
                    "status": "success",
                    "usage": new_usage,
                    "limit": max_free_usage,
                    "remaining": remaining,
                    "message": f"5회 충전 완료! (남은 횟수: {remaining}회)",
                }
            )

        return _execute_json_route(
            handler=_handler,
            logger=logger,
            error_label="Recharge quota error",
        )
