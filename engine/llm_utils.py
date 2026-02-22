#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Engine - LLM Utilities (Facade)

기존 공개 API를 유지하면서 기능별 모듈로 분리된 구현을 재노출한다.
"""

from engine.llm_utils_batch import process_batch_with_concurrency
from engine.llm_utils_fallback import ModelFallbackHandler
from engine.llm_utils_logging import LLMCallLogger, log_llm_response
from engine.llm_utils_parsing import extract_code_block, extract_json_from_response
from engine.llm_utils_retry import (
    RetryConfig,
    async_retry_with_backoff,
    retry_async_call,
    retry_blocking_call,
    sync_retry_with_backoff,
)

__all__ = [
    "RetryConfig",
    "async_retry_with_backoff",
    "sync_retry_with_backoff",
    "retry_async_call",
    "retry_blocking_call",
    "process_batch_with_concurrency",
    "extract_json_from_response",
    "extract_code_block",
    "LLMCallLogger",
    "log_llm_response",
    "ModelFallbackHandler",
]
