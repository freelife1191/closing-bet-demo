#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KR Market Chatbot Request Helpers

챗봇 요청/세션/프로필 관련 순수 헬퍼를 제공한다.
"""

from __future__ import annotations

import json
import logging
from typing import Any


def resolve_chatbot_owner_id(user_email: str | None, session_id_header: str | None) -> str | None:
    """로그인/비로그인 사용자별 챗봇 owner_id를 계산한다."""
    if user_email and user_email != "user@example.com":
        return user_email
    return session_id_header


def handle_chatbot_sessions_request(
    bot: Any,
    method: str,
    owner_id: str | None,
    req_data: dict[str, Any],
) -> tuple[int, dict[str, Any]]:
    """챗봇 세션 목록/생성을 공통 처리한다."""
    if method == "GET":
        sessions = bot.history.get_all_sessions(owner_id=owner_id)
        return 200, {"sessions": sessions}

    model_name = req_data.get("model")
    session_id = bot.history.create_session(model_name=model_name, owner_id=owner_id)
    return 200, {"session_id": session_id, "message": "New session created"}


def handle_chatbot_history_request(
    bot: Any,
    method: str,
    session_id: str | None,
    msg_index_str: str | None,
) -> tuple[int, dict[str, Any]]:
    """챗봇 히스토리 조회/삭제를 처리한다."""
    if method == "GET":
        if session_id:
            history = bot.history.get_messages(session_id)
            return 200, {"history": history}
        return 200, {"history": []}

    if session_id == "all":
        bot.history.clear_all()
        return 200, {"status": "cleared all"}

    if not session_id:
        return 400, {"error": "Missing session_id"}

    if msg_index_str is None:
        bot.history.delete_session(session_id)
        return 200, {"status": "deleted session"}

    try:
        msg_index = int(msg_index_str)
    except ValueError:
        return 400, {"error": "Invalid index format"}

    success = bot.history.delete_message(session_id, msg_index)
    if success:
        return 200, {"status": "deleted message"}
    return 404, {"error": "Message not found"}


def handle_chatbot_profile_request(
    bot: Any,
    method: str,
    req_data: dict[str, Any],
) -> tuple[int, dict[str, Any]]:
    """챗봇 프로필 조회/수정을 처리한다."""
    if method == "GET":
        profile = bot.get_user_profile()
        return 200, {"profile": profile}

    name = req_data.get("name")
    persona = req_data.get("persona")
    if not name:
        return 400, {"error": "Name is required"}

    updated = bot.update_user_profile(name, persona)
    return 200, {"message": "Profile updated", "profile": updated}


def parse_chatbot_watchlist_query(watchlist_param: str | None) -> list[str] | None:
    """watchlist 쿼리 문자열(comma separated)을 정규화한다."""
    if not watchlist_param:
        return None
    return [item.strip() for item in watchlist_param.split(",") if item.strip()]


def resolve_chatbot_usage_context(
    user_api_key_header: str | None,
    user_email_header: str | None,
    session_id_header: str | None,
) -> dict[str, Any]:
    """요청 헤더 기준 사용자/세션/키 컨텍스트를 정규화한다."""
    user_api_key = (user_api_key_header or "").strip() or None
    is_authenticated = bool(user_email_header and user_email_header != "user@example.com")
    usage_key = user_email_header if is_authenticated else session_id_header
    return {
        "user_api_key": user_api_key,
        "usage_key": usage_key,
        "header_session_id": session_id_header,
    }


def parse_chatbot_watchlist_json(raw_watchlist: str | None, logger: logging.Logger) -> Any:
    """multipart watchlist 문자열을 안전하게 JSON 파싱한다."""
    if not raw_watchlist:
        return None

    try:
        return json.loads(raw_watchlist)
    except json.JSONDecodeError as e:
        logger.warning(f"[Chatbot] watchlist JSON 파싱 실패: {e}")
        return None


def parse_chatbot_request_payload(
    *,
    content_type: str | None,
    form_data: Any,
    request_files: Any,
    request_json: dict[str, Any] | None,
    default_session_id: str | None,
    logger: logging.Logger,
) -> dict[str, Any]:
    """JSON/multipart 요청 본문을 공통 파라미터로 변환한다."""
    payload: dict[str, Any] = {
        "message": "",
        "model_name": None,
        "session_id": default_session_id,
        "persona": None,
        "watchlist": None,
        "files": [],
    }

    if content_type and "multipart/form-data" in content_type:
        payload["message"] = form_data.get("message", "")
        payload["model_name"] = form_data.get("model")
        payload["session_id"] = form_data.get("session_id", payload["session_id"])
        payload["persona"] = form_data.get("persona")
        payload["watchlist"] = parse_chatbot_watchlist_json(form_data.get("watchlist"), logger=logger)

        if "file" in request_files:
            uploaded_files = request_files.getlist("file")
            for file in uploaded_files:
                if file.filename == "":
                    continue
                payload["files"].append({"mime_type": file.content_type, "data": file.read()})
    else:
        data = request_json or {}
        payload["message"] = data.get("message", "")
        payload["model_name"] = data.get("model")
        payload["session_id"] = data.get("session_id", payload["session_id"])
        payload["persona"] = data.get("persona")
        payload["watchlist"] = data.get("watchlist")

    return payload


def detect_chatbot_device_type(platform: str | None, ua_string: str | None) -> str:
    """요청 메타데이터 기반 디바이스 유형을 판별한다."""
    ua = ua_string or ""
    if platform in ("android", "iphone", "ipad") or "Mobile" in ua:
        return "MOBILE"
    return "WEB"


def extract_chatbot_client_ip(forwarded_for: str | None, remote_addr: str | None) -> str | None:
    """X-Forwarded-For 또는 remote_addr에서 실사용자 IP를 추출한다."""
    real_ip = forwarded_for or remote_addr
    if real_ip and "," in real_ip:
        return real_ip.split(",")[0].strip()
    return real_ip

