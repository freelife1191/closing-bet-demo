#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
챗봇 응답 처리: 에러/메타데이터/폴백 모델 유틸
"""

from __future__ import annotations

import re
from typing import Any, Dict, List

from engine.llm_analyzer_retry import build_model_chain


def extract_usage_metadata(response: Any) -> Dict[str, int]:
    """Gemini 응답에서 토큰 사용량 메타데이터를 추출한다."""
    meta = getattr(response, "usage_metadata", None)
    if meta is None:
        return {}
    return {
        "prompt_token_count": getattr(meta, "prompt_token_count", 0),
        "candidates_token_count": getattr(meta, "candidates_token_count", 0),
        "total_token_count": getattr(meta, "total_token_count", 0),
    }


def friendly_error_message(error_msg: str, default_prefix: str) -> str:
    """사용자 친화 에러 메시지 변환."""
    # google-genai 의 APIError 는 "<code> <status>. <details>" 로 문자열화된다. 판정은 이 맨 앞
    # 코드로 한다. `"400" in error_msg` 같은 부분 문자열 검사는 details 에 낀 숫자
    # (max_output_tokens=16400 등)에 걸려 오분류된다([CHAT-036]).
    match = re.match(r"\s*(\d{3})\b", error_msg or "")
    code = int(match.group(1)) if match else None

    if (
        code == 429
        or "Resource exhausted" in error_msg
        or "RESOURCE_EXHAUSTED" in error_msg
    ):
        return (
            "⚠️ **AI 서버 요청 한도 초과**\n\n"
            "Vertex AI 서버의 분당 요청 한도에 도달했습니다.\n"
            "**약 30초~1분 후에 다시 시도해주세요.**\n\n"
            "💡 사용량이 자주 초과되면 관리자에게 문의해 주세요."
        )

    # Vertex 서비스 계정 인증 실패는 401·403 으로 온다. API 키 문구는 종전 경로의 호환이다.
    if (
        code in (401, 403)
        or "API_KEY_INVALID" in error_msg
        or "API key not valid" in error_msg
    ):
        return (
            "⚠️ **AI 서버 인증 오류**\n\n"
            "Vertex AI 서비스 계정 인증에 문제가 발생했습니다.\n"
            "관리자에게 문의해 주세요.\n"
            "(Google Cloud 서비스 일시 장애일 수도 있습니다.)"
        )

    if code is not None and code >= 500:
        return (
            "⚠️ **AI 서버 일시 장애**\n\n"
            f"AI 서버가 요청을 처리하지 못했습니다 (HTTP {code}).\n"
            "**잠시 후 다시 시도해주세요.**"
        )

    return f"{default_prefix}{error_msg}"


# 3.x / 2.5 tier를 번갈아 소진하도록 의도한 순서로, Gemini 재시도 체인과 별개다.
CHATBOT_STREAM_FALLBACK_CHAIN = [
    "gemini-3.5-flash-lite",
    "gemini-2.5-flash-lite",
    "gemini-3.7-flash",
    "gemini-2.5-flash",
]


def build_fallback_models(target_model_name: str) -> List[str]:
    """스트리밍 재시도용 모델 후보 리스트."""
    return build_model_chain(target_model_name, CHATBOT_STREAM_FALLBACK_CHAIN)


__all__ = [
    "extract_usage_metadata",
    "friendly_error_message",
    "build_fallback_models",
]
