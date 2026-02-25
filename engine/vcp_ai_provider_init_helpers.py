#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VCP AI provider initialization helpers.
"""

from __future__ import annotations

from typing import Any


def normalize_provider_name(name: str | None) -> str:
    """Provider 이름을 내부 표준 키로 정규화한다."""
    provider = str(name or "").strip().lower()
    if provider in {"z.ai", "z_ai", "zai"}:
        return "zai"
    if provider in {"openai"}:
        return "gpt"
    return provider


def normalize_provider_list(providers: list[str]) -> list[str]:
    """Provider 목록을 정규화하고 순서를 유지한 채 중복 제거한다."""
    normalized: list[str] = []
    seen: set[str] = set()
    for provider in providers:
        key = normalize_provider_name(provider)
        if not key or key in seen:
            continue
        normalized.append(key)
        seen.add(key)
    return normalized


def init_gemini_client(providers: list[str], app_config: Any, logger: Any) -> Any:
    """Gemini client를 초기화해 반환한다."""
    normalized = normalize_provider_list(providers)
    if "gemini" not in normalized:
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
    normalized = normalize_provider_list(providers)
    if "gpt" not in normalized:
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


def init_zai_client(app_config: Any, logger: Any) -> Any:
    """Z.ai(OpenAI 호환) client를 초기화해 반환한다."""
    api_key = app_config.ZAI_API_KEY
    if not api_key:
        logger.warning("ZAI_API_KEY가 설정되지 않아 Z.ai fallback 사용 불가")
        return None

    try:
        from openai import OpenAI

        base_url = app_config.ZAI_BASE_URL
        client = OpenAI(api_key=api_key, base_url=base_url)
        logger.info("✅ Z.ai 클라이언트 초기화 성공")
        return client
    except Exception as error:
        logger.error(f"Z.ai 초기화 실패: {error}")
        return None


def resolve_perplexity_disabled(
    providers: list[str],
    second_provider: str,
    has_api_key: bool,
    logger: Any,
) -> bool:
    """Perplexity 사용 가능 여부(비활성화 플래그)를 계산한다."""
    normalized_providers = normalize_provider_list(providers)
    normalized_second = normalize_provider_name(second_provider)
    needs_perplexity = "perplexity" in normalized_providers or normalized_second == "perplexity"
    if needs_perplexity and not has_api_key:
        logger.warning("PERPLEXITY_API_KEY가 설정되지 않아 Perplexity 사용 불가")
        return True
    return False


__all__ = [
    "init_gemini_client",
    "init_gpt_client",
    "init_zai_client",
    "normalize_provider_name",
    "normalize_provider_list",
    "resolve_perplexity_disabled",
]
