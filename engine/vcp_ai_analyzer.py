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
from engine.llm_analyzer_retry import GEMINI_RETRY_MODEL_CHAIN
from engine.vcp_ai_analyzer_helpers import (
    build_vcp_rule_based_recommendation,
    build_perplexity_request,
    build_vcp_prompt,
    classify_perplexity_error,
    extract_openai_message_text,
    extract_perplexity_response_text,
    is_prompt_echo_response,
    is_low_quality_recommendation,
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

ZAI_FALLBACK_MODEL_CHAIN = [
    "glm-4.6V-Flash",
]
GPT_FALLBACK_TRIGGER_STATUS_CODES = {429, 503}
GPT_RETRYABLE_STATUS_CODES = {408, 409, 429, 500, 502, 503, 504}
GPT_RETRYABLE_KEYWORDS = (
    "timeout",
    "timed out",
    "temporarily unavailable",
    "server error",
    "connection reset",
    "connection aborted",
    "rate limit",
    "too many requests",
    "overloaded",
    "resource exhausted",
    "quota exceeded",
)
GPT_CREDIT_EXHAUSTED_KEYWORDS = (
    "insufficient_quota",
    "credit exhausted",
    "quota exceeded",
    "quota exhausted",
    "out of credits",
    "billing",
    "insufficient balance",
    "exceeded your current quota",
)

_ZAI_ASSISTANT_PREFILL = '{"action":"'


def _restore_zai_prefill(response_text: str) -> str:
    """assistant prefill로 시작 토큰을 강제했을 때 응답이 prefix를 생략하면 복원한다."""
    if not response_text:
        return response_text
    stripped = response_text.lstrip()
    if stripped.startswith("{"):
        return response_text
    return _ZAI_ASSISTANT_PREFILL + response_text


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
        self.gpt_quota_exhausted = False
        self.gpt_blocked_reason: str | None = None
    
    def _build_vcp_prompt(self, stock_name: str, stock_data: Dict) -> str:
        """VCP 분석용 프롬프트 생성"""
        return build_vcp_prompt(stock_name, stock_data)

    def _build_gpt_system_prompt(self) -> str:
        """GPT용 VCP 시스템 프롬프트."""
        return (
            "당신은 한국 주식 VCP(Volatility Contraction Pattern) 전문 기술적 분석가입니다. "
            "제공된 종목 데이터만 근거로 수급과 패턴을 평가하고, 연구/교육 목적의 객관적 의견만 제시하십시오. "
            "반드시 JSON 객체 1개만 출력하고 코드블록, 머리말, 설명문, 마크다운을 금지합니다. "
            "JSON 외 텍스트를 단 한 글자도 출력하지 말고 반드시 '{'로 시작해 '}'로 끝내십시오. "
            "필수 키는 action, confidence, reason 입니다. "
            "action은 BUY, SELL, HOLD 중 하나여야 합니다. "
            "action must be BUY, SELL, or HOLD. "
            "action에는 설명 문장을 넣지 말고 정확히 BUY, SELL, HOLD 중 하나만 넣으십시오. "
            "confidence는 0-100 사이 정수여야 합니다. "
            "confidence must be an integer between 0 and 100. "
            "reason은 반드시 한국어 2문장 이상, 최소 90자 이상으로 작성하고 "
            "[핵심 투자 포인트], [리스크 요인], [종합 의견] 구조를 우선 사용하십시오. "
            "수급 방향이 최근 5일과 오늘 사이에서 엇갈리면 오늘 변화를 더 중요하게 해석하십시오. "
            "Return exactly one compact JSON object and nothing else."
        )

    def _build_gpt_repair_system_prompt(self) -> str:
        """GPT 응답 복구용 시스템 프롬프트."""
        return (
            "당신은 한국 주식 분석 텍스트를 strict JSON으로 정규화하는 변환기입니다. "
            "반드시 JSON 객체 1개만 출력하고 JSON 외 텍스트는 절대 출력하지 마십시오. "
            "반드시 '{'로 시작해 '}'로 끝내십시오. "
            "필수 키는 action, confidence, reason 입니다. "
            "action은 BUY, SELL, HOLD 중 하나여야 합니다. "
            "action에는 설명 문장을 넣지 말고 정확히 BUY, SELL, HOLD 중 하나만 넣으십시오. "
            "confidence는 0-100 사이 정수여야 합니다. "
            "reason은 반드시 한국어 2문장 이상, 최소 90자 이상으로 작성하고 "
            "[핵심 투자 포인트], [리스크 요인], [종합 의견] 구조를 우선 사용하십시오. "
            "Return exactly one JSON object with keys action, confidence, reason."
        )

    def _extract_status_code(self, error: Exception) -> int | None:
        """예외 객체에서 HTTP status code를 추출한다."""
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

    def _is_retryable_gpt_error(self, error_msg: str, status_code: int | None) -> bool:
        """GPT 호출 실패가 재시도 가능한 오류인지 판별한다."""
        if status_code in GPT_RETRYABLE_STATUS_CODES:
            return True
        lowered = str(error_msg or "").lower()
        return any(keyword in lowered for keyword in GPT_RETRYABLE_KEYWORDS)

    def _is_gpt_credit_exhausted_error(self, error_msg: str, status_code: int | None) -> bool:
        """GPT 오류가 크레딧/쿼터 소진에 해당하는지 판별한다."""
        lowered = str(error_msg or "").lower()
        if status_code == 402:
            return True
        return any(keyword in lowered for keyword in GPT_CREDIT_EXHAUSTED_KEYWORDS)

    async def _call_openai_chat_json(
        self,
        *,
        client,
        model: str,
        messages: list[dict[str, str]],
        timeout_value: float,
        max_tokens: int,
    ) -> str:
        """OpenAI 호환 chat.completions 호출 후 텍스트를 추출한다."""

        def _call():
            normalized_model = str(model or "").strip().lower()
            if normalized_model.startswith("gpt-5"):
                instructions = "\n\n".join(
                    message.get("content", "")
                    for message in messages
                    if message.get("role") == "system" and message.get("content")
                ).strip()
                input_text = "\n\n".join(
                    message.get("content", "")
                    for message in messages
                    if message.get("role") != "system" and message.get("content")
                ).strip()
                request_args = {
                    "model": model,
                    "instructions": instructions,
                    "input": input_text,
                    "max_output_tokens": max_tokens,
                    "reasoning": {"effort": "minimal"},
                    "text": {"verbosity": "low"},
                    "timeout": timeout_value,
                }
            else:
                request_args = {
                    "model": model,
                    "messages": messages,
                    "timeout": timeout_value,
                    "response_format": {"type": "json_object"},
                }
                request_args["temperature"] = 0.1
                request_args["max_tokens"] = max_tokens

            last_error = None
            response = None
            for _ in range(3):
                try:
                    if normalized_model.startswith("gpt-5"):
                        response = client.responses.create(**request_args)
                    else:
                        response = client.chat.completions.create(**request_args)
                    break
                except Exception as error:
                    last_error = error
                    lowered = str(error).lower()
                    if "text" in lowered and "verbosity" in lowered and "text" in request_args:
                        request_args.pop("text", None)
                        continue
                    if "reasoning" in lowered and "reasoning" in request_args:
                        request_args.pop("reasoning", None)
                        continue
                    if "response_format" in lowered and "response_format" in request_args:
                        request_args.pop("response_format", None)
                        continue
                    if "temperature" in lowered and "temperature" in request_args:
                        request_args.pop("temperature", None)
                        continue
                    if (
                        "max_tokens" in lowered
                        and "max_completion_tokens" in lowered
                        and "max_tokens" in request_args
                    ):
                        request_args.pop("max_tokens", None)
                        request_args["max_completion_tokens"] = max_tokens
                        continue
                    if (
                        "max_completion_tokens" in lowered
                        and "max_tokens" in lowered
                        and "max_completion_tokens" in request_args
                    ):
                        request_args.pop("max_completion_tokens", None)
                        request_args["max_tokens"] = max_tokens
                        continue
                    raise

            if response is None:
                raise last_error or RuntimeError("OpenAI chat.completions 응답이 비어 있습니다.")

            if normalized_model.startswith("gpt-5"):
                output_text = getattr(response, "output_text", None)
                if isinstance(output_text, str) and output_text.strip():
                    return output_text

                output_items = getattr(response, "output", None)
                if isinstance(output_items, list):
                    for item in output_items:
                        content = getattr(item, "content", None)
                        extracted = extract_openai_message_text(content)
                        if extracted and extracted.strip():
                            return extracted
                        if isinstance(item, dict):
                            extracted = extract_openai_message_text(item.get("content"))
                            if extracted and extracted.strip():
                                return extracted
                return ""

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
            return extract_openai_message_text(reasoning_content)

        return await asyncio.to_thread(_call)

    async def _repair_gpt_response(
        self,
        *,
        model: str,
        response_text: str,
        timeout_value: float,
    ) -> Optional[Dict]:
        """비정형 GPT 응답을 JSON으로 보정 시도한다."""
        repair_input = str(response_text or "").strip()
        if not repair_input:
            return None
        if len(repair_input) > 4000:
            repair_input = repair_input[:4000]

        repair_messages = [
            {"role": "system", "content": self._build_gpt_repair_system_prompt()},
            {
                "role": "user",
                "content": (
                    "Previous model output:\n"
                    f"{repair_input}\n\n"
                    "Return only valid JSON."
                ),
            },
        ]
        repaired_text = await self._call_openai_chat_json(
            client=self.gpt_client,
            model=model,
            messages=repair_messages,
            timeout_value=timeout_value,
            max_tokens=800,
        )
        repaired_result = self._parse_json_response(str(repaired_text or ""))
        if not repaired_result:
            return None
        if is_low_quality_recommendation(repaired_result):
            return None
        repaired_result["model"] = model
        return repaired_result
    
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

        resolved_prompt = prompt or self._build_vcp_prompt(stock_name, stock_data)
        blocked_reason = str(getattr(self, "gpt_blocked_reason", "") or "").strip()
        if blocked_reason:
            return await self._fallback_from_gpt(
                stock_name=stock_name,
                stock_data=stock_data,
                prompt=resolved_prompt,
                reason=f"GPT blocked (session cache: {blocked_reason})",
            )
        if getattr(self, "gpt_quota_exhausted", False):
            return await self._fallback_from_gpt(
                stock_name=stock_name,
                stock_data=stock_data,
                prompt=resolved_prompt,
                reason="GPT quota exhausted (session cache)",
            )
        primary_model = str(app_config.VCP_GPT_MODEL or "").strip() or "gpt-5-nano"
        fallback_model = str(getattr(app_config, "VCP_GPT_FALLBACK_MODEL", "gpt-5-mini") or "").strip()
        current_model = primary_model
        max_attempts = max(1, int(getattr(app_config, "VCP_GPT_MAX_ATTEMPTS", 3)))
        request_timeout = float(getattr(app_config, "VCP_GPT_API_TIMEOUT", 120))
        base_delay = 2
        last_error: Exception | None = None
        last_response_text = ""

        messages = [
            {"role": "system", "content": self._build_gpt_system_prompt()},
            {"role": "user", "content": resolved_prompt},
        ]

        for attempt in range(max_attempts):
            attempt_timeout = request_timeout + (attempt * 10.0)
            try:
                start = time.time()
                response_text = await self._call_openai_chat_json(
                    client=self.gpt_client,
                    model=current_model,
                    messages=messages,
                    timeout_value=attempt_timeout,
                    max_tokens=900,
                )
                last_response_text = str(response_text or "")
                elapsed = time.time() - start
                logger.debug(
                    f"[GPT] {stock_name} 분석 완료 "
                    f"(model={current_model}, {elapsed:.2f}s, attempt={attempt+1}/{max_attempts})"
                )

                if is_prompt_echo_response(last_response_text):
                    logger.warning(
                        f"[GPT] {stock_name} 프롬프트 에코/메타 응답 감지 "
                        f"(model={current_model}, attempt={attempt+1})"
                    )
                else:
                    result = self._parse_json_response(last_response_text)
                    if result and not is_low_quality_recommendation(result):
                        result["model"] = current_model
                        return result

                    repaired_result = await self._repair_gpt_response(
                        model=current_model,
                        response_text=last_response_text,
                        timeout_value=attempt_timeout,
                    )
                    if repaired_result:
                        logger.info(
                            f"[GPT] {stock_name} JSON 보정 성공 "
                            f"(model={current_model}, attempt={attempt+1})"
                        )
                        return repaired_result

                    if result and is_low_quality_recommendation(result):
                        logger.warning(
                            f"[GPT] {stock_name} 응답 품질 미달 "
                            f"(model={current_model}, attempt={attempt+1})"
                        )
                    else:
                        logger.warning(
                            f"[GPT] {stock_name} JSON 파싱 실패 "
                            f"(model={current_model}, attempt={attempt+1})"
                        )
            except Exception as error:
                last_error = error
                status_code = self._extract_status_code(error)
                error_msg = str(error or "")
                retryable = self._is_retryable_gpt_error(error_msg, status_code)
                credit_exhausted = self._is_gpt_credit_exhausted_error(error_msg, status_code)

                if credit_exhausted:
                    self.gpt_quota_exhausted = True
                    self.gpt_blocked_reason = (
                        f"quota-like-{status_code}" if status_code is not None else "quota-like"
                    )
                    logger.warning(
                        f"[GPT] {stock_name} 크레딧/쿼터 소진 감지. "
                        "z.ai fallback으로 전환합니다."
                    )
                    return await self._fallback_from_gpt(
                        stock_name=stock_name,
                        stock_data=stock_data,
                        prompt=resolved_prompt,
                        reason=f"GPT credit exhausted ({status_code or 'unknown'})",
                    )

                if (
                    status_code in GPT_FALLBACK_TRIGGER_STATUS_CODES
                    and fallback_model
                    and fallback_model != current_model
                ):
                    logger.warning(
                        f"[GPT] {stock_name} {status_code} 응답으로 모델 전환 "
                        f"({current_model} -> {fallback_model})"
                    )
                    current_model = fallback_model

                if not retryable:
                    logger.error(
                        f"[GPT] {stock_name} 재시도 불가 오류: {error} "
                        f"(model={current_model}, attempt={attempt+1}/{max_attempts})"
                    )
                    return None

                logger.warning(
                    f"[GPT] {stock_name} 재시도 가능 오류: {error} "
                    f"(model={current_model}, attempt={attempt+1}/{max_attempts})"
                )

            if attempt >= max_attempts - 1:
                break

            delay = base_delay * (2 ** attempt) + (random.randint(0, 1000) / 1000)
            logger.warning(
                f"[GPT] {stock_name} {delay:.2f}초 후 재시도 "
                f"(model={current_model}, next_attempt={attempt+2}/{max_attempts})"
            )
            await asyncio.sleep(delay)

        if last_response_text:
            logger.error(f"[GPT] {stock_name} 최종 JSON 파싱 실패: {last_response_text[:300]}...")
        elif last_error is not None:
            logger.error(f"[GPT] {stock_name} 분석 실패(최종): {last_error}")
        else:
            logger.error(f"[GPT] {stock_name} 분석 실패: 빈 응답")
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
                            self.perplexity_blocked_reason = f"quota-like-{response.status_code}"
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
                            self.perplexity_blocked_reason = f"quota-{response.status_code}"
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
                            self.perplexity_blocked_reason = f"auth-or-quota-{response.status_code}"
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
                            self.perplexity_blocked_reason = f"auth-{response.status_code}"
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

        disabled_reason = str(getattr(self, "zai_disabled_reason", "") or "").strip()
        if disabled_reason:
            logger.warning(f"[Z.ai] {stock_name} 세션 비활성화 상태로 건너뜀: {disabled_reason}")
            fallback_result = build_vcp_rule_based_recommendation(
                stock_name=stock_name,
                stock_data=stock_data,
            )
            logger.warning(
                f"[Z.ai] {stock_name} 세션 비활성화로 규칙 기반 fallback 사용: "
                f"{fallback_result.get('action')} ({fallback_result.get('confidence')}%)"
            )
            return fallback_result

        try:
            resolved_prompt = prompt or self._build_vcp_prompt(stock_name, stock_data)
            primary_model = str(app_config.ZAI_MODEL or "").strip()
            model_chain: list[str] = []
            seen_models: set[str] = set()
            for candidate in [primary_model, *ZAI_FALLBACK_MODEL_CHAIN]:
                model_name = str(candidate or "").strip()
                if not model_name:
                    continue
                key = model_name.lower()
                if key in seen_models:
                    continue
                seen_models.add(key)
                model_chain.append(model_name)
            if not model_chain:
                logger.warning("[Z.ai] 사용 가능한 모델이 없습니다.")
                fallback_result = build_vcp_rule_based_recommendation(
                    stock_name=stock_name,
                    stock_data=stock_data,
                )
                logger.warning(
                    f"[Z.ai] {stock_name} 모델 체인 소진으로 규칙 기반 fallback 사용: "
                    f"{fallback_result.get('action')} ({fallback_result.get('confidence')}%)"
                )
                return fallback_result

            # 요청사항: 재시도는 동일 모델 반복이 아닌 모델 전환 기반으로 수행
            max_parse_attempts = 1
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

            for model_idx, model in enumerate(model_chain):
                should_try_next_model = False
                same_model_echo_retries_used = 0
                same_model_echo_retries_max = 2

                for attempt in range(max_parse_attempts):
                    start = time.time()
                    attempt_timeout = request_timeout + (attempt * 20.0)

                    def _call(
                        messages: list[dict[str, str]],
                        use_json_mode: bool,
                        max_tokens: int = 2500,
                        timeout_value: float = request_timeout,
                        temperature: float = 0.0,
                    ):
                        request_args = {
                            "model": model,
                            "messages": messages,
                            "temperature": temperature,
                            "max_tokens": max_tokens,
                            "timeout": timeout_value,
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
                            return _restore_zai_prefill(response_text)

                        reasoning_content = getattr(message_obj, "reasoning_content", None)
                        if reasoning_content is None and isinstance(message_obj, dict):
                            reasoning_content = message_obj.get("reasoning_content")
                        response_text = extract_openai_message_text(reasoning_content)
                        if response_text and response_text.strip():
                            return _restore_zai_prefill(response_text)

                        return ""

                    primary_messages = [
                        {
                            "role": "system",
                            "content": (
                                "당신은 한국 주식 기술적 분석가입니다. "
                                "반드시 JSON 객체 1개만 출력하고 코드블록/설명문/마크다운을 금지합니다. "
                                "JSON 외 텍스트를 단 한 글자도 출력하지 말고, 반드시 '{'로 시작해 '}'로 끝내십시오. "
                                "reason은 반드시 한국어로 상세하게 작성하십시오. "
                                "reason은 최소 2문장, 최소 90자 이상이어야 합니다. "
                                "가능하면 아래 섹션 구조를 포함하십시오: "
                                "[핵심 투자 포인트], [리스크 요인], [종합 의견]. "
                                "You are a technical analyst. "
                                "Return exactly one compact JSON object and nothing else. "
                                "Required keys: action, confidence, reason. "
                                "action must be BUY, SELL, or HOLD. "
                                "confidence must be an integer 0-100. "
                                "reason must be detailed Korean analysis with at least two sentences."
                            ),
                        },
                        {"role": "user", "content": resolved_prompt},
                        {"role": "assistant", "content": '{"action":"'},
                    ]
                    try:
                        response_text = await asyncio.to_thread(
                            _call,
                            primary_messages,
                            True,
                            2500,
                            attempt_timeout,
                        )
                        last_response_text = str(response_text or "")

                        elapsed = time.time() - start
                        logger.debug(
                            f"[Z.ai] {stock_name} 분석 완료 "
                            f"(model={model}, {elapsed:.2f}s, attempt={attempt+1}/{max_parse_attempts}, "
                            f"timeout={attempt_timeout:.0f}s)"
                        )

                        if is_prompt_echo_response(last_response_text):
                            logger.warning(
                                f"[Z.ai] {stock_name} 프롬프트 에코/메타 응답 감지 "
                                f"(model={model}, attempt={attempt+1})"
                            )
                            recovered_text: str | None = None
                            while same_model_echo_retries_used < same_model_echo_retries_max:
                                same_model_echo_retries_used += 1
                                # 결정론적 echo를 깨기 위해 retry마다 temperature를 점진적으로 올린다.
                                retry_temperature = 0.3 + 0.2 * (same_model_echo_retries_used - 1)
                                logger.info(
                                    f"[Z.ai] {stock_name} 같은 모델로 재시도 "
                                    f"(model={model}, retry={same_model_echo_retries_used}/{same_model_echo_retries_max}, temp={retry_temperature:.1f})"
                                )
                                try:
                                    retry_text = await asyncio.to_thread(
                                        _call,
                                        primary_messages,
                                        True,
                                        2500,
                                        attempt_timeout,
                                        retry_temperature,
                                    )
                                except Exception as retry_error:
                                    logger.warning(
                                        f"[Z.ai] {stock_name} 재시도 호출 실패: {retry_error}"
                                    )
                                    retry_text = ""
                                retry_text = str(retry_text or "")
                                if retry_text and not is_prompt_echo_response(retry_text):
                                    recovered_text = retry_text
                                    break
                            if recovered_text is not None:
                                last_response_text = recovered_text
                                # 재시도 응답으로 정상 흐름 재진입을 위해 아래 파싱 단계로 이어진다.
                            else:
                                if model_idx < len(model_chain) - 1:
                                    next_model = model_chain[model_idx + 1]
                                    logger.warning(
                                        f"[Z.ai] {stock_name} 재시도도 메타 응답이라 모델 전환 "
                                        f"({model} -> {next_model})"
                                    )
                                    should_try_next_model = True
                                else:
                                    self.zai_disabled_reason = "prompt-echo responses"
                                    logger.warning(
                                        f"[Z.ai] {stock_name} 마지막 모델 {model} 재시도까지 메타 응답이 반복되어 "
                                        "이번 세션에서 Z.ai를 비활성화합니다."
                                    )
                                break

                        result = self._parse_json_response(last_response_text)
                        quality_low = False
                        if result:
                            if not is_low_quality_recommendation(result):
                                return result
                            quality_low = True
                            logger.warning(
                                f"[Z.ai] {stock_name} 응답 품질 미달 감지. "
                                f"모델 전환 후보로 표시합니다 (model={model}, attempt={attempt+1})"
                            )

                        # 1차 응답이 JSON이 아니거나 품질 미달일 경우, 동일 모델에 JSON 보정 요청을 추가로 수행한다.
                        if (not quality_low) and last_response_text.strip():
                            repair_input = last_response_text.strip()
                            if len(repair_input) > 4000:
                                repair_input = repair_input[:4000]

                            repair_messages = [
                                {
                                    "role": "system",
                                    "content": (
                                        "당신은 주식 분석 텍스트를 JSON으로 정규화하는 변환기입니다. "
                                        "출력은 JSON 객체 1개만 허용됩니다. "
                                        "JSON 외 텍스트를 단 한 글자도 출력하지 말고, 반드시 '{'로 시작해 '}'로 끝내십시오. "
                                        "reason은 반드시 한국어로 상세하게 작성하십시오. "
                                        "reason은 최소 2문장, 최소 90자 이상이어야 합니다. "
                                        "가능하면 [핵심 투자 포인트], [리스크 요인], [종합 의견] 섹션을 포함하십시오. "
                                        "You convert stock analysis text into strict JSON only. "
                                        "Return exactly one JSON object with keys: action, confidence, reason. "
                                        "action must be BUY, SELL, or HOLD. confidence must be integer 0-100. "
                                        "reason must be detailed Korean analysis with at least two sentences."
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
                                {"role": "assistant", "content": '{"action":"'},
                            ]
                            repaired_text = await asyncio.to_thread(
                                _call,
                                repair_messages,
                                True,
                                2000,
                                attempt_timeout,
                            )
                            repaired_result = self._parse_json_response(str(repaired_text or ""))
                            if repaired_result:
                                if not is_low_quality_recommendation(repaired_result):
                                    logger.info(
                                        f"[Z.ai] {stock_name} JSON 변환 보정 성공 "
                                        f"(model={model}, attempt={attempt+1})"
                                    )
                                    return repaired_result
                                quality_low = True
                                logger.warning(
                                    f"[Z.ai] {stock_name} JSON 보정 응답도 품질 미달입니다 "
                                    f"(model={model}, attempt={attempt+1})"
                                )

                        if quality_low:
                            if model_idx < len(model_chain) - 1:
                                next_model = model_chain[model_idx + 1]
                                logger.warning(
                                    f"[Z.ai] {stock_name} 응답 품질 미달로 모델 전환 "
                                    f"({model} -> {next_model})"
                                )
                                should_try_next_model = True
                            else:
                                logger.warning(
                                    f"[Z.ai] {stock_name} 마지막 모델 {model}도 응답 품질 미달로 "
                                    "추가 모델 전환 없이 fallback으로 종료합니다."
                                )
                            break

                        if model_idx < len(model_chain) - 1:
                            next_model = model_chain[model_idx + 1]
                            logger.warning(
                                f"[Z.ai] {stock_name} JSON 파싱 실패로 모델 전환 "
                                f"({model} -> {next_model})"
                            )
                            should_try_next_model = True
                        break
                    except Exception as error:
                        last_error = error
                        elapsed = time.time() - start
                        status_code = _extract_status_code(error)
                        if model_idx < len(model_chain) - 1:
                            next_model = model_chain[model_idx + 1]
                            reason = f"status={status_code}" if status_code is not None else str(error)
                            logger.warning(
                                f"[Z.ai] {stock_name} 호출 실패로 모델 전환 "
                                f"({model} -> {next_model}, reason={reason}, "
                                f"elapsed={elapsed:.2f}s, timeout={attempt_timeout:.0f}s)"
                            )
                            should_try_next_model = True
                            break

                        logger.error(
                            f"[Z.ai] {stock_name} 호출 실패(최종): {error} "
                            f"(model={model}, elapsed={elapsed:.2f}s, timeout={attempt_timeout:.0f}s)"
                        )
                        break

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

    async def _fallback_from_gpt(
        self,
        *,
        stock_name: str,
        stock_data: Dict,
        prompt: str,
        reason: str,
    ) -> Optional[Dict]:
        """GPT 크레딧/쿼터 소진 시 z.ai로 폴백 분석."""
        normalized_providers = [normalize_provider_name(provider) for provider in getattr(self, "providers", [])]
        if "zai" not in normalized_providers:
            logger.error(
                f"[GPT fallback] {stock_name} 폴백 불가: "
                f"VCP_AI_PROVIDERS에 z.ai가 없습니다. ({reason})"
            )
            return None
        if not getattr(self, "zai_client", None):
            logger.error(
                f"[GPT fallback] {stock_name} 폴백 불가: "
                f"z.ai 클라이언트 미초기화 ({reason})"
            )
            return None

        logger.warning(f"[GPT->Z.ai fallback] {stock_name} 사유: {reason}")
        return await self._analyze_with_zai(stock_name, stock_data, prompt)

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
