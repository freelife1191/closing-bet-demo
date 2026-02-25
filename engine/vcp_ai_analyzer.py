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
import re
from typing import List, Dict, Optional

from engine.config import app_config
from engine.vcp_ai_analyzer_helpers import (
    build_vcp_rule_based_recommendation,
    build_perplexity_request,
    build_vcp_prompt,
    classify_perplexity_error,
    extract_openai_message_text,
    extract_perplexity_response_text,
    is_perplexity_quota_exceeded,
    parse_json_response,
)
from engine.vcp_ai_provider_init_helpers import (
    init_gemini_client,
    init_gpt_client,
    init_zai_client,
    normalize_provider_list,
    normalize_provider_name,
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
ZAI_FALLBACK_MODEL_CHAIN = [
    "glm-4.5-Flash",
    "glm-4.6V-Flash",
]


class VCPMultiAIAnalyzer:
    """VCP 시그널 멀티 AI 분석기 (Gemini + GPT/Perplexity 동시 분석)"""

    def __init__(self):
        self.providers = normalize_provider_list(app_config.VCP_AI_PROVIDERS)
        self.second_provider = normalize_provider_name(app_config.VCP_SECOND_PROVIDER)

        logger.info(f"VCP MultiAI 분석기 초기화: {self.providers}")

        self.gemini_client = init_gemini_client(self.providers, app_config, logger)
        self.gpt_client = init_gpt_client(self.providers, app_config, logger)
        self.zai_client = init_zai_client(app_config, logger)

        # Perplexity - httpx 직접 사용하므로 클라이언트 초기화 불필요
        self.perplexity_client = None
        self.perplexity_disabled = resolve_perplexity_disabled(
            providers=self.providers,
            second_provider=self.second_provider,
            has_api_key=bool(app_config.PERPLEXITY_API_KEY),
            logger=logger,
        )
        self.perplexity_quota_exhausted = False
        self.perplexity_blocked_reason: str | None = None
        self.perplexity_fallback_providers = self._build_perplexity_fallback_chain()
        self.gemini_blocked_models: set[str] = set()
        self.zai_blocked_models: set[str] = set()
    
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

        blocked_models = getattr(self, "gemini_blocked_models", None)
        if not isinstance(blocked_models, set):
            blocked_models = set()
            self.gemini_blocked_models = blocked_models

        resolved_prompt = prompt or self._build_vcp_prompt(stock_name, stock_data)
        base_delay = 2
        model_chain = [model for model in GEMINI_RETRY_MODEL_CHAIN if model not in blocked_models]
        if not model_chain:
            logger.warning("[Gemini] 사용 가능한 모델이 없습니다. 모든 모델이 세션에서 제외되었습니다.")
            return None
        max_retries = len(model_chain) - 1

        def _extract_status_code(error: Exception) -> int | None:
            for attr in ("status_code", "http_status", "code"):
                value = getattr(error, attr, None)
                if isinstance(value, int) and 100 <= value <= 599:
                    return value
            response_obj = getattr(error, "response", None)
            status_code = getattr(response_obj, "status_code", None)
            if isinstance(status_code, int) and 100 <= status_code <= 599:
                return status_code
            match = re.search(r"\b([45][0-9]{2})\b", str(error))
            if match:
                try:
                    return int(match.group(1))
                except (TypeError, ValueError):
                    return None
            return None

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
                status_code = _extract_status_code(e)
                # 429: Rate Limit, 503/500: Server Error/Overloaded
                retry_conditions = ['429', 'resource exhausted', 'quota exceeded', '503', '502', '500', 'overloaded']
                is_model_unavailable = (
                    status_code in {429, 503}
                    or "resource exhausted" in error_msg
                )
                if is_model_unavailable:
                    if current_model not in blocked_models:
                        blocked_models.add(current_model)
                    logger.warning(
                        f"[Gemini] {stock_name} {current_model} 모델을 429/503 계열 오류로 세션에서 제외합니다."
                    )

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
            second_provider=getattr(
                self,
                "second_provider",
                normalize_provider_name(app_config.VCP_SECOND_PROVIDER),
            ),
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
        blocked_reason = str(getattr(self, "perplexity_blocked_reason", "") or "").strip()
        if blocked_reason:
            return await self._fallback_from_perplexity(
                stock_name=stock_name,
                stock_data=stock_data,
                prompt=resolved_prompt,
                reason=f"Perplexity blocked (session cache: {blocked_reason})",
            )
        if getattr(self, "perplexity_quota_exhausted", False):
            return await self._fallback_from_perplexity(
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
            perplexity_timeout = float(getattr(app_config, "VCP_PERPLEXITY_API_TIMEOUT", 60))
            async with httpx.AsyncClient(timeout=perplexity_timeout) as client:
                for attempt in range(max_retries + 1):
                    response = await client.post(url, headers=headers, json=payload)

                    if response.status_code == 429:
                        self.perplexity_quota_exhausted = True
                        self.perplexity_blocked_reason = "429"
                        logger.warning(
                            f"[Perplexity] {stock_name} 429 응답 감지. 세션에서 Perplexity 모델을 제외하고 fallback 전환."
                        )
                        return await self._fallback_from_perplexity(
                            stock_name=stock_name,
                            stock_data=stock_data,
                            prompt=resolved_prompt,
                            reason="Perplexity 429",
                        )
                    if response.status_code == 503:
                        self.perplexity_quota_exhausted = True
                        self.perplexity_blocked_reason = "503"
                        logger.warning(
                            f"[Perplexity] {stock_name} 503 응답 감지. 세션에서 Perplexity 모델을 제외하고 fallback 전환."
                        )
                        return await self._fallback_from_perplexity(
                            stock_name=stock_name,
                            stock_data=stock_data,
                            prompt=resolved_prompt,
                            reason="Perplexity 503",
                        )

                    if response.status_code != 200:
                        if is_perplexity_quota_exceeded(response.status_code, response.text):
                            logger.warning(
                                "[Perplexity] 할당량 소진 또는 크레딧 제한 감지 "
                                f"({response.status_code}). 보조 Provider fallback 수행"
                            )
                            self.perplexity_quota_exhausted = True
                            return await self._fallback_from_perplexity(
                                stock_name=stock_name,
                                stock_data=stock_data,
                                prompt=resolved_prompt,
                                reason=f"Perplexity quota-like response ({response.status_code})",
                            )

                        logger.error(f"[Perplexity] API Error: {response.status_code} - {response.text[:200]}")
                        error_type = classify_perplexity_error(response.status_code, response.text)
                        if error_type == "quota":
                            logger.warning(
                                "[Perplexity] 할당량 초과로 판단되어 fallback 수행 "
                                f"({response.status_code})"
                            )
                            self.perplexity_quota_exhausted = True
                            return await self._fallback_from_perplexity(
                                stock_name=stock_name,
                                stock_data=stock_data,
                                prompt=resolved_prompt,
                                reason=f"Perplexity quota exceeded ({response.status_code})",
                            )

                        if error_type == "auth_or_quota":
                            logger.warning(
                                "[Perplexity] 401/403 원인이 인증 또는 할당량 소진으로 모호합니다. "
                                "할당량 소진 가능성을 고려해 fallback 수행합니다."
                            )
                            self.perplexity_quota_exhausted = True
                            return await self._fallback_from_perplexity(
                                stock_name=stock_name,
                                stock_data=stock_data,
                                prompt=resolved_prompt,
                                reason=f"Perplexity ambiguous 401/403 ({response.status_code})",
                            )

                        if error_type == "auth":
                            logger.warning(
                                "[Perplexity] 인증 오류(401/403) 감지. "
                                "이번 세션에서는 Perplexity 직접 호출을 중단하고 fallback으로 전환합니다."
                            )
                            self.perplexity_quota_exhausted = True
                            return await self._fallback_from_perplexity(
                                stock_name=stock_name,
                                stock_data=stock_data,
                                prompt=resolved_prompt,
                                reason=f"Perplexity auth error ({response.status_code})",
                            )
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
        zai_client = getattr(self, "zai_client", None)
        if not zai_client:
            return None

        try:
            resolved_prompt = prompt or self._build_vcp_prompt(stock_name, stock_data)
            primary_model = str(app_config.ZAI_MODEL or "").strip()
            blocked_models = getattr(self, "zai_blocked_models", None)
            if not isinstance(blocked_models, set):
                blocked_models = set()
                self.zai_blocked_models = blocked_models
            model_chain: list[str] = []
            seen_models: set[str] = set()
            for candidate in [primary_model, *ZAI_FALLBACK_MODEL_CHAIN]:
                model_name = str(candidate or "").strip()
                if not model_name:
                    continue
                key = model_name.lower()
                if key in seen_models or key in blocked_models:
                    continue
                seen_models.add(key)
                model_chain.append(model_name)
            if not model_chain:
                logger.warning("[Z.ai] 사용 가능한 모델이 없습니다. 모든 모델이 세션에서 제외되었습니다.")
                fallback_result = build_vcp_rule_based_recommendation(
                    stock_name=stock_name,
                    stock_data=stock_data,
                )
                logger.warning(
                    f"[Z.ai] {stock_name} 모델 체인 소진으로 규칙 기반 fallback 사용: "
                    f"{fallback_result.get('action')} ({fallback_result.get('confidence')}%)"
                )
                return fallback_result

            max_parse_attempts = 2
            request_timeout = float(getattr(app_config, "VCP_ZAI_API_TIMEOUT", 180))
            last_response_text = ""
            last_error: Exception | None = None

            def _extract_status_code(error: Exception) -> int | None:
                for attr in ("status_code", "http_status"):
                    value = getattr(error, attr, None)
                    if isinstance(value, int) and 100 <= value <= 599:
                        return value
                response_obj = getattr(error, "response", None)
                status_code = getattr(response_obj, "status_code", None)
                if isinstance(status_code, int) and 100 <= status_code <= 599:
                    return status_code
                match = re.search(r"\b([45][0-9]{2})\b", str(error))
                if match:
                    try:
                        return int(match.group(1))
                    except (TypeError, ValueError):
                        return None
                return None

            def _is_failure_response(error: Exception) -> bool:
                status_code = _extract_status_code(error)
                if status_code is None:
                    return False
                return 400 <= status_code <= 599

            for model_idx, model in enumerate(model_chain):
                should_try_next_model = False

                for attempt in range(max_parse_attempts):
                    start = time.time()

                    def _call(messages: list[dict[str, str]], use_json_mode: bool, max_tokens: int = 500):
                        request_args = {
                            "model": model,
                            "messages": messages,
                            "temperature": 0.0,
                            "max_tokens": max_tokens,
                            "timeout": request_timeout,
                        }
                        if use_json_mode:
                            request_args["response_format"] = {"type": "json_object"}

                        try:
                            response = zai_client.chat.completions.create(**request_args)
                        except Exception as error:
                            message = str(error).lower()
                            if use_json_mode and "response_format" in message:
                                request_args.pop("response_format", None)
                                response = zai_client.chat.completions.create(**request_args)
                            else:
                                raise

                        choices = getattr(response, "choices", None)
                        if not choices and isinstance(response, dict):
                            choices = response.get("choices")
                        if not choices:
                            return ""

                        first_choice = choices[0]
                        message_obj = getattr(first_choice, "message", None)
                        if message_obj is None and isinstance(first_choice, dict):
                            message_obj = first_choice.get("message")
                        if message_obj is None:
                            return ""

                        content = getattr(message_obj, "content", None)
                        if content is None and isinstance(message_obj, dict):
                            content = message_obj.get("content")
                        response_text = extract_openai_message_text(content)
                        if response_text and response_text.strip():
                            return response_text

                        reasoning_content = getattr(message_obj, "reasoning_content", None)
                        if reasoning_content is None and isinstance(message_obj, dict):
                            reasoning_content = message_obj.get("reasoning_content")
                        response_text = extract_openai_message_text(reasoning_content)
                        if response_text and response_text.strip():
                            return response_text

                        return ""

                    primary_messages = [
                        {
                            "role": "system",
                            "content": (
                                "You are a technical analyst. "
                                "Return exactly one compact JSON object and nothing else. "
                                "Required keys: action, confidence, reason. "
                                "action must be BUY, SELL, or HOLD. "
                                "confidence must be an integer 0-100. "
                                "reason must be a short Korean sentence."
                            ),
                        },
                        {"role": "user", "content": resolved_prompt},
                    ]
                    try:
                        response_text = await asyncio.to_thread(_call, primary_messages, attempt == 0)
                        last_response_text = str(response_text or "")

                        elapsed = time.time() - start
                        logger.debug(
                            f"[Z.ai] {stock_name} 분석 완료 "
                            f"(model={model}, {elapsed:.2f}s, attempt={attempt+1}, timeout={request_timeout:.0f}s)"
                        )

                        result = self._parse_json_response(last_response_text)
                        if result:
                            return result

                        # 1차 응답이 JSON이 아닐 경우, 동일 모델에 "JSON 변환" 보정 요청을 추가로 수행한다.
                        if last_response_text.strip():
                            repair_input = last_response_text.strip()
                            if len(repair_input) > 4000:
                                repair_input = repair_input[:4000]

                            repair_messages = [
                                {
                                    "role": "system",
                                    "content": (
                                        "You convert stock analysis text into strict JSON only. "
                                        "Return exactly one JSON object with keys: action, confidence, reason. "
                                        "action must be BUY, SELL, or HOLD. confidence must be integer 0-100."
                                    ),
                                },
                                {
                                    "role": "user",
                                    "content": (
                                        "Previous model output:\n"
                                        f"{repair_input}\n\n"
                                        "Return only valid JSON."
                                    ),
                                },
                            ]
                            repaired_text = await asyncio.to_thread(_call, repair_messages, True, 250)
                            repaired_result = self._parse_json_response(str(repaired_text or ""))
                            if repaired_result:
                                logger.info(
                                    f"[Z.ai] {stock_name} JSON 변환 보정 성공 "
                                    f"(model={model}, attempt={attempt+1})"
                                )
                                return repaired_result

                        if attempt < max_parse_attempts - 1:
                            logger.warning(
                                f"[Z.ai] JSON 파싱 실패 for {stock_name}. 재시도합니다 "
                                f"(model={model}, {attempt+1}/{max_parse_attempts-1})"
                            )
                    except Exception as error:
                        last_error = error
                        elapsed = time.time() - start
                        status_code = _extract_status_code(error)
                        is_model_unavailable = status_code in {429, 503}

                        if is_model_unavailable:
                            blocked_models.add(str(model).lower())
                            if model_idx < len(model_chain) - 1:
                                next_model = model_chain[model_idx + 1]
                                logger.warning(
                                    f"[Z.ai] {stock_name} 모델 전환(429/503): "
                                    f"{model} -> {next_model} (status={status_code})"
                                )
                                should_try_next_model = True
                            else:
                                logger.warning(
                                    f"[Z.ai] {stock_name} 마지막 모델 {model}이(가) 429/503 실패하여 "
                                    "추가 모델 전환 없이 fallback으로 종료합니다."
                                )
                            break

                        if attempt < max_parse_attempts - 1:
                            logger.warning(
                                f"[Z.ai] {stock_name} 호출 실패({error}) -> 재시도 "
                                f"(model={model}, {attempt+1}/{max_parse_attempts-1}, "
                                f"elapsed={elapsed:.2f}s, timeout={request_timeout:.0f}s)"
                            )
                            await asyncio.sleep(1.0 + attempt)
                            continue

                        if _is_failure_response(error) and model_idx < len(model_chain) - 1:
                            next_model = model_chain[model_idx + 1]
                            reason = f"status={status_code}" if status_code is not None else str(error)
                            logger.warning(
                                f"[Z.ai] {stock_name} 모델 실패 응답으로 모델 전환 "
                                f"({model} -> {next_model}, reason={reason})"
                            )
                            should_try_next_model = True
                            break

                        logger.error(
                            f"[Z.ai] {stock_name} 호출 실패(최종): {error} "
                            f"(model={model}, elapsed={elapsed:.2f}s, timeout={request_timeout:.0f}s)"
                        )

                if should_try_next_model:
                    continue
                break

            logger.warning(
                f"[Z.ai] JSON 파싱 실패 for {stock_name}. Raw Output: {last_response_text[:300]}..."
            )
            if last_error is not None:
                logger.warning(
                    f"[Z.ai] {stock_name} API 오류 이후 규칙 기반 fallback 사용: {last_error}"
                )
            fallback_result = build_vcp_rule_based_recommendation(
                stock_name=stock_name,
                stock_data=stock_data,
            )
            logger.warning(
                f"[Z.ai] {stock_name} 규칙 기반 fallback 사용: "
                f"{fallback_result.get('action')} ({fallback_result.get('confidence')}%)"
            )
            return fallback_result
        except Exception as e:
            logger.error(f"[Z.ai] {stock_name} 분석 실패(예외): {e}")
            fallback_result = build_vcp_rule_based_recommendation(
                stock_name=stock_name,
                stock_data=stock_data,
            )
            logger.warning(
                f"[Z.ai] {stock_name} 예외 발생으로 규칙 기반 fallback 사용: "
                f"{fallback_result.get('action')} ({fallback_result.get('confidence')}%)"
            )
            return fallback_result

    def _build_perplexity_fallback_chain(self, providers: List[str] | None = None) -> List[str]:
        """Perplexity 실패 시 사용할 보조 Provider 순서를 구성한다."""
        source = providers if providers is not None else getattr(self, "providers", [])
        normalized_source = [normalize_provider_name(provider) for provider in source]
        chain: list[str] = []
        # 요구사항: Perplexity 실패 시 다음 Provider는 Z.ai를 우선 시도
        if "zai" in normalized_source:
            chain.append("zai")
        if "gpt" in normalized_source:
            chain.append("gpt")
        for provider in source:
            key = normalize_provider_name(provider)
            if key in {"gpt", "zai"} and key not in chain:
                chain.append(key)
        return chain

    def _resolve_perplexity_fallback_providers(self) -> List[str]:
        providers = getattr(self, "providers", None)
        allowed_chain: list[str] = []
        if isinstance(providers, list) and providers:
            allowed_chain = self._build_perplexity_fallback_chain(providers)
        allowed_set = set(allowed_chain)

        configured = getattr(self, "perplexity_fallback_providers", None)
        if isinstance(configured, list) and configured:
            if allowed_set:
                return [provider for provider in configured if provider in allowed_set]
            return []

        if allowed_chain:
            return allowed_chain

        # fallback 대상은 반드시 VCP_AI_PROVIDERS 설정값 기반으로만 결정한다.
        return []

    async def _fallback_from_perplexity(
        self,
        *,
        stock_name: str,
        stock_data: Dict,
        prompt: str,
        reason: str,
    ) -> Optional[Dict]:
        """Perplexity 실패 시 설정된 보조 Provider(gpt/zai)로 폴백 분석."""
        fallback_providers = self._resolve_perplexity_fallback_providers()
        if not fallback_providers:
            logger.error(
                f"[Perplexity fallback] {stock_name} 폴백 불가: "
                f"VCP_AI_PROVIDERS에 gpt/z.ai가 없거나 클라이언트 미초기화 ({reason})"
            )
            return None

        for provider in fallback_providers:
            if provider == "zai":
                if not getattr(self, "zai_client", None):
                    logger.warning(f"[Perplexity->Z.ai fallback] {stock_name} 건너뜀: Z.ai 미초기화")
                    continue
                logger.warning(f"[Perplexity->Z.ai fallback] {stock_name} 사유: {reason}")
                result = await self._analyze_with_zai(stock_name, stock_data, prompt)
            elif provider == "gpt":
                if not getattr(self, "gpt_client", None):
                    logger.warning(f"[Perplexity->GPT fallback] {stock_name} 건너뜀: GPT 미초기화")
                    continue
                logger.warning(f"[Perplexity->GPT fallback] {stock_name} 사유: {reason}")
                result = await self._analyze_with_gpt(stock_name, stock_data, prompt)
            else:
                continue

            if result:
                return result

        logger.error(f"[Perplexity fallback] {stock_name} 폴백 실패: 사용 가능한 보조 Provider 응답 없음")
        return None

    async def _fallback_to_zai(
        self,
        *,
        stock_name: str,
        stock_data: Dict,
        prompt: str,
        reason: str,
    ) -> Optional[Dict]:
        """하위 호환용 Z.ai 직접 폴백."""
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
        if getattr(self, "zai_client", None):
            available.append('zai')
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
