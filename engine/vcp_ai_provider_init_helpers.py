#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VCP AI provider initialization helpers.
"""

from __future__ import annotations

from typing import Any


def init_gemini_client(providers: list[str], app_config: Any, logger: Any) -> Any:
    """Gemini client를 초기화해 반환한다."""
    if "gemini" not in providers:
        return None

    api_key = app_config.GOOGLE_API_KEY
    if not api_key:
        logger.warning("GOOGLE_API_KEY가 설정되지 않아 Gemini 사용 불가")
        return None

    try:
        from google import genai

        client = genai.Client(api_key=api_key)
        logger.info("✅ Gemini 클라이언트 초기화 성공")
        return client
    except Exception as error:
        logger.error(f"Gemini 초기화 실패: {error}")
        return None


def init_gpt_client(providers: list[str], app_config: Any, logger: Any) -> Any:
    """GPT(OpenAI) client를 초기화해 반환한다."""
    if "gpt" not in providers and "openai" not in providers:
        return None

    api_key = app_config.OPENAI_API_KEY
    if not api_key:
        logger.warning("OPENAI_API_KEY가 설정되지 않아 GPT 사용 불가")
        return None

    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key)
        logger.info("✅ GPT (OpenAI) 클라이언트 초기화 성공")
        return client
    except Exception as error:
        logger.error(f"GPT 초기화 실패: {error}")
        return None


def resolve_perplexity_disabled(
    providers: list[str],
    second_provider: str,
    has_api_key: bool,
    logger: Any,
) -> bool:
    """Perplexity 사용 가능 여부(비활성화 플래그)를 계산한다."""
    needs_perplexity = "perplexity" in providers or second_provider == "perplexity"
    if needs_perplexity and not has_api_key:
        logger.warning("PERPLEXITY_API_KEY가 설정되지 않아 Perplexity 사용 불가")
        return True
    return False

