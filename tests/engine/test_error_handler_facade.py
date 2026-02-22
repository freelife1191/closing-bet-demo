#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Error Handler 퍼사드/분해 회귀 테스트
"""

import asyncio
import os
import sys

import pytest


sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from engine.error_handler import (
    ErrorHandler,
    build_error_response,
    build_success_response,
    execute_with_fallback,
    execute_with_fallback_async,
    handle_llm_error,
    safe_execute,
    validate_positive,
    validate_range,
    validate_required,
)
from engine.exceptions import EngineError, LLMAnalysisError


def test_safe_execute_returns_default_on_error():
    def _raise():
        raise RuntimeError("boom")

    assert safe_execute(_raise, default=123) == 123


def test_execute_with_fallback_calls_secondary():
    def _primary():
        raise RuntimeError("primary")

    def _fallback():
        return "ok"

    assert execute_with_fallback(_primary, _fallback, default="nope") == "ok"


def test_execute_with_fallback_async_calls_secondary():
    async def _primary():
        raise RuntimeError("primary")

    async def _fallback():
        return "ok-async"

    result = asyncio.run(execute_with_fallback_async(_primary, _fallback, default="nope"))
    assert result == "ok-async"


def test_handle_llm_error_decorator_returns_default():
    @handle_llm_error(default_return={"score": 0})
    def _run():
        raise LLMAnalysisError("llm failed")

    assert _run() == {"score": 0}


def test_validation_helpers_raise_expected_errors():
    with pytest.raises(ValueError):
        validate_required("", "name")

    with pytest.raises(ValueError):
        validate_range(11, "score", max_val=10)

    with pytest.raises(ValueError):
        validate_positive(0, "price")


def test_response_builders_include_error_metadata():
    error = EngineError("failed", context={"step": "load"})
    payload = build_error_response(error, include_details=True)

    assert payload["error"] is True
    assert payload["type"] == "EngineError"
    assert "details" in payload
    assert "context" in payload

    success = build_success_response({"ok": True}, message="done")
    assert success["error"] is False
    assert success["data"]["ok"] is True
    assert success["message"] == "done"


def test_error_handler_context_suppresses_error_and_returns_default():
    with ErrorHandler("test-op", default_return="fallback") as handler:
        raise RuntimeError("boom")

    assert handler.get_result() == "fallback"
