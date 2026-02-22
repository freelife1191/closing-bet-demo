#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LLM Analyzer retry helper 리팩토링 회귀 테스트
"""

from __future__ import annotations

from unittest.mock import patch

from engine.llm_analyzer_retry import RetryConfig


def test_retry_config_identifies_retryable_error_strings():
    assert RetryConfig.is_retryable_error("429 RATE_LIMIT") is True
    assert RetryConfig.is_retryable_error("503 unavailable") is True
    assert RetryConfig.is_retryable_error("business logic failure") is False


def test_retry_config_compute_wait_time_uses_bounds():
    with patch("engine.llm_analyzer_retry.random.uniform", return_value=0.0):
        wait_0 = RetryConfig.compute_wait_time(0)
        wait_10 = RetryConfig.compute_wait_time(10)

    assert wait_0 == RetryConfig.BASE_WAIT
    assert wait_10 == RetryConfig.MAX_WAIT
