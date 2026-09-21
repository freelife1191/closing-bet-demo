#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Common Update/System Routes
"""

from __future__ import annotations

import os
from collections.abc import Callable
from threading import Thread

from flask import g, jsonify, request
from werkzeug.exceptions import HTTPException

from app.routes.common_route_context import CommonRouteContext
from app.routes.route_guards import require_admin
from services.admin_helpers import verify_admin_api_token
from services.common_data_status_service import build_common_data_status_payload
from services.common_env_service import (
    read_masked_env_vars,
    resolve_env_path,
    update_env_file,
)
from services.scheduler_runtime_status_service import get_scheduler_runtime_status


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
    # 원인은 호출부에서 기록하며 외부에는 경로·예외 내용을 보내지 않는다.
    return {"error": "Internal Server Error"}


def _execute_update_route(
    *,
    handler: Callable[[], object],
    ctx: CommonRouteContext,
    error_label: str,
    error_payload_builder: Callable[[Exception], dict[str, str]] = _build_error_payload,
) -> object:
    try:
        return handler()
    except HTTPException as error:
        ctx.logger.warning("%s: %s", error_label, type(error).__name__)
        raise
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
    """프록시 전달 헤더 대신 Flask가 직접 관측한 연결 상대를 감사한다."""
    return request.remote_addr


def _register_update_control_routes(common_bp, ctx: CommonRouteContext) -> None:
    @common_bp.route("/system/update-status")
    def get_update_status():
        """업데이트 상태만 조회 (가벼운 폴링용)."""
        with ctx.update_lock:
            try:
                loaded_status = ctx.load_update_status(deep_copy=False)
            except TypeError:
                loaded_status = ctx.load_update_status()

            # 상태 폴링 응답에서 파생 필드를 주입하므로 원본 캐시 객체를 직접 변경하지 않는다.
            status = dict(loaded_status) if isinstance(loaded_status, dict) else {}
            scheduler_data_dir = os.path.dirname(ctx.update_status_file) or "data"
            scheduler_status = get_scheduler_runtime_status(data_dir=scheduler_data_dir)
            if scheduler_status.get("is_data_scheduling_running"):
                status["isRunning"] = True
                status["currentItem"] = "전체 스케쥴링 작업 진행 중인 상태"
            status["_debug_path"] = ctx.update_status_file
            status["_debug_exists"] = os.path.exists(ctx.update_status_file)
            return jsonify(status)

    @common_bp.route("/system/start-update", methods=["POST"])
    @require_admin
    def api_start_update():
        """업데이트 시작 (백그라운드 실행)."""
        data = request.get_json() or {}
        items_list = data.get("items", [])
        target_date = data.get("target_date")
        force = data.get("force", False)

        try:
            current_status = ctx.load_update_status(deep_copy=False)
        except TypeError:
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
    @require_admin
    def api_update_item_status():
        """아이템 상태 업데이트."""
        data = request.get_json() or {}
        name = data.get("name")
        status = data.get("status")
        if name and status:
            ctx.update_item_status(name, status)
        return jsonify({"status": "ok"})

    @common_bp.route("/system/finish-update", methods=["POST"])
    @require_admin
    def api_finish_update():
        """업데이트 완료."""
        ctx.finish_update()
        return jsonify({"status": "ok"})

    @common_bp.route("/system/stop-update", methods=["POST"])
    @require_admin
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

            # g 의 두 값은 검증을 거쳤다. 헤더를 그대로 읽으면 활동 로그의 사용자 칸을
            # 아무 문자열로나 채울 수 있다.
            session_id = g.get("session_id")
            user_id = g.get("user_email") or session_id

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
    @common_bp.route("/system/env", methods=["GET", "POST"])
    def manage_env():
        """환경 변수 관리 (읽기 및 쓰기). 관리자 토큰이 있는 요청만 처리한다."""
        # 이 토큰은 Next.js 라우트 핸들러가 NextAuth 세션을 확인한 뒤에만 붙인다.
        # 브라우저는 값을 알 수 없으므로 헤더를 지어내도 통과하지 못한다.
        # Next 의 rewrite 예외만으로는 부족하다. `/api/system%2Fenv` 처럼 인코딩한
        # 경로는 그 부정 전방탐색을 빠져나가 Flask 로 넘어오고, WSGI 가 PATH_INFO 를
        # 디코딩해 이 라우트에 닿는다. 그때 요청을 세우는 것은 이 검사뿐이다.
        if not verify_admin_api_token(request.headers.get("X-Admin-Token")):
            return jsonify({"error": "Forbidden"}), 403

        if request.method == "GET":
            def _handle_get():
                return jsonify(read_masked_env_vars(resolve_env_path()))

            return _execute_update_route(
                handler=_handle_get,
                ctx=ctx,
                error_label="Error reading .env",
            )

        def _handle_post():
            try:
                data = request.get_json()
            except HTTPException as error:
                ctx.logger.warning("Invalid env JSON request: %s", type(error).__name__)
                return jsonify({"status": "error", "message": "Invalid JSON request"}), error.code
            if not isinstance(data, dict):
                return jsonify({"status": "error", "message": "Expected a JSON object"}), 400
            try:
                result = update_env_file(resolve_env_path(), data, os.environ)
            except Exception as error:
                ctx.logger.error("Error updating .env: %s", type(error).__name__)
                return jsonify({"status": "error", "message": "Settings could not be saved"}), 500
            if result["rejected"]:
                return jsonify({"status": "error", **result,
                                "message": "Some settings were rejected; accepted settings were saved."}), 400
            return jsonify({"status": "ok", **result})

        return _execute_update_route(
            handler=_handle_post,
            ctx=ctx,
            error_label="Error updating .env",
        )


def register_common_update_routes(common_bp, ctx: CommonRouteContext) -> None:
    """시스템/업데이트 관련 라우트를 등록한다."""
    _register_update_control_routes(common_bp, ctx)
    _register_event_log_route(common_bp, ctx)
    _register_data_status_route(common_bp, ctx)
    _register_manage_env_route(common_bp, ctx)
