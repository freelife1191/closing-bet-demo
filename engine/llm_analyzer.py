#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Engine - LLM Analyzer (Gemini/Z.ai) - Refactored

LLM 분석기로 Gemini와 Z.ai를 지원하며, 중복된 재시도 로직을 추출하여 코드를 간소화했습니다.

Created: 2026-02-11
Refactored from: engine/llm_analyzer.py (591 lines → 약 480 lines)
"""
import os
import logging
import time
import json
import re
from typing import List, Dict, Optional, Callable, Any
import asyncio
import random
from abc import ABC, abstractmethod

try:
    from google import genai
except ImportError:
    genai = None

from engine.config import app_config

logger = logging.getLogger(__name__)


# ========================================================================
# Retry Strategy Classes
# ========================================================================

class RetryConfig:
    """재시도 설정"""
    MAX_RETRIES = 5
    BASE_WAIT = 2.0
    MAX_WAIT = 32.0

    # 재시도 조건 (에러 메시지에 포함된 키워드)
    RETRY_CONDITIONS = [
        "429",
        "resource_exhausted",
        "503",
        "overloaded",
        "502",
        "500",
        "resource_exhausted",
        "unavailable",
    ]


class LLMRetryStrategy(ABC):
    """LLM 재시도 전략 인터페이스"""

    @abstractmethod
    async def execute(
        self,
        prompt: str,
        timeout: float,
        model: str
    ) -> str:
        """LLM 호출 실행 (추상 메서드)"""
        pass

    @abstractmethod
    def get_model_name(self) -> str:
        """모델명 반환 (추상 메서드)"""
        pass


class GeminiRetryStrategy(LLMRetryStrategy):
    """Gemini 재시도 전략"""

    def __init__(self, client, model: str = "gemini-2.0-flash"):
        self.client = client
        self.model = model
        self._current_model = model

    async def execute(self, prompt: str, timeout: float, model: str) -> str:
        """Gemini 호출 실행"""
        self._current_model = model

        def _call_gemini():
            return self.client.models.generate_content(
                model=self._current_model,
                contents=prompt
            )

        return await self._call_with_retry(_call_gemini, timeout)

    async def _call_with_retry(self, call_fn: Callable, timeout: float) -> str:
        """Gemini 재시도 로직"""
        for attempt in range(RetryConfig.MAX_RETRIES):
            try:
                resp = await asyncio.wait_for(
                    asyncio.to_thread(call_fn),
                    timeout=timeout
                )

                # 응답 모델 버전 로깅 (디버그 전용, _current_model은 덮어쓰지 않음)
                model_version = getattr(resp, 'model_version', None)
                if model_version and model_version != self._current_model:
                    logger.debug(
                        f"[GEMINI] 요청 모델: {self._current_model} → "
                        f"실제 응답 모델: {model_version}"
                    )

                return resp.text

            except asyncio.TimeoutError:
                logger.warning(
                    f"[GEMINI] Timeout (Attempt {attempt + 1}/{RetryConfig.MAX_RETRIES})"
                )
                if attempt == RetryConfig.MAX_RETRIES - 1:
                    raise
                continue

            except Exception as e:
                error_msg = str(e).lower()

                # 재시도 조건 확인
                if any(c in error_msg for c in RetryConfig.RETRY_CONDITIONS):
                    if attempt < RetryConfig.MAX_RETRIES - 1:
                        # Fallback Logic: primary -> gemini-flash-latest
                        if self._current_model != "gemini-flash-latest":
                            logger.warning(
                                f"[GEMINI] {self._current_model} 과부하 또는 오류로 인해 "
                                "'gemini-flash-latest'로 전환하여 재시도합니다."
                            )
                            self._current_model = "gemini-flash-latest"
                            wait_time = 1.0
                        else:
                            wait_time = (5 * (2 ** attempt)) + random.uniform(1, 3)

                        logger.warning(
                            f"[GEMINI] Transient error hit. "
                            f"Retrying with {self._current_model} in {wait_time:.1f}s... "
                            f"({attempt + 1}/{RetryConfig.MAX_RETRIES})"
                        )
                        await asyncio.sleep(wait_time)
                        continue

                # Other errors or max retries reached
                raise e

    def get_model_name(self) -> str:
        return self._current_model


class ZAIRetryStrategy(LLMRetryStrategy):
    """Z.ai (OpenAI 호환) 재시도 전략"""

    def __init__(self, client, model: str = "gpt-4o-mini"):
        self.client = client
        self.model = model

    async def execute(self, prompt: str, timeout: float, model: str) -> str:
        """Z.ai 호출 실행"""
        messages = [
            {"role": "system", "content": "당신은 주식 투자 전문가입니다."},
            {"role": "user", "content": prompt}
        ]

        def _call_zai():
            return self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.1
            )

        response = await asyncio.wait_for(
            asyncio.to_thread(_call_zai),
            timeout=timeout
        )

        # OpenAI 응답에서 텍스트 추출
        if response and response.choices:
            return response.choices[0].message.content
        return ""

    def get_model_name(self) -> str:
        return self.model


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

        self._last_loaded_key = current_key
        self._client = None
        self._retry_strategy = None  # Reset strategy

        if not current_key and self.provider != 'zai':
            logger.warning("API key not configured")
            return

        self._create_client(current_key)

    def _get_api_key(self) -> str:
        """Get current API key"""
        if self._api_key_source:
            return self._api_key_source
        elif self.provider == 'zai':
            return app_config.ZAI_API_KEY
        else:
            return app_config.GOOGLE_API_KEY

    def _create_client(self, api_key: str) -> None:
        """Create client based on provider"""
        if self.provider == 'zai':
            self._create_zai_client(api_key)
        else:
            self._create_gemini_client(api_key)

    def _create_zai_client(self, api_key: str) -> None:
        """Create Z.ai (OpenAI) client"""
        try:
            from openai import OpenAI

            base_url = app_config.ZAI_BASE_URL
            formatted_key = api_key[:4] + "*" * 10 if api_key else "None"

            logger.info(f"Z.ai LLM Init (Key: {formatted_key})")
            self._client = OpenAI(api_key=api_key, base_url=base_url)

            self._retry_strategy = ZAIRetryStrategy(
                self._client,
                app_config.ZAI_MODEL
            )

        except ImportError:
            logger.error("openai package missing")
        except Exception as e:
            logger.error(f"Z.ai Init Failed: {e}")

    def _create_gemini_client(self, api_key: str) -> None:
        """Create Gemini client"""
        if genai is None:
            logger.error("google-genai package missing")
            return

        try:
            masked_key = api_key[:4] + "*" * 10 if api_key else "None"
            
            # API Timeout: google-genai http_options uses milliseconds (ms)
            timeout_ms = float(app_config.ANALYSIS_LLM_API_TIMEOUT) * 1000

            self._client = genai.Client(
                api_key=api_key,
                http_options={'timeout': timeout_ms}
            )

            self._retry_strategy = GeminiRetryStrategy(
                self._client,
                app_config.ANALYSIS_GEMINI_MODEL
            )

            model_name = app_config.ANALYSIS_GEMINI_MODEL
            logger.info(f"Gemini LLM Client Initialized - Model: {model_name}, Timeout setting: {timeout_ms}ms")

        except Exception as e:
            logger.error(f"Gemini Init Failed: {e}")

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
            prompt = self._build_sentiment_prompt(stock_name, news_items)

            response_content = await self._execute_llm_call(
                prompt=prompt,
                timeout=app_config.LLM_API_TIMEOUT
            )

            return self._parse_json_response(
                response_text=response_content,
                stock_name=stock_name
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
            prompt = self._build_batch_prompt(items, market_status)

            response_content = await self._execute_llm_call(
                prompt=prompt,
                timeout=app_config.ANALYSIS_LLM_API_TIMEOUT
            )

            results_list = self._parse_batch_response(
                response_text=response_content
            )

            return self._build_result_map(results_list)

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
            prompt = self._build_summary_prompt(signals)

            response_content = await self._execute_llm_call(
                prompt=prompt,
                timeout=app_config.LLM_API_TIMEOUT
            )

            return response_content.strip()

        except Exception as e:
            logger.error(f"{self.provider} 시장 요약 실패: {e}")
            return f"시장 요약 생성 실패: {str(e)}"

    # ========================================================================
    # Private Methods - Prompt Building
    # ========================================================================

    def _build_sentiment_prompt(self, stock_name: str, news_items: List[Dict]) -> str:
        """감성 분석 프롬프트 구성"""
        news_text = self._format_news_for_prompt(news_items)

        return f"""
