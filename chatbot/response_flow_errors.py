#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
챗봇 응답 처리: 에러/메타데이터/폴백 모델 유틸
"""

from __future__ import annotations

from typing import Any, Dict, List


def extract_usage_metadata(response: Any) -> Dict[str, int]:
    """Gemini 응답에서 토큰 사용량 메타데이터를 추출한다."""
    if not hasattr(response, "usage_metadata"):
        return {}
    meta = response.usage_metadata
    return {
        "prompt_token_count": getattr(meta, "prompt_token_count", 0),
        "candidates_token_count": getattr(meta, "candidates_token_count", 0),
        "total_token_count": getattr(meta, "total_token_count", 0),
    }


def friendly_error_message(error_msg: str, default_prefix: str) -> str:
    """사용자 친화 에러 메시지 변환."""
    if (
        "429" in error_msg
        or "Resource exhausted" in error_msg
        or "RESOURCE_EXHAUSTED" in error_msg
    ):
        return (
            "⚠️ **AI 서버 요청 한도 초과**\n\n"
            "Google AI 서버의 분당 요청 한도에 도달했습니다.\n"
            "**약 30초~1분 후에 다시 시도해주세요.**\n\n"
            "💡 안정적인 사용을 위해 **[설정] > [API Key]** 메뉴에서 "
            "개인 API Key를 등록하시면 이 제한을 피할 수 있습니다."
        )

    if (
        "400" in error_msg
        or "API_KEY_INVALID" in error_msg
        or "API key not valid" in error_msg
    ):
        return (
            "⚠️ **API Key 설정 오류**\n\n"
            "시스템에 설정된 API Key가 유효하지 않습니다.\n"
            "관리자에게 문의하거나 **[설정] > [API Key]** 메뉴에서 "
            "올바른 API Key를 다시 등록해주세요.\n"
            "(Google 서비스 문제일 수도 있습니다.)"
        )

    return f"{default_prefix}{error_msg}"


def build_fallback_models(target_model_name: str) -> List[str]:
    """스트리밍 재시도용 모델 후보 리스트."""
    fallback_sequence = [
        "gemini-2.0-flash-lite",
        "gemini-2.5-flash-lite",
        "gemini-2.0-flash",
        "gemini-2.5-flash",
        "gemini-3-flash-preview",
    ]
    models = [target_model_name]
    for model_name in fallback_sequence:
        if model_name not in models:
            models.append(model_name)
    return models


def is_retryable_stream_error(error_msg: str) -> bool:
    """스트리밍 폴백 재시도 가능 에러인지 판별한다."""
    error_upper = error_msg.upper()
    return (
        "503" in error_msg
        or "UNAVAILABLE" in error_upper
        or "429" in error_msg
        or "RESOURCE EXHAUSTED" in error_upper
        or "RESOURCE_EXHAUSTED" in error_upper
    )


__all__ = [
    "extract_usage_metadata",
    "friendly_error_message",
    "build_fallback_models",
    "is_retryable_stream_error",
]
