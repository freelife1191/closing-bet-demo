#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KR Market Quota Service

챗봇 무료 사용량(쿼터) 관련 로직을 라우트에서 분리한다.
"""

from __future__ import annotations

import json
from typing import Any, Callable


def safe_usage_count(value: Any) -> int:
    """저장된 사용량 값을 0 이상의 정수로 정규화한다."""
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


def load_quota_data_unlocked(load_json_file: Callable[..., dict[str, Any]]) -> dict[str, int]:
    """quota json을 읽어 정규화된 dict를 반환한다 (lock 외부 호출 금지)."""
    try:
        raw_data = load_json_file("user_quota.json", deep_copy=False)
    except TypeError:
        raw_data = load_json_file("user_quota.json")
    if not isinstance(raw_data, dict):
        return {}

    return {
        str(key): safe_usage_count(value)
        for key, value in raw_data.items()
        if str(key).strip()
    }


def save_quota_data_unlocked(
    quota_data: dict[str, int],
    atomic_write_text: Callable[[str, str], None],
    quota_file_path: str,
) -> None:
    """quota json을 원자적으로 저장한다 (lock 외부 호출 금지)."""
    serialized = json.dumps(quota_data, indent=2, ensure_ascii=False)
    atomic_write_text(quota_file_path, serialized)


def resolve_quota_usage_key(user_email: str | None, session_id: str | None) -> str | None:
    """로그인 여부를 고려해 quota usage key를 계산한다."""
    is_authenticated = bool(user_email and user_email != "user@example.com")
    return user_email if is_authenticated else session_id


def build_quota_info_payload(
    usage_key: str | None,
    max_free_usage: int,
    get_user_usage_fn: Callable[[str | None], int],
    server_key_available: bool,
) -> dict[str, Any]:
    """쿼터 조회 응답 payload를 생성한다."""
    if not usage_key:
        return {
            "usage": 0,
            "limit": max_free_usage,
            "remaining": max_free_usage,
            "message": "무료 10회 사용 가능",
        }

    used = get_user_usage_fn(usage_key)
    remaining = max(0, max_free_usage - used)
    return {
        "usage": used,
        "limit": max_free_usage,
        "remaining": remaining,
        "is_exhausted": used >= max_free_usage,
        "server_key_configured": server_key_available,
    }