당신은 주식 투자 전문가입니다. 주어지는 뉴스들을 분석하여 호재 강도를 평가하세요.

다음은 '{stock_name}' 종목에 대한 최신 뉴스들입니다.
이 뉴스들을 **종합적으로 분석**하여 현재 시점에서의 호재 강도를 0~3점으로 평가하세요.

[뉴스 목록]
{news_text}

[점수 기준]
3점: 확실한 호재 (대규모 수주, 상한가 재료, 어닝 서프라이즈, 경영권 분쟁 등)
2점: 긍정적 호재 (실적 개선, 기대감, 테마 상승)
1점: 단순/중립적 소식
0점: 악재 또는 별다른 호재 없음

[출력 형식]
뉴스 3개를 따로 평가하지 말고, **종목 전체에 대한 하나의 평가**를 내리세요.
반드시 아래 포맷의 **단일 JSON 객체**로만 답하세요. (Markdown code block 없이)

Format: {{"score": 2, "reason": "종합적인 요약 이유"}}
"""

    def _build_batch_prompt(self, items: List[Dict], market_status: Dict = None) -> str:
        """배치 분석 프롬프트 구성"""
        # Market Context
        market_context = self._build_market_context(market_status)

        # Stocks Text
        stocks_text = self._build_stocks_text(items)

        return f"""
{market_context}

