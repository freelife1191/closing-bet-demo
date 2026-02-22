#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Engine - LLM Analyzer (Gemini/Z.ai) - Refactored

LLM 분석기로 Gemini와 Z.ai를 지원하며, 중복된 재시도 로직을 추출하여 코드를 간소화했습니다.

Created: 2026-02-11
Refactored from: engine/llm_analyzer.py (591 lines → 약 480 lines)
"""
import logging
import time
from typing import List, Dict, Optional
import asyncio

try:
    from google import genai
except ImportError:
    genai = None

from engine.config import app_config
from engine.llm_analyzer_parsers import (
    build_result_map as build_result_map_impl,
    parse_batch_response as parse_batch_response_impl,
    parse_json_response as parse_json_response_impl,
)
from engine.llm_analyzer_formatters import (
    build_market_context as build_market_context_impl,
    build_stocks_text as build_stocks_text_impl,
    format_news_for_prompt as format_news_for_prompt_impl,
)
from engine.llm_analyzer_prompts import (
    build_batch_prompt as build_batch_prompt_impl,
    build_sentiment_prompt as build_sentiment_prompt_impl,
    build_summary_prompt as build_summary_prompt_impl,
)
from engine.llm_analyzer_retry import (
    GEMINI_RETRY_MODEL_CHAIN,
    GeminiRetryStrategy,
    LLMRetryStrategy,
    RetryConfig,
    ZAIRetryStrategy,
)
from engine.llm_analyzer_client_factory import (
    create_client_and_strategy as create_client_and_strategy_impl,
    resolve_api_key as resolve_api_key_impl,
)

logger = logging.getLogger(__name__)


# ========================================================================
# Main LLM Analyzer Class
# ========================================================================

class LLMAnalyzer:
    """
    LLM 분석기 (Gemini / Z.ai 지원)

    Refactored to extract duplicate retry logic into strategy classes.
    """

    def __init__(self, api_key: str = None):
        self.provider = app_config.LLM_PROVIDER.lower()
        self._client = None
        self._api_key_source = api_key
        self._last_loaded_key = None
        self._retry_strategy: Optional[LLMRetryStrategy] = None
        self._client_init_attempted = False
        self._missing_key_warned = False
        self._init_client()

    # ========================================================================
    # Client Initialization
    # ========================================================================

    def _init_client(self) -> None:
        """Initialize Client based on current config"""
        current_key = self._get_api_key()

        # Key hasn't changed and client exists
        if self._client and current_key == self._last_loaded_key:
            return
        if (
            self._client_init_attempted
            and self._client is None
            and current_key == self._last_loaded_key
        ):
            return

        self._last_loaded_key = current_key
        self._client = None
        self._retry_strategy = None  # Reset strategy
        self._client_init_attempted = True

        if not current_key:
            if not self._missing_key_warned:
                logger.warning("API key not configured")
                self._missing_key_warned = True
            return

        self._missing_key_warned = False
        self._create_client(current_key)

    def _get_api_key(self) -> str | None:
        """Get current API key"""
        return resolve_api_key_impl(
            provider=self.provider,
            api_key_source=self._api_key_source,
            app_config=app_config,
        )

    def _create_client(self, api_key: str | None) -> None:
        """Create client based on provider"""
        self._client, self._retry_strategy = create_client_and_strategy_impl(
            provider=self.provider,
            api_key=api_key,
            genai_module=genai,
            app_config=app_config,
            logger=logger,
        )

    # ========================================================================
    # Properties
    # ========================================================================

    @property
    def client(self):
        """Dynamic Client Accessor - always refreshes before returning"""
        self._init_client()
        return self._client

    # ========================================================================
    # Public Methods
    # ========================================================================

    async def close(self) -> None:
        """리소스 정리"""
        try:
            if self._client and hasattr(self._client, 'aclose'):
                await self._client.aclose()
        except Exception as e:
            logger.warning(f"Error closing LLM client: {e}")

    async def analyze_news_sentiment(
        self,
        stock_name: str,
        news_items: List[Dict]
    ) -> Optional[Dict]:
        """
        뉴스 감성 분석 (단일 종목)

        Refactored to use retry strategy.
        """
        if not self.client or not news_items:
            return None

        try:
            prompt = build_sentiment_prompt_impl(
                stock_name=stock_name,
                news_items=news_items,
                format_news_for_prompt_fn=format_news_for_prompt_impl,
            )

            response_content = await self._execute_llm_call(
                prompt=prompt,
                timeout=app_config.LLM_API_TIMEOUT
            )

            model_name = self._retry_strategy.get_model_name() if self._retry_strategy else "unknown"
            return parse_json_response_impl(
                response_text=response_content,
                stock_name=stock_name,
                model_name=model_name,
                logger=logger,
            )

        except Exception as e:
            logger.error(f"{self.provider} 분석 실패 ({stock_name}): {e}")
            return None

    async def analyze_news_batch(
        self,
        items: List[Dict],
        market_status: Dict = None
    ) -> Dict[str, Dict]:
        """
        뉴스 + 심층 데이터 일괄 분석 (Batch Processing)

        Refactored to use retry strategy.
        """
        if not self.client or not items:
            return {}

        start_time = time.time()

        try:
            prompt = build_batch_prompt_impl(
                items=items,
                market_status=market_status,
                build_market_context_fn=build_market_context_impl,
                build_stocks_text_fn=build_stocks_text_impl,
            )

            response_content = await self._execute_llm_call(
                prompt=prompt,
                timeout=app_config.ANALYSIS_LLM_API_TIMEOUT
            )

            results_list = parse_batch_response_impl(
                response_text=response_content,
                logger=logger,
            )
            model_name = self._retry_strategy.get_model_name() if self._retry_strategy else "unknown"
            return build_result_map_impl(results_list=results_list, model_name=model_name)

        except Exception as e:
            logger.error(f"{self.provider} 배치 분석 실패: {e}")
            return {}
        finally:
            elapsed = time.time() - start_time
            logger.info(f"[{self.provider.upper()}] Batch Analysis ({len(items)} stocks): {elapsed:.2f}s")

    async def generate_market_summary(self, signals: List[Dict]) -> str:
        """
        최종 시장 요약 리포트 생성

        Refactored to use retry strategy.
        """
        if not self.client or not signals:
            return "분석된 종목이 없거나 AI 클라이언트가 설정되지 않았습니다."

        try:
            prompt = build_summary_prompt_impl(signals=signals)

            response_content = await self._execute_llm_call(
                prompt=prompt,
                timeout=app_config.LLM_API_TIMEOUT
            )

            return response_content.strip()

        except Exception as e:
            logger.error(f"{self.provider} 시장 요약 실패: {e}")
            return f"시장 요약 생성 실패: {str(e)}"

    # ========================================================================
    # Private Methods - Execution
    # ========================================================================

    async def _execute_llm_call(
        self,
        prompt: str,
        timeout: float
    ) -> str:
        """
        LLM 호출 실행 (재시도 로직 포함)

        Refactored to use retry strategy.
        """
        strategy_client = getattr(self._retry_strategy, "client", None)
        if (
            self._retry_strategy is not None
            and strategy_client is not None
            and self._client is not None
            and strategy_client is not self._client
        ):
            # 테스트/호환 경로: 외부에서 _client를 주입한 경우 전략을 무효화한다.
            self._retry_strategy = None

        if not self._retry_strategy:
            return await self._execute_legacy_retry_call(prompt=prompt, timeout=timeout)

        model_name = self._retry_strategy.get_model_name()
        logger.info(
            f"[{self.provider.upper()}] LLM API 호출 시작 "
            f"(Model: {model_name}, Timeout: {timeout}s)..."
        )

        try:
            return await self._retry_strategy.execute(prompt, timeout, model_name)

        except asyncio.TimeoutError:
            logger.error(
                f"[{self.provider.upper()}] Timeout after {timeout}s"
            )
            raise
        except Exception as e:
            logger.error(f"[{self.provider.upper()}] API Error: {e}")
            raise

    async def _execute_legacy_retry_call(self, prompt: str, timeout: float) -> str:
        """레거시 호환: 주입된 클라이언트 기반 단순 재시도."""
        if not self._client:
            raise RuntimeError("Retry strategy not initialized")
        if not hasattr(self._client, "models") or not hasattr(self._client.models, "generate_content"):
            raise RuntimeError("Retry strategy not initialized")

        model_name = getattr(app_config, "GEMINI_MODEL", "gemini-2.0-flash-lite")
        max_retries = RetryConfig.MAX_RETRIES

        for attempt in range(max_retries):
            try:
                response = self._client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                )
                return getattr(response, "text", "")
            except asyncio.TimeoutError:
                if attempt >= max_retries - 1:
                    raise
            except Exception as error:
                is_retryable = RetryConfig.is_retryable_error(str(error))
                if not is_retryable or attempt >= max_retries - 1:
                    raise

            await asyncio.sleep(RetryConfig.compute_wait_time(attempt))

        raise RuntimeError("LLM call failed after retries")
