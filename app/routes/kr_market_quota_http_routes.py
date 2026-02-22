#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KR Market Quota HTTP Routes

쿼터 관련 엔드포인트 등록을 담당한다.
"""

from __future__ import annotations

from typing import Any, Callable

from flask import jsonify, request

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
    recharge_usage_fn: Callable[[str | None, int], int],
) -> None:
    @kr_bp.route("/user/quota")
    def get_user_quota_info():
        def _handler():
            from engine.config import app_config

            user_email = request.args.get("email") or request.headers.get("X-User-Email")
            session_id = request.args.get("session_id") or request.headers.get("X-Session-Id")
            usage_key = resolve_quota_usage_key(user_email=user_email, session_id=session_id)
            payload = build_quota_info_payload(
                usage_key=usage_key,
                max_free_usage=max_free_usage,
                get_user_usage_fn=get_user_usage_fn,
                server_key_available=bool(app_config.GOOGLE_API_KEY or app_config.ZAI_API_KEY),
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
            data = request.get_json() or {}
            user_email = data.get("email") or request.headers.get("X-User-Email")
            session_id = data.get("session_id") or request.headers.get("X-Session-Id")
            usage_key = resolve_quota_usage_key(user_email=user_email, session_id=session_id)

            if not usage_key:
                return jsonify({"error": "세션 정보가 없습니다."}), 400

            new_usage = int(recharge_usage_fn(usage_key, 5))
            remaining = max(0, max_free_usage - new_usage)
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