다음 종목들을 분석하여 투자 매력도를 평가하세요.
특히 **VCP(변동성 수축 패턴)의 기술적 완성도**를 반드시 평가에 포함해야 합니다.

[입력 데이터]
{stocks_text}

[평가 기준]
0. **VCP 분석 (필수)**:
   - 변동성 수축(Contraction Ratio)이 0.1~0.5 사이로 건전한가?
   - 거래량(Volume)이 급감하며 매물 소화가 잘 되었는가?
   - 이 기술적 지표가 점수에 **가장 큰 영향**을 미쳐야 함.
1. **Score (0-3)**: 뉴스/재료 기반 호재 강도
   - 3점: 확실한 호재 (대규모 수주, 상한가 재료, 어닝 서프라이즈)
   - 2점: 긍정적 호재 (실적 개선, 기대감, 테마 상승)
   - 1점: 단순/중립적 소식
   - 0점: 악재 또는 별다른 호재 없음
2. **Action**: BUY / HOLD / SELL
3. **Confidence**: 확신도 (0-100%)
4. **Reason**: 다음 요소를 종합하여 **3~5줄**로 구체적 근거를 포함하여 작성하세요.
   - 뉴스/재료 분석: 구체적 호재/악재 내용과 산업 영향도
   - VCP 기술적 분석: 수축 비율, 거래량 추이, 패턴 완성도 평가
   - 수급 동향: 외인/기관 매매 추이와 의미
   - 리스크 요인: 단기 과열, 밸류에이션, 업종 리스크 등
   - 매매 전략: 매수 시점, 목표가, 손절 기준 구체적 제시

[출력 형식]
반드시 아래 포맷의 **JSON 배열**로만 답하세요. (Markdown code block 없이)

