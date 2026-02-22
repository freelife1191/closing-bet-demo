#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KR Market Chatbot HTTP Routes

챗봇 관련 엔드포인트 등록을 담당한다.
"""

from __future__ import annotations

from typing import Any, Callable

from flask import Response, jsonify, request, stream_with_context

from app.routes.route_execution import execute_json_route as _execute_json_route
from services.kr_market_chatbot_service import (
    check_chatbot_quota_guard,
    detect_chatbot_device_type,
    extract_chatbot_client_ip,
    handle_chatbot_history_request,
    handle_chatbot_profile_request,
    handle_chatbot_sessions_request,
    parse_chatbot_request_payload,
    parse_chatbot_watchlist_query,
    resolve_chatbot_owner_id,
    resolve_chatbot_usage_context,
    stream_chatbot_response,
)

def _build_chatbot_activity_logger(logger: Any) -> Callable[..., None]:
    activity_logger_instance: Any | None = None
    try:
        from services.activity_logger import activity_logger as _activity_logger

        activity_logger_instance = _activity_logger
    except Exception as error:
        logger.warning(f"Activity logger unavailable: {error}")

    def _log_chatbot_activity(
        usage_key: str | None,
        session_id: str | None,
        model_name: str | None,
        message: str,
        full_response: str,
        usage_metadata: dict[str, Any],
        has_files: bool,
    ) -> None:
        if activity_logger_instance is None:
            return

        try:
            ua_string = request.user_agent.string or ""
            activity_logger_instance.log_action(
                user_id=usage_key,
                action="CHAT_MESSAGE",
                details={
                    "session_id": session_id,
                    "model": model_name,
                    "user_message": message[:2000] if message else "",
                    "bot_response": full_response[:2000] if full_response else "",
                    "token_usage": usage_metadata,
                    "has_files": has_files,
                    "device": detect_chatbot_device_type(
                        platform=request.user_agent.platform,
                        ua_string=ua_string,
                    ),
                    "user_agent": ua_string[:150],
                },
                ip_address=extract_chatbot_client_ip(
                    forwarded_for=request.headers.get("X-Forwarded-For"),
                    remote_addr=request.remote_addr,
                ),
            )
        except Exception as e:
            logger.error(f"[{usage_key}] Chat log error: {e}")

    return _log_chatbot_activity


def _register_chatbot_welcome_session_routes(kr_bp: Any, *, logger: Any) -> None:
    @kr_bp.route("/chatbot/welcome", methods=["GET"])
    def kr_chatbot_welcome():
        def _handler():
            from chatbot import get_chatbot

            bot = get_chatbot()
            msg = bot.get_welcome_message()
            return jsonify({"message": msg})

        return _execute_json_route(handler=_handler, logger=logger, error_label="Chatbot welcome error")

    @kr_bp.route("/chatbot/sessions", methods=["GET", "POST"])
    def kr_chatbot_sessions():
        def _handler():
            from chatbot import get_chatbot

            bot = get_chatbot()
            owner_id = resolve_chatbot_owner_id(
                user_email=request.headers.get("X-User-Email"),
                session_id_header=request.headers.get("X-Session-Id"),
            )
            req_data = request.get_json(silent=True) or {}
            status_code, payload = handle_chatbot_sessions_request(
                bot=bot,
                method=request.method,
                owner_id=owner_id,
                req_data=req_data,
            )
            return jsonify(payload), int(status_code)

        return _execute_json_route(handler=_handler, logger=logger, error_label="Chatbot sessions error")


def _register_chatbot_stream_route(
    kr_bp: Any,
    *,
    logger: Any,
    max_free_usage: int,
    get_user_usage_fn: Callable[[str | None], int],
    increment_user_usage_fn: Callable[[str | None], int],
    log_chatbot_activity: Callable[..., None],
) -> None:
    @kr_bp.route("/chatbot", methods=["POST"])
    def kr_chatbot():
        usage_key = None
        try:
            from chatbot import get_chatbot
            from engine.config import app_config

            context = resolve_chatbot_usage_context(
                user_api_key_header=request.headers.get("X-Gemini-Key"),
                user_email_header=request.headers.get("X-User-Email"),
                session_id_header=request.headers.get("X-Session-Id"),
            )
            user_api_key = context["user_api_key"]
            usage_key = context["usage_key"]

            use_free_tier, quota_error = check_chatbot_quota_guard(
                user_api_key=user_api_key,
                usage_key=usage_key,
                max_free_usage=max_free_usage,
                get_user_usage_fn=get_user_usage_fn,
                server_key_available=bool(app_config.GOOGLE_API_KEY or app_config.ZAI_API_KEY),
            )
            if quota_error:
                status_code, payload = quota_error
                return jsonify(payload), int(status_code)

            payload = parse_chatbot_request_payload(
                content_type=request.content_type,
                form_data=request.form,
                request_files=request.files,
                request_json=request.get_json(silent=True),
                default_session_id=context["header_session_id"],
                logger=logger,
            )
            bot = get_chatbot()

            def _log_activity(
                full_response: str,
                usage_metadata: dict[str, Any],
                stream_has_error: bool,
            ) -> None:
                del stream_has_error
                log_chatbot_activity(
                    usage_key=usage_key,
                    session_id=payload["session_id"],
                    model_name=payload["model_name"],
                    message=payload["message"],
                    full_response=full_response,
                    usage_metadata=usage_metadata,
                    has_files=bool(payload["files"]),
                )

            response = Response(
                stream_with_context(
                    stream_chatbot_response(
                        bot=bot,
                        payload=payload,
                        user_api_key=user_api_key,
                        usage_key=usage_key,
                        use_free_tier=use_free_tier,
                        logger=logger,
                        increment_user_usage_fn=increment_user_usage_fn,
                        log_activity_fn=_log_activity,
                    )
                ),
                content_type="text/event-stream",
            )
            response.headers["Cache-Control"] = "no-cache, no-transform"
            response.headers["X-Accel-Buffering"] = "no"
            response.headers["Connection"] = "keep-alive"
            return response
        except Exception as e:
            logger.error(f"[{usage_key or 'anonymous'}] Chatbot API Error: {e}")
            return jsonify({"error": str(e)}), 500


def _register_chatbot_core_routes(
    kr_bp: Any,
    *,
    logger: Any,
    max_free_usage: int,
    get_user_usage_fn: Callable[[str | None], int],
    increment_user_usage_fn: Callable[[str | None], int],
) -> None:
    log_chatbot_activity = _build_chatbot_activity_logger(logger)
    _register_chatbot_welcome_session_routes(kr_bp, logger=logger)
    _register_chatbot_stream_route(
        kr_bp,
        logger=logger,
        max_free_usage=max_free_usage,
        get_user_usage_fn=get_user_usage_fn,
        increment_user_usage_fn=increment_user_usage_fn,
        log_chatbot_activity=log_chatbot_activity,
    )


def _register_chatbot_meta_routes(kr_bp: Any, *, logger: Any) -> None:
    @kr_bp.route("/chatbot/models", methods=["GET"])
    def kr_chatbot_models():
        def _handler():
            from chatbot import get_chatbot

            bot = get_chatbot()
            models = bot.get_available_models()
            current = bot.current_model_name
            return jsonify({"models": models, "current": current})

        return _execute_json_route(handler=_handler, logger=logger, error_label="Chatbot models error")

    @kr_bp.route("/chatbot/suggestions", methods=["GET"])
    def kr_chatbot_suggestions():
        def _handler():
            from chatbot import get_chatbot

            bot = get_chatbot()
            watchlist = parse_chatbot_watchlist_query(request.args.get("watchlist"))
            persona = request.args.get("persona")
            suggestions = bot.get_daily_suggestions(watchlist=watchlist, persona=persona)
            return jsonify({"suggestions": suggestions})

        return _execute_json_route(handler=_handler, logger=logger, error_label="Suggestions API Error")

    @kr_bp.route("/chatbot/history", methods=["GET", "DELETE"])
    def kr_chatbot_history():
        def _handler():
            from chatbot import get_chatbot

            bot = get_chatbot()
            status_code, payload = handle_chatbot_history_request(
                bot=bot,
                method=request.method,
                session_id=request.args.get("session_id"),
                msg_index_str=request.args.get("index"),
            )
            return jsonify(payload), int(status_code)

        return _execute_json_route(handler=_handler, logger=logger, error_label="Chatbot history error")

    @kr_bp.route("/chatbot/profile", methods=["GET", "POST"])
    def kr_chatbot_profile():
        def _handler():
            from chatbot import get_chatbot

            bot = get_chatbot()
            req_data = request.get_json(silent=True) or {}
            status_code, payload = handle_chatbot_profile_request(
                bot=bot,
                method=request.method,
                req_data=req_data,
            )
            return jsonify(payload), int(status_code)

        return _execute_json_route(handler=_handler, logger=logger, error_label="Chatbot profile error")


def register_chatbot_routes(
    kr_bp: Any,
    *,
    logger: Any,
    max_free_usage: int,
    get_user_usage_fn: Callable[[str | None], int],
    increment_user_usage_fn: Callable[[str | None], int],
) -> None:
    _register_chatbot_core_routes(
        kr_bp,
        logger=logger,
        max_free_usage=max_free_usage,
        get_user_usage_fn=get_user_usage_fn,
        increment_user_usage_fn=increment_user_usage_fn,
    )
    _register_chatbot_meta_routes(kr_bp, logger=logger)
