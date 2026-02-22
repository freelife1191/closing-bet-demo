#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KR Market Chatbot Quota Helpers

챗봇 무료 사용량 가드/차감 로직을 제공한다.
"""

from __future__ import annotations

import logging
from typing import Any, Callable


def check_chatbot_quota_guard(
    user_api_key: str | None,
    usage_key: str | None,
    max_free_usage: int,
    get_user_usage_fn: Callable[[str | None], int],
    server_key_available: bool,
) -> tuple[bool, tuple[int, dict[str, Any]] | None]:
    """
    무료 티어 사용 가능 여부를 확인한다.
    반환값: (use_free_tier, (status_code, payload) | None)
    """
    if user_api_key:
        return False, None

    if not usage_key:
        return False, (
            400,
            {
                "error": "세션 정보가 없습니다. 페이지를 새로고침 해주세요.",
                "code": "SESSION_REQUIRED",
            },
        )

    if not server_key_available:
        return False, (
            503,
            {
                "error": "시스템 API Key가 설정되지 않았습니다.",
                "code": "SERVER_CONFIG_MISSING",
            },
        )

    used = get_user_usage_fn(usage_key)
    if used >= max_free_usage:
        return False, (
            402,
            {
                "error": "무료 사용량(10회)을 초과했습니다. [설정 > API]에서 개인 API Key를 등록해주세요.",
                "code": "QUOTA_EXCEEDED",
            },
        )

    return True, None


def should_increment_free_quota(use_free_tier: bool, stream_has_error: bool, full_response: str) -> bool:
    """무료 티어일 때 정상 완료 응답만 차감 대상으로 본다."""
    if not use_free_tier:
        return False
    if stream_has_error:
        return False
    return not str(full_response).startswith("⚠️")


def maybe_increment_chatbot_usage(
    *,
    use_free_tier: bool,
    usage_key: str | None,
    stream_has_error: bool,
    full_response: str,
    increment_user_usage_fn: Callable[[str | None], int],
    logger: logging.Logger,
) -> None:
    """무료 티어일 때 응답 성공 건만 사용량을 차감한다."""
    if not usage_key:
        return

    should_increment = should_increment_free_quota(
        use_free_tier=use_free_tier,
        stream_has_error=stream_has_error,
        full_response=full_response,
    )
    logger.info(
        f"[QUOTA] use_free_tier={use_free_tier}, stream_has_error={stream_has_error}, "
        f"starts_with_warning={str(full_response).startswith('⚠️')}, usage_key={usage_key}"
    )
    if not should_increment:
        logger.info(f"[QUOTA] 차감 스킵: usage_key={usage_key}")
        return

    new_usage = increment_user_usage_fn(usage_key)
    logger.info(f"[QUOTA] 사용량 차감 완료: {usage_key} -> {new_usage}회")