[
    {{
        "name": "종목명",
        "score": 2,
        "action": "BUY",
        "confidence": 85,
        "reason": "대규모 신규 수주 발표로 강한 호재. 외인/기관 동반 순매수 유입 중. 시가 매수 후 전저점 이탈 시 손절 권장."
    }}
]
"""

    def _build_summary_prompt(self, signals: List[Dict]) -> str:
        """시장 요약 프롬프트 구성"""
        # 상위 30개 종목만 추출
        sorted_signals = sorted(
            signals,
            key=lambda x: x.get('score', {}).get('total', 0),
            reverse=True
        )
        top_signals = sorted_signals[:30]

        stocks_text = ""
        for s in top_signals:
            grade = s.get('grade', 'C')
            score = s.get('score', {}).get('total', 0)
            name = s.get('stock_name', '')
            reason = s.get('score', {}).get('llm_reason', '')

            stocks_text += f"- {name} ({grade}급/{score}점): {reason}\n"

        return f"""
당신은 주식 시장 분석 전문가입니다. 오늘 '종가베팅' 알고리즘에 포착된 상위 종목 리스트입니다.
이들을 분석하여 다음 내용을 포함한 3~5줄 내외의 시장 요약 리포트를 작성해주세요.

1. 오늘의 주도 섹터/테마
2. 시장의 전반적인 분위기 (수급 강도 등)
3. 특히 주목할만한 특징

[종목 리스트]
{stocks_text}

[출력 형식]
줄글 형태로 간결하게 요약. (Markdown 사용 가능)
"""

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
        if not self._retry_strategy:
            raise RuntimeError("Retry strategy not initialized")

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

    # ========================================================================
    # Private Methods - Response Parsing
    # ========================================================================

    def _parse_json_response(
        self,
        response_text: str,
        stock_name: str
    ) -> Optional[Dict]:
        """JSON 응답 파싱"""
        result_text = response_text.strip()
        if not result_text:
            logger.warning(f"Empty response for {stock_name}")
            return None

        # JSON 추출
        json_match = re.search(r'\{.*\}', result_text, re.DOTALL)
        json_str = json_match.group(0) if json_match else result_text

        try:
            result = json.loads(json_str)
            # 모델명 추가
            if isinstance(result, dict) and 'model' not in result:
                model = self._retry_strategy.get_model_name() if self._retry_strategy else "unknown"
                if model == "gemini-flash-latest":
                    model = "Gemini Flash (Latest)"
                result['model'] = model
            return result

        except json.JSONDecodeError as je:
            logger.error(f"JSON 파싱 실패 ({stock_name}): {je}")
            logger.debug(f"Raw: {result_text}")
            return None

    def _parse_batch_response(self, response_text: str) -> List[Dict]:
        """배치 JSON 응답 파싱"""
        result_text = response_text.strip()

        json_match = re.search(r'\[.*\]', result_text, re.DOTALL)
        json_str = json_match.group(0) if json_match else result_text

        try:
            return json.loads(json_str)
        except json.JSONDecodeError as je:
            logger.error(f"배치 JSON 파싱 실패: {je}")
            return []

    def _build_result_map(self, results_list: List[Dict]) -> Dict[str, Dict]:
        """결과 매핑 생성"""
        model = self._retry_strategy.get_model_name() if self._retry_strategy else "unknown"
        if model == "gemini-flash-latest":
            model = "Gemini Flash (Latest)"

        final_map = {}
        for item in results_list:
            name = item.get("name")
            if name:
                final_map[name] = {
                    "score": item.get("score", 0),
                    "action": item.get("action", "HOLD"),
                    "confidence": item.get("confidence", 0),
                    "reason": item.get("reason", ""),
                    "model": model
                }

        return final_map

    # ========================================================================
    # Private Methods - Data Formatting
    # ========================================================================

    def _format_news_for_prompt(self, news_items: List[Dict]) -> str:
        """프롬프트용 뉴스 텍스트 포맷팅"""
        news_text = ""
        for i, news in enumerate(news_items, 1):
            title = news.get("title", "")
            summary = news.get("summary", "")[:200]
            news_text += f"[{i}] 제목: {title}\n내용: {summary}\n\n"
        return news_text

    def _build_market_context(self, market_status: Dict) -> str:
        """시장 컨텍스트 구성"""
        if not market_status:
            return ""

        return f"""
