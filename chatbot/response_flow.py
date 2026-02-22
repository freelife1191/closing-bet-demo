#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
챗봇 응답 처리(에러/스트리밍/폴백) 유틸 (Facade)

기존 import 경로를 유지하면서 구현을 모듈별로 분리한다.
"""

from __future__ import annotations

from .response_flow_errors import (
    build_fallback_models,
    extract_usage_metadata,
    friendly_error_message,
    is_retryable_stream_error,
)
from .response_flow_fallback import (
    stream_with_fallback_models,
    sync_stream_with_final_response,
)
from .response_flow_stream import (
    stream_single_model_response,
    yield_stream_deltas,
)

__all__ = [
    "extract_usage_metadata",
    "friendly_error_message",
    "build_fallback_models",
    "is_retryable_stream_error",
    "yield_stream_deltas",
    "stream_single_model_response",
    "stream_with_fallback_models",
    "sync_stream_with_final_response",
]
