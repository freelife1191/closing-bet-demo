#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LLM Utils 퍼사드/분해 회귀 테스트
"""

import os
import sys
import asyncio


sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from engine.llm_utils import (
    ModelFallbackHandler,
    extract_code_block,
    extract_json_from_response,
    process_batch_with_concurrency,
    retry_async_call,
)


def test_extract_json_from_response_parses_markdown_object():
    text = "```json\n{\"action\":\"BUY\",\"score\":90}\n```"
    parsed = extract_json_from_response(text)

    assert parsed is not None
    assert parsed["action"] == "BUY"
    assert parsed["score"] == 90


def test_extract_code_block_with_language():
    text = "prefix\n```python\nprint('ok')\n```\nsuffix"
    code = extract_code_block(text, "python")

    assert code == "print('ok')"


def test_retry_async_call_retries_on_retryable_error():
    state = {"count": 0}

    async def _call():
        state["count"] += 1
        if state["count"] == 1:
            raise RuntimeError("429 rate limit")
        return "ok"

    result = asyncio.run(
        retry_async_call(
            _call,
            max_retries=2,
            base_delay=0.0,
            retry_on=["429"],
        )
    )
    assert result == "ok"
    assert state["count"] == 2


def test_process_batch_with_concurrency_preserves_order():
    async def _processor(item):
        return item * 2

    result = asyncio.run(
        process_batch_with_concurrency(
            items=[3, 1, 2],
            processor=_processor,
            concurrency=2,
        )
    )
    assert result == [6, 2, 4]


def test_model_fallback_handler_switches_once():
    handler = ModelFallbackHandler(
        {"primary": "gemini-main", "fallback": "gemini-backup"}
    )

    assert handler.get_model() == "gemini-main"
    assert handler.should_fallback(RuntimeError("RESOURCE_EXHAUSTED")) is True
    assert handler.get_fallback_model() == "gemini-backup"
    assert handler.should_fallback(RuntimeError("RESOURCE_EXHAUSTED")) is False
    handler.set_model("gemini-backup")
    assert handler.get_model() == "gemini-backup"
    handler.reset()
    assert handler.get_model() == "gemini-main"