[시장 상황]
- 상태: {market_status.get('status', 'Unknown')}
- 점수: {market_status.get('total_score', 0)}/100
- KOSPI: {market_status.get('kospi_close', 0)} ({market_status.get('kospi_change', 0)}%)
"""

    def _build_stocks_text(self, items: List[Dict]) -> str:
        """종목 텍스트 구성"""
        stocks_text = ""

        for item in items:
            stock = item.get('stock')
            if not stock:
                continue

            news_list = item.get('news', [])
            supply = item.get('supply')

            # 뉴스 텍스트
            news_text = ""
            for i, news in enumerate(news_list[:3], 1):
                weight = getattr(news, 'weight', 1.0)
                if isinstance(news, dict):
                    weight = news.get('weight', 1.0)
                    title = news.get('title', '')
                else:
                    title = news.title

                prefix = "[주요] " if weight >= 1.2 else ""
                news_text += f"  {i}. {prefix}{title}\n"

            # 수급 텍스트
            if supply:
                supply_text = (
                    f"외인 5일합: {supply.foreign_buy_5d:,}, "
                    f"기관 5일합: {supply.inst_buy_5d:,}"
                )
            else:
                supply_text = "N/A"

            # Stock 정보
            s_name, s_code, s_close, s_change, s_value = self._extract_stock_info(stock)
            vcp_score, contraction_ratio = self._extract_vcp_info(stock)

            stocks_text += f"""
=== {s_name} ({s_code}) ===
[기술적/수급 지표]
- 현재가: {s_close:,}원 (등락: {s_change}%)
- **VCP 점수: {vcp_score}점**
- **수축 비율: {contraction_ratio} (낮을수록 좋음)**
- 거래대금: {s_value // 100000000}억원
- 수급: {supply_text}

[최신 뉴스]
{news_text}
"""

        return stocks_text

    def _extract_stock_info(self, stock: Dict) -> tuple:
        """Stock 정보 추출"""
        if isinstance(stock, dict):
            s_name = stock.get('stock_name') or stock.get('name', 'Unknown')
            s_code = stock.get('stock_code') or stock.get('code', '')
            s_close = stock.get('current_price', 0)
            s_change = stock.get('change_pct', 0)
            s_value = stock.get('trading_value', 0)
        else:
            s_name = getattr(stock, 'name', 'Unknown')
            s_code = getattr(stock, 'code', '')
            s_close = getattr(stock, 'close', 0)
            s_change = getattr(stock, 'change_pct', 0)
            s_value = getattr(stock, 'trading_value', 0)

        return s_name, s_code, s_close, s_change, s_value

    def _extract_vcp_info(self, stock: Dict) -> tuple:
        """VCP 정보 추출"""
        vcp_score = 0
        contraction_ratio = 1.0

        if isinstance(stock, dict):
            # 1. Direct VCP keys
            if 'vcp_score' in stock:
                vcp_score = stock['vcp_score']
                contraction_ratio = stock.get('contraction_ratio', 1.0)
            # 2. Score object fallback
            else:
                score = stock.get('score', 0)
                if hasattr(score, 'total'):
                    # This is Closing Bet Score, not VCP score. 
                    # If this is Closing Bet, we want VCP score if available.
                    vcp_score = getattr(stock, 'vcp_score', 0)
                elif isinstance(score, dict):
                    vcp_score = score.get('total', 0)
                else:
                    vcp_score = score
                
                if 'contraction_ratio' in stock:
                    contraction_ratio = stock['contraction_ratio']

        else:
            # Object
            if hasattr(stock, 'vcp_score'):
                vcp_score = getattr(stock, 'vcp_score', 0)
                contraction_ratio = getattr(stock, 'contraction_ratio', 1.0)
            else:
                # Fallback to score (might be total score if VCP not available)
                # But for VCP analysis we really want VCP score.
                # If unavailable, return 0 to indicate "Not observed"
                vcp_score = 0
                contraction_ratio = getattr(stock, 'contraction_ratio', 1.0)

        return vcp_score, contraction_ratio
