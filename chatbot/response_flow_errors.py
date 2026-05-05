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
            "Vertex AI 서버의 분당 요청 한도에 도달했습니다.\n"
            "**약 30초~1분 후에 다시 시도해주세요.**\n\n"
            "💡 사용량이 자주 초과되면 관리자에게 문의해 주세요."
        )

    if (
        "400" in error_msg
        or "API_KEY_INVALID" in error_msg
        or "API key not valid" in error_msg
    ):
        return (
            "⚠️ **AI 서버 인증 오류**\n\n"
            "Vertex AI 서비스 계정 인증에 문제가 발생했습니다.\n"
            "관리자에게 문의해 주세요.\n"
            "(Google Cloud 서비스 일시 장애일 수도 있습니다.)"
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
