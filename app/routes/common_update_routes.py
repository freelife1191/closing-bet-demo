#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Common Update/System Routes
"""

from __future__ import annotations

import os
from collections.abc import Callable
from threading import Thread

from flask import jsonify, request

from app.routes.common_route_context import CommonRouteContext
from services.common_data_status_service import build_common_data_status_payload
from services.common_env_service import (
    read_masked_env_vars,
    reset_sensitive_env_and_user_data,
    resolve_data_dir,
    resolve_env_path,
    update_env_file,
)


_ACTIVITY_LOGGER = None


DATA_FILES_TO_CHECK = [
    {
        "name": "Daily Prices",
        "path": "data/daily_prices.csv",
        "link": "/dashboard/kr/closing-bet",
        "menu": "Closing Bet",
    },
    {
        "name": "Institutional Trend",
        "path": "data/all_institutional_trend_data.csv",
        "link": "/dashboard/kr/vcp",
        "menu": "VCP Signals",
    },
    {
        "name": "AI Analysis",
        "path": "data/kr_ai_analysis.json",
        "link": "/dashboard/kr/vcp",
        "menu": "VCP Signals",
    },
    {
        "name": "VCP Signals",
        "path": "data/signals_log.csv",
        "link": "/dashboard/kr/vcp",
        "menu": "VCP Signals",
    },
    {
        "name": "AI Jongga V2",
        "path": "data/jongga_v2_latest.json",
        "link": "/dashboard/kr/closing-bet",
        "menu": "Closing Bet",
    },
    {
        "name": "Market Gate",
        "path": "data/market_gate.json",
        "link": "/dashboard/kr",
        "menu": "Market Overview",
    },
]


def _build_error_payload(error: Exception) -> dict[str, str]:
    return {"error": str(error)}


def _execute_update_route(
    *,
    handler: Callable[[], object],
    ctx: CommonRouteContext,
    error_label: str,
    error_payload_builder: Callable[[Exception], dict[str, str]] = _build_error_payload,
) -> object:
    try:
        return handler()
    except Exception as error:
        ctx.logger.error(f"{error_label}: {error}")
        return jsonify(error_payload_builder(error)), 500


def _resolve_activity_logger():
    global _ACTIVITY_LOGGER
    if _ACTIVITY_LOGGER is None:
        from services.activity_logger import activity_logger

        _ACTIVITY_LOGGER = activity_logger
    return _ACTIVITY_LOGGER


def _resolve_request_ip() -> str | None:
    real_ip = request.headers.get("X-Forwarded-For", request.remote_addr)
    if real_ip and "," in real_ip:
        return real_ip.split(",")[0].strip()
    return real_ip


def _register_update_control_routes(common_bp, ctx: CommonRouteContext) -> None:
    @common_bp.route("/system/update-status")
    def get_update_status():
        """업데이트 상태만 조회 (가벼운 폴링용)."""
        with ctx.update_lock:
            status = ctx.load_update_status()
            status["_debug_path"] = ctx.update_status_file
            status["_debug_exists"] = os.path.exists(ctx.update_status_file)
            return jsonify(status)

    @common_bp.route("/system/start-update", methods=["POST"])
    def api_start_update():
        """업데이트 시작 (백그라운드 실행)."""
        data = request.get_json() or {}
        items_list = data.get("items", [])
        target_date = data.get("target_date")
        force = data.get("force", False)

        current_status = ctx.load_update_status()
        if current_status.get("isRunning", False):
            return jsonify({"status": "error", "message": "Already running"}), 400

        ctx.start_update(items_list)

        thread = Thread(
            target=ctx.run_background_update,
            args=(target_date, items_list, force),
            daemon=True,
        )
        thread.start()
        return jsonify({"status": "ok"})

    @common_bp.route("/system/update-item-status", methods=["POST"])
    def api_update_item_status():
        """아이템 상태 업데이트."""
        data = request.get_json() or {}
        name = data.get("name")
        status = data.get("status")
        if name and status:
            ctx.update_item_status(name, status)
        return jsonify({"status": "ok"})

    @common_bp.route("/system/finish-update", methods=["POST"])
    def api_finish_update():
        """업데이트 완료."""
        ctx.finish_update()
        return jsonify({"status": "ok"})

    @common_bp.route("/system/stop-update", methods=["POST"])
    def api_stop_update():
        """업데이트 중단 요청."""
        ctx.stop_update()
        return jsonify({"status": "stopped"})


def _register_event_log_route(common_bp, ctx: CommonRouteContext) -> None:
    @common_bp.route("/system/log-event", methods=["POST"])
    def api_log_event():
        """프론트엔드 이벤트 로깅 (Login, Profile Update 등)."""
        def _handler():
            data = request.get_json() or {}
            action = data.get("action", "FRONTEND_EVENT")
            details = data.get("details", {})

            user_email = request.headers.get("X-User-Email")
            session_id = request.headers.get("X-Session-Id")
            user_id = user_email if (user_email and user_email != "user@example.com") else session_id

            activity_logger = _resolve_activity_logger()

            if "session_id" not in details and session_id:
                details["session_id"] = session_id

            real_ip = _resolve_request_ip()

            activity_logger.log_action(
                user_id=user_id,
                action=action,
                details=details,
                ip_address=real_ip,
            )
            return jsonify({"status": "ok"})

        return _execute_update_route(
            handler=_handler,
            ctx=ctx,
            error_label="Event Log Error",
        )


def _register_data_status_route(common_bp, ctx: CommonRouteContext) -> None:
    @common_bp.route("/system/data-status")
    def get_data_status():
        """데이터 파일 상태 조회."""
        payload = build_common_data_status_payload(
            data_files_to_check=DATA_FILES_TO_CHECK,
            load_update_status=ctx.load_update_status,
            logger=ctx.logger,
        )
        return jsonify(payload)


def _register_manage_env_route(common_bp, ctx: CommonRouteContext) -> None:
    @common_bp.route("/system/env", methods=["GET", "POST", "DELETE"])
    def manage_env():
        """환경 변수 관리 (읽기 및 쓰기)."""
        if request.method == "GET":
            def _handle_get():
                return jsonify(read_masked_env_vars(resolve_env_path()))

            return _execute_update_route(
                handler=_handle_get,
                ctx=ctx,
                error_label="Error reading .env",
            )

        if request.method == "POST":
            def _handle_post():
                data = request.get_json() or {}
                if not data:
                    return jsonify({"status": "ok"})
                update_env_file(resolve_env_path(), data, os.environ)
                return jsonify({"status": "ok"})

            return _execute_update_route(
                handler=_handle_post,
                ctx=ctx,
                error_label="Error updating .env",
            )

        def _handle_delete():
            reset_sensitive_env_and_user_data(
                env_path=resolve_env_path(),
                data_dir=resolve_data_dir(),
                environ=os.environ,
                logger=ctx.logger,
            )
            return jsonify(
                {
                    "status": "ok",
                    "message": "All sensitive data and user history types wiped.",
                }
            )

        return _execute_update_route(
            handler=_handle_delete,
            ctx=ctx,
            error_label="Error resetting .env",
        )


def register_common_update_routes(common_bp, ctx: CommonRouteContext) -> None:
    """시스템/업데이트 관련 라우트를 등록한다."""
    _register_update_control_routes(common_bp, ctx)
    _register_event_log_route(common_bp, ctx)
    _register_data_status_route(common_bp, ctx)
    _register_manage_env_route(common_bp, ctx)
