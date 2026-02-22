#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LLM Analyzer 재시도 전략 모듈.
"""

from __future__ import annotations

import asyncio
import logging
import random
from abc import ABC, abstractmethod
from typing import Callable


logger = logging.getLogger(__name__)


class RetryConfig:
    """재시도 설정."""

    MAX_RETRIES = 5
    BASE_WAIT = 2.0
    MAX_WAIT = 32.0
    RETRY_CONDITIONS = (
        "429",
        "resource_exhausted",
        "503",
        "overloaded",
        "502",
        "500",
        "unavailable",
    )

    @classmethod
    def is_retryable_error(cls, error_msg: str) -> bool:
        """재시도 가능한 오류 문자열인지 판정한다."""
        lowered = (error_msg or "").lower()
        return any(condition in lowered for condition in cls.RETRY_CONDITIONS)

    @classmethod
    def compute_wait_time(cls, attempt: int) -> float:
        """지수 백오프 + jitter 대기 시간 계산."""
        return min(
            (cls.BASE_WAIT * (2 ** attempt)) + random.uniform(0.5, 1.5),
            cls.MAX_WAIT,
        )


GEMINI_RETRY_MODEL_CHAIN = [
    "gemini-2.0-flash-lite",
    "gemini-2.5-flash-lite",
    "gemini-2.0-flash",
    "gemini-2.5-flash",
    "gemini-3-flash-preview",
]


class LLMRetryStrategy(ABC):
    """LLM 재시도 전략 인터페이스."""

    @abstractmethod
    async def execute(
        self,
        prompt: str,
        timeout: float,
        model: str,
    ) -> str:
        """LLM 호출 실행."""

    @abstractmethod
    def get_model_name(self) -> str:
        """모델명 반환."""


class GeminiRetryStrategy(LLMRetryStrategy):
    """Gemini 재시도 전략."""

    def __init__(self, client, model: str = "gemini-2.0-flash"):
        self.client = client
        self.model = model
        self._model_chain = list(GEMINI_RETRY_MODEL_CHAIN)
        self._current_model = self._model_chain[0]

    async def execute(self, prompt: str, timeout: float, model: str) -> str:
        """Gemini 호출 실행."""
        self._current_model = self._model_chain[0]

        def _call_gemini():
            return self.client.models.generate_content(
                model=self._current_model,
                contents=prompt,
            )

        return await self._call_with_retry(_call_gemini, timeout)

    async def _call_with_retry(self, call_fn: Callable, timeout: float) -> str:
        """Gemini 재시도 로직."""
        total_models = len(self._model_chain)

        for attempt, current_model in enumerate(self._model_chain):
            self._current_model = current_model
            try:
                response = await asyncio.wait_for(
                    asyncio.to_thread(call_fn),
                    timeout=timeout,
                )

                model_version = getattr(response, "model_version", None)
                if model_version and model_version != self._current_model:
                    logger.debug(
                        f"[GEMINI] 요청 모델: {self._current_model} -> "
                        f"실제 응답 모델: {model_version}"
                    )

                return response.text

            except asyncio.TimeoutError:
                logger.warning(
                    f"[GEMINI] Timeout (Attempt {attempt + 1}/{total_models}, Model: {self._current_model})"
                )
                if attempt >= total_models - 1:
                    raise

                next_model = self._model_chain[attempt + 1]
                wait_time = RetryConfig.compute_wait_time(attempt)
                logger.warning(
                    f"[GEMINI] Timeout으로 모델 전환: {self._current_model} -> {next_model} "
                    f"(대기 {wait_time:.1f}s)"
                )
                await asyncio.sleep(wait_time)
                continue

            except Exception as error:
                is_retryable = RetryConfig.is_retryable_error(str(error))

                if attempt < total_models - 1:
                    next_model = self._model_chain[attempt + 1]
                    wait_time = RetryConfig.compute_wait_time(attempt)
                    error_type = "재시도 가능 오류" if is_retryable else "분석 실패"
                    logger.warning(
                        f"[GEMINI] {error_type} 발생으로 모델 전환: {self._current_model} -> {next_model} "
                        f"(대기 {wait_time:.1f}s, {attempt + 1}/{total_models})"
                    )
                    await asyncio.sleep(wait_time)
                    continue

                raise error

    def get_model_name(self) -> str:
        return self._current_model


class ZAIRetryStrategy(LLMRetryStrategy):
    """Z.ai (OpenAI 호환) 재시도 전략."""

    def __init__(self, client, model: str = "gpt-4o-mini"):
        self.client = client
        self.model = model

    async def execute(self, prompt: str, timeout: float, model: str) -> str:
        """Z.ai 호출 실행."""
        messages = [
            {"role": "system", "content": "당신은 주식 투자 전문가입니다."},
            {"role": "user", "content": prompt},
        ]

        def _call_zai():
            return self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.1,
            )

        response = await asyncio.wait_for(
            asyncio.to_thread(_call_zai),
            timeout=timeout,
        )

        if response and response.choices:
            return response.choices[0].message.content
        return ""

    def get_model_name(self) -> str:
        return self.model


__all__ = [
    "RetryConfig",
    "LLMRetryStrategy",
    "GeminiRetryStrategy",
    "ZAIRetryStrategy",
]
