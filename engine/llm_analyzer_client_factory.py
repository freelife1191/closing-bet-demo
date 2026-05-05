#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LLM Analyzer client/strategy factory helpers.
"""

from __future__ import annotations

from typing import Any

from engine.llm_analyzer_retry import GeminiRetryStrategy, LLMRetryStrategy, ZAIRetryStrategy


def resolve_api_key(
    provider: str,
    api_key_source: str | None,
    app_config: Any,
) -> str | None:
    """공급자에 따라 API 키를 결정한다.

    Gemini는 Vertex AI(서비스 계정 ADC)를 사용하므로 실제 API 키는 없다.
    LLMAnalyzer._init_client는 빈 키를 보면 client 생성을 건너뛰므로,
    Vertex 설정이 갖춰져 있으면 sentinel "vertex"를 반환해 client 생성을 진행시킨다.
    """
    if api_key_source:
        return api_key_source
    if provider == "zai":
        return app_config.ZAI_API_KEY

    from engine.genai_client import vertex_configured

    return "vertex" if vertex_configured() else ""


def _create_zai_client_and_strategy(
    *,
    api_key: str | None,
    app_config: Any,
    logger: Any,
) -> tuple[Any | None, LLMRetryStrategy | None]:
    try:
        from openai import OpenAI

        base_url = app_config.ZAI_BASE_URL
        formatted_key = api_key[:4] + "*" * 10 if api_key else "None"
        logger.info(f"Z.ai LLM Init (Key: {formatted_key})")

        client = OpenAI(api_key=api_key, base_url=base_url)
        strategy = ZAIRetryStrategy(client, app_config.ZAI_MODEL)
        return client, strategy
    except ImportError:
        logger.error("openai package missing")
    except Exception as error:
        logger.error(f"Z.ai Init Failed: {error}")
    return None, None


def _create_gemini_client_and_strategy(
    *,
    api_key: str | None,
    genai_module: Any,
    app_config: Any,
    logger: Any,
) -> tuple[Any | None, LLMRetryStrategy | None]:
    """Vertex AI 기반 Gemini client + retry strategy 생성.

    api_key 인자는 하위 호환을 위해 받지만 Vertex 모드에서는 사용되지 않는다.
    """
    del api_key  # Vertex 모드: ADC 인증 사용
    if genai_module is None:
        logger.error("google-genai package missing")
        return None, None

    try:
        from engine.genai_client import build_genai_client

        timeout_ms = float(app_config.ANALYSIS_LLM_API_TIMEOUT) * 1000
        client = build_genai_client(http_options={"timeout": timeout_ms})
        strategy = GeminiRetryStrategy(client, app_config.ANALYSIS_GEMINI_MODEL)
        logger.info(
            f"Gemini(Vertex) LLM Client Initialized - Model: {app_config.ANALYSIS_GEMINI_MODEL}, "
            f"Project: {app_config.GOOGLE_CLOUD_PROJECT}, Location: {app_config.GOOGLE_CLOUD_LOCATION}, "
            f"Timeout setting: {timeout_ms}ms"
        )
        return client, strategy
    except Exception as error:
        logger.error(f"Gemini(Vertex) Init Failed: {error}")
    return None, None


def create_client_and_strategy(
    *,
    provider: str,
    api_key: str | None,
    genai_module: Any,
    app_config: Any,
    logger: Any,
) -> tuple[Any | None, LLMRetryStrategy | None]:
    """공급자별 client + retry strategy를 생성한다."""
    if provider == "zai":
        return _create_zai_client_and_strategy(
            api_key=api_key,
            app_config=app_config,
            logger=logger,
        )
    return _create_gemini_client_and_strategy(
        api_key=api_key,
        genai_module=genai_module,
        app_config=app_config,
        logger=logger,
    )

