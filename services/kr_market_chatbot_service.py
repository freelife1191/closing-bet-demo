#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KR Market Chatbot Service

챗봇 보조 로직의 호환 import 레이어를 제공한다.
실제 구현은 기능별 헬퍼 모듈로 분리한다.
"""

from __future__ import annotations

from services.kr_market_chatbot_quota_helpers import (
    check_chatbot_quota_guard,
    maybe_increment_chatbot_usage,
    should_increment_free_quota,
)
from services.kr_market_chatbot_request_helpers import (
    detect_chatbot_device_type,
    extract_chatbot_client_ip,
    handle_chatbot_history_request,
    handle_chatbot_profile_request,
    handle_chatbot_sessions_request,
    parse_chatbot_request_payload,
    parse_chatbot_watchlist_json,
    parse_chatbot_watchlist_query,
    resolve_chatbot_owner_id,
    resolve_chatbot_usage_context,
)
from services.kr_market_chatbot_stream_helpers import (
    stream_chatbot_response,
    stream_chatbot_response_chunks,
)

__all__ = [
    "check_chatbot_quota_guard",
    "detect_chatbot_device_type",
    "extract_chatbot_client_ip",
    "handle_chatbot_history_request",
    "handle_chatbot_profile_request",
    "handle_chatbot_sessions_request",
    "maybe_increment_chatbot_usage",
    "parse_chatbot_request_payload",
    "parse_chatbot_watchlist_json",
    "parse_chatbot_watchlist_query",
    "resolve_chatbot_owner_id",
    "resolve_chatbot_usage_context",
    "should_increment_free_quota",
    "stream_chatbot_response",
    "stream_chatbot_response_chunks",
]
