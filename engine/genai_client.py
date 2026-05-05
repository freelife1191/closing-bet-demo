#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
google-genai Vertex AI Client 팩토리.

이 모듈은 프로젝트 전역에서 사용하는 단 하나의 genai.Client 생성 경로다.
인증은 GOOGLE_APPLICATION_CREDENTIALS(서비스 계정 JSON)을 통한 ADC로 위임한다.
AI Studio API Key 방식은 더 이상 지원하지 않는다.
"""

from __future__ import annotations

import os
from typing import Any, Optional


def _vertex_enabled() -> bool:
    return os.getenv("GOOGLE_GENAI_USE_VERTEXAI", "").strip().lower() in {"1", "true", "yes", "on"}


def build_genai_client(http_options: Optional[dict] = None) -> Any:
    """Vertex AI 모드로 google-genai Client를 생성한다.

    Returns:
        google.genai.Client 인스턴스

    Raises:
        RuntimeError: Vertex 설정이 누락된 경우
        ImportError: google-genai 패키지 미설치
    """
    if not _vertex_enabled():
        raise RuntimeError(
            "Vertex AI 모드가 비활성화되어 있습니다. "
            "GOOGLE_GENAI_USE_VERTEXAI=true 와 GOOGLE_CLOUD_PROJECT를 설정하세요. "
            "이 프로젝트는 더 이상 AI Studio API Key 방식을 지원하지 않습니다."
        )

    project = os.environ.get("GOOGLE_CLOUD_PROJECT", "").strip()
    if not project:
        raise RuntimeError("GOOGLE_CLOUD_PROJECT 환경변수가 필요합니다.")

    location = os.environ.get("GOOGLE_CLOUD_LOCATION", "global").strip() or "global"

    from google import genai

    kwargs: dict = {"vertexai": True, "project": project, "location": location}
    if http_options:
        kwargs["http_options"] = http_options
    return genai.Client(**kwargs)


def vertex_configured() -> bool:
    """현재 환경에서 Vertex 호출이 가능한지 확인 (config 가용성 체크용)."""
    return _vertex_enabled() and bool(os.environ.get("GOOGLE_CLOUD_PROJECT", "").strip())


__all__ = ["build_genai_client", "vertex_configured"]
