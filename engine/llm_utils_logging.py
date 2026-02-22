#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Engine - LLM Utilities (Logging)
"""

from __future__ import annotations

import logging
import time


logger = logging.getLogger(__name__)


class LLMCallLogger:
    """
    LLM API 호출 로깅 헬퍼.
    """

    def __init__(self, provider: str, operation: str):
        self.provider = provider.upper()
        self.operation = operation
        self.start_time = None

    def __enter__(self):
        self.start_time = time.time()
        logger.info(f"[{self.provider}] Starting {self.operation}...")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        elapsed = time.time() - self.start_time
        if exc_type is None:
            logger.info(f"[{self.provider}] {self.operation} completed in {elapsed:.2f}s")
            return
        logger.error(f"[{self.provider}] {self.operation} failed after {elapsed:.2f}s: {exc_val}")

    async def __aenter__(self):
        self.start_time = time.time()
        logger.info(f"[{self.provider}] Starting {self.operation}...")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        elapsed = time.time() - self.start_time
        if exc_type is None:
            logger.info(f"[{self.provider}] {self.operation} completed in {elapsed:.2f}s")
            return
        logger.error(f"[{self.provider}] {self.operation} failed after {elapsed:.2f}s: {exc_val}")


def log_llm_response(provider: str, response_length: int, model: str = None):
    """
    LLM 응답 로깅.
    """

    model_info = f" (Model: {model})" if model else ""
    logger.info(
        f"[{provider.upper()}] Response received{model_info} "
        f"(Length: {response_length} chars)"
    )


__all__ = ["LLMCallLogger", "log_llm_response"]
