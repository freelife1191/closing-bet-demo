#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VCP AI Analyzer - 멀티 AI 분석 (Gemini + GPT/Perplexity 지원)
"""
import os
import logging
import time
import asyncio
import httpx
import random
from typing import List, Dict, Optional

from engine.config import app_config
from engine.vcp_ai_analyzer_helpers import (
    build_perplexity_request,
    build_vcp_prompt,
    extract_perplexity_response_text,
    is_perplexity_quota_exceeded,
    parse_json_response,
)
from engine.vcp_ai_provider_init_helpers import (
    init_gemini_client,
    init_gpt_client,
    init_zai_client,
    resolve_perplexity_disabled,
)
from engine.vcp_ai_orchestration_helpers import (
    analyze_batch_with_limit as analyze_batch_with_limit_impl,
    orchestrate_stock_analysis as orchestrate_stock_analysis_impl,
)

logger = logging.getLogger(__name__)

GEMINI_RETRY_MODEL_CHAIN = [
    "gemini-2.0-flash-lite",
    "gemini-2.5-flash-lite",
    "gemini-2.0-flash",
    "gemini-2.5-flash",
    "gemini-3-flash-preview",
]


class VCPMultiAIAnalyzer:
    """VCP 시그널 멀티 AI 분석기 (Gemini + GPT/Perplexity 동시 분석)"""

    def __init__(self):
        self.providers = app_config.VCP_AI_PROVIDERS

        logger.info(f"VCP MultiAI 분석기 초기화: {self.providers}")

        self.gemini_client = init_gemini_client(self.providers, app_config, logger)
        self.gpt_client = init_gpt_client(self.providers, app_config, logger)
        self.zai_client = init_zai_client(app_config, logger)

        # Perplexity - httpx 직접 사용하므로 클라이언트 초기화 불필요
        self.perplexity_client = None
        self.perplexity_disabled = resolve_perplexity_disabled(
            providers=self.providers,
            second_provider=app_config.VCP_SECOND_PROVIDER,
            has_api_key=bool(app_config.PERPLEXITY_API_KEY),
            logger=logger,
        )
        self.perplexity_quota_exhausted = False
    
    def _build_vcp_prompt(self, stock_name: str, stock_data: Dict) -> str:
        """VCP 분석용 프롬프트 생성"""
        return build_vcp_prompt(stock_name, stock_data)
    
    async def _analyze_with_gemini(
        self,
        stock_name: str,
        stock_data: Dict,
        prompt: str | None = None,
    ) -> Optional[Dict]:
        """Gemini로 분석 (Retry Logic 적용)"""
        if not self.gemini_client:
            return None
        
        resolved_prompt = prompt or self._build_vcp_prompt(stock_name, stock_data)
        base_delay = 2
        model_chain = list(GEMINI_RETRY_MODEL_CHAIN)
        max_retries = len(model_chain) - 1

        for attempt, current_model in enumerate(model_chain):
            try:
                start = time.time()
                
                # Gemini API 호출 (동기 호출을 executor로 실행)
                def _call():
                    response = self.gemini_client.models.generate_content(
                        model=current_model,
                        contents=resolved_prompt
                    )
                    return response.text

                response_text = await asyncio.to_thread(_call)
                
                elapsed = time.time() - start
                logger.debug(f"[Gemini] {stock_name} 분석 완료 ({current_model}, {elapsed:.2f}s)")
                
                # JSON 파싱
                result = self._parse_json_response(response_text)
                if result:
                    return result

                if attempt < max_retries:
                    delay = base_delay * (2 ** attempt) + (random.randint(0, 1000) / 1000)
                    next_model = model_chain[attempt + 1]
                    logger.warning(
                        f"[Gemini] {stock_name} JSON 파싱 실패 -> {delay:.2f}초 후 재시도 "
                        f"(모델 전환: {current_model} -> {next_model}, {attempt+1}/{max_retries})"
                    )
                    await asyncio.sleep(delay)
                    continue

                logger.error(f"[Gemini] {stock_name} 분석 실패 (Final): 유효한 JSON 응답을 받지 못함")
                return result
                
            except Exception as e:
                error_msg = str(e).lower()
                # 429: Rate Limit, 503/500: Server Error/Overloaded
                retry_conditions = ['429', 'resource exhausted', 'quota exceeded', '503', '502', '500', 'overloaded']

                if attempt < max_retries:
                    delay = base_delay * (2 ** attempt) + (random.randint(0, 1000) / 1000)
                    next_model = model_chain[attempt + 1]
                    is_retryable = any(c in error_msg for c in retry_conditions)
                    reason = "429/503 계열 오류" if is_retryable else "분석 실패"

                    log_msg = (
                        f"[Gemini] {stock_name} {reason} ({error_msg[:50]}) -> {delay:.2f}초 후 재시도 "
                        f"(모델 전환: {current_model} -> {next_model})"
                    )
                    logger.warning(f"{log_msg} ({attempt+1}/{max_retries})")
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"[Gemini] {stock_name} 분석 실패 (Final): {e}")
                    return None
        return None
    
    async def _analyze_with_gpt(
        self,
        stock_name: str,
        stock_data: Dict,
        prompt: str | None = None,
    ) -> Optional[Dict]:
        """GPT로 분석"""
        if not self.gpt_client:
            return None
        
        try:
            resolved_prompt = prompt or self._build_vcp_prompt(stock_name, stock_data)
            model = app_config.VCP_GPT_MODEL
            
            start = time.time()
            
            # GPT API 호출 (동기 호출을 executor로 실행)
            def _call():
                response = self.gpt_client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": "You are a technical analyst researcher. Respond ONLY in JSON format."},
                        {"role": "user", "content": resolved_prompt}
                    ],
                    temperature=0.7,
                    max_tokens=500
                )
                return response.choices[0].message.content

            # 호출당 Executor 생성 비용을 줄이기 위해 to_thread 사용
            response_text = await asyncio.to_thread(_call)
            
            elapsed = time.time() - start
            logger.debug(f"[GPT] {stock_name} 분석 완료 ({elapsed:.2f}s)")
            
            # JSON 파싱
            result = self._parse_json_response(response_text)
            return result
            
        except Exception as e:
            logger.error(f"[GPT] {stock_name} 분석 실패: {e}")
            return None
    
    def _parse_json_response(self, text: str) -> Optional[Dict]:
        """LLM 응답에서 JSON 추출"""
        return parse_json_response(text)
    
    async def analyze_stock(self, stock_name: str, stock_data: Dict) -> Dict:
        """단일 종목 멀티 AI 분석 (Gemini + GPT/Perplexity 동시 실행 - 병렬 처리)"""
        return await orchestrate_stock_analysis_impl(
            stock_name=stock_name,
            stock_data=stock_data,
            providers=self.providers,
            second_provider=app_config.VCP_SECOND_PROVIDER,
            perplexity_disabled=self.perplexity_disabled,
            build_prompt_fn=self._build_vcp_prompt,
            analyze_with_gemini_fn=self._analyze_with_gemini,
            analyze_with_gpt_fn=self._analyze_with_gpt,
            analyze_with_perplexity_fn=self._analyze_with_perplexity,
            logger=logger,
        )
    
    async def _analyze_with_perplexity(
        self,
        stock_name: str,
        stock_data: Dict,
        prompt: str | None = None,
    ) -> Optional[Dict]:
        """Perplexity로 분석 (httpx 사용 - Retry Logic 적용)"""
        if not app_config.PERPLEXITY_API_KEY or getattr(self, "perplexity_disabled", False):
            return None

        max_retries = 3
        base_delay = 2

        resolved_prompt = prompt or self._build_vcp_prompt(stock_name, stock_data)
        if getattr(self, "perplexity_quota_exhausted", False):
            return await self._fallback_to_zai(
                stock_name=stock_name,
                stock_data=stock_data,
                prompt=resolved_prompt,
                reason="Perplexity quota exhausted (session cache)",
            )

        model = app_config.VCP_PERPLEXITY_MODEL
        url, headers, payload = build_perplexity_request(
            prompt=resolved_prompt,
            api_key=app_config.PERPLEXITY_API_KEY,
            model=model,
        )

        start = time.time()
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                for attempt in range(max_retries + 1):
                    response = await client.post(url, headers=headers, json=payload)

                    if response.status_code == 429:
                        if attempt < max_retries:
                            delay = base_delay * (2 ** attempt) + (random.randint(0, 1000) / 1000)
                            logger.warning(
                                f"[Perplexity] {stock_name} 429 Error. Retrying in {delay:.2f}s... "
                                f"({attempt+1}/{max_retries})"
                            )
                            await asyncio.sleep(delay)
                            continue
                        logger.error(f"[Perplexity] Max retries exceeded for {stock_name}")
                        self.perplexity_quota_exhausted = True
                        return await self._fallback_to_zai(
                            stock_name=stock_name,
                            stock_data=stock_data,
                            prompt=resolved_prompt,
                            reason="Perplexity repeated 429",
                        )

                    if response.status_code != 200:
                        if is_perplexity_quota_exceeded(response.status_code, response.text):
                            logger.warning(
                                "[Perplexity] 할당량 소진 또는 크레딧 제한 감지 "
                                f"({response.status_code}). Z.ai fallback 수행"
                            )
                            self.perplexity_quota_exhausted = True
                            return await self._fallback_to_zai(
                                stock_name=stock_name,
                                stock_data=stock_data,
                                prompt=resolved_prompt,
                                reason=f"Perplexity quota-like response ({response.status_code})",
                            )

                        logger.error(f"[Perplexity] API Error: {response.status_code} - {response.text[:200]}")
                        if response.status_code in [401, 403]:
                            logger.warning("[Perplexity] 인증 오류 발생. 이번 세션에서 Perplexity 분석을 비활성화합니다.")
                            self.perplexity_disabled = True
                        return None

                    response_json = response.json()
                    response_text = extract_perplexity_response_text(response_json)
                    if not response_text:
                        logger.error(f"[Perplexity] 응답 파싱 실패: {response_json}")
                        return None

                    elapsed = time.time() - start
                    logger.debug(f"[Perplexity] {stock_name} 분석 완료 ({elapsed:.2f}s)")
                    result = self._parse_json_response(response_text)
                    if not result:
                        logger.warning(f"[Perplexity] JSON 파싱 실패 for {stock_name}. Raw Output: {response_text[:300]}...")
                    return result
        except Exception as e:
            logger.error(f"[Perplexity] {stock_name} 분석 실패: {e}")
            return None
        return None

    async def _analyze_with_zai(
        self,
        stock_name: str,
        stock_data: Dict,
        prompt: str | None = None,
    ) -> Optional[Dict]:
        """Z.ai(OpenAI 호환)로 분석."""
        if not getattr(self, "zai_client", None):
            return None

        try:
            resolved_prompt = prompt or self._build_vcp_prompt(stock_name, stock_data)
            model = app_config.ZAI_MODEL

            start = time.time()

            def _call():
                response = self.zai_client.chat.completions.create(
                    model=model,
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "You are a technical analyst researcher. "
                                "Respond ONLY in JSON format."
                            ),
                        },
                        {"role": "user", "content": resolved_prompt},
                    ],
                    temperature=0.2,
                    max_tokens=500,
                )

                choices = getattr(response, "choices", None)
                if not choices:
                    return ""
                first_choice = choices[0]
                message = getattr(first_choice, "message", None)
                return getattr(message, "content", "")

            response_text = await asyncio.to_thread(_call)
            elapsed = time.time() - start
            logger.debug(f"[Z.ai] {stock_name} 분석 완료 ({elapsed:.2f}s)")

            result = self._parse_json_response(response_text)
            if not result:
                logger.warning(
                    f"[Z.ai] JSON 파싱 실패 for {stock_name}. Raw Output: {str(response_text)[:300]}..."
                )
            return result
        except Exception as e:
            logger.error(f"[Z.ai] {stock_name} 분석 실패: {e}")
            return None

    async def _fallback_to_zai(
        self,
        *,
        stock_name: str,
        stock_data: Dict,
        prompt: str,
        reason: str,
    ) -> Optional[Dict]:
        """Perplexity 실패 시 Z.ai로 폴백 분석."""
        if not getattr(self, "zai_client", None):
            logger.error(
                f"[Perplexity->Z.ai fallback] {stock_name} 폴백 불가: Z.ai 클라이언트 미초기화 ({reason})"
            )
            return None

        logger.warning(f"[Perplexity->Z.ai fallback] {stock_name} 사유: {reason}")
        return await self._analyze_with_zai(stock_name, stock_data, prompt)
    
    async def analyze_batch(self, stocks: List[Dict]) -> Dict[str, Dict]:
        """여러 종목 일괄 분석 (완전 병렬 처리 + 진행률 로그)"""
        total = len(stocks)
        concurrency = getattr(app_config, 'ANALYSIS_LLM_CONCURRENCY', 2)
        logger.info(f"VCP AI 일괄 분석 시작: 총 {total}개 종목 (Concurrency: {concurrency})")

        results, success_count = await analyze_batch_with_limit_impl(
            stocks=stocks,
            concurrency=concurrency,
            analyze_stock_fn=self.analyze_stock,
            logger=logger,
        )
        logger.info(f"VCP AI 일괄 분석 종료: 성공 {success_count}/{total}건")
        return results
    
    def get_available_providers(self) -> List[str]:
        """현재 사용 가능한 AI 제공자 목록"""
        available = []
        if self.gemini_client:
            available.append('gemini')
        if self.gpt_client:
            available.append('gpt')
        if app_config.PERPLEXITY_API_KEY and not self.perplexity_disabled:
            available.append('perplexity')
        return available


# 싱글톤 인스턴스
_vcp_analyzer = None

def get_vcp_analyzer() -> VCPMultiAIAnalyzer:
    """VCP Analyzer 싱글톤 인스턴스 반환"""
    global _vcp_analyzer
    if _vcp_analyzer is None:
        _vcp_analyzer = VCPMultiAIAnalyzer()
    return _vcp_analyzer
