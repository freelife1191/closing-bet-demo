#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Engine - LLM Analyzer (Gemini)
"""
import os
import logging
import time
from typing import List, Dict, Optional
import asyncio
try:
    from google import genai
except ImportError:
    genai = None

from engine.config import app_config

logger = logging.getLogger(__name__)


class LLMAnalyzer:
    """LLM 분석기 (Gemini / Z.ai 지원)"""

    def __init__(self, api_key: str = None):
        self.provider = app_config.LLM_PROVIDER.lower()
        self._client = None
        self._api_key_source = api_key # If provided explicitly, stick to it? Or allow override? 
        # Strategy: If api_key arg is provided, use it rigidly. If None, use app_config dynamically.
        self._last_loaded_key = None
        self._init_client()

    def _init_client(self):
        """Initialize Client based on current config"""
        # Determine current key
        if self._api_key_source:
            current_key = self._api_key_source
        elif self.provider == 'zai':
             current_key = app_config.ZAI_API_KEY
        else:
             current_key = app_config.GOOGLE_API_KEY

        # If key hasn't changed and client exists, do nothing (unless forced?)
        if self._client and current_key == self._last_loaded_key:
            return

        self._last_loaded_key = current_key
        self._client = None # Reset

        if not current_key and self.provider != 'zai':
             # logger.warning("GOOGLE_API_KEY가 설정되지 않았습니다.")
             return

        if self.provider == 'zai':
            base_url = app_config.ZAI_BASE_URL
            if current_key:
                try:
                    from openai import OpenAI
                    formatted_key = current_key[:4] + "*" * 10 if current_key else "None"
                    logger.info(f"Z.ai LLM Re-Init (Key: {formatted_key})")
                    self._client = OpenAI(api_key=current_key, base_url=base_url)
                except ImportError:
                    logger.error("openai package missing")
                except Exception as e:
                    logger.error(f"Z.ai Init Failed: {e}")
        else:
            # Gemini
            if genai is None:
                logger.error("google-genai package missing")
                return
            try:
                masked_key = current_key[:4] + "*" * 10 if current_key else "None"
                # logger.debug(f"Gemini LLM Re-Init: Key={masked_key}")
                self._client = genai.Client(api_key=current_key)
            except Exception as e:
                logger.error(f"Gemini Init Failed: {e}")

    @property
    def client(self):
        """Dynamic Client Accessor"""
        # Always check/refresh before returning
        self._init_client()
        return self._client


    async def analyze_news_sentiment(self, stock_name: str, news_items: List[Dict]) -> Optional[Dict]:
        """뉴스 감성 분석"""
        if not self.client or not news_items:
            return None

        try:
            # 프롬프트 구성
            news_text = ""
            for i, news in enumerate(news_items, 1):
                title = news.get("title", "")
                summary = news.get("summary", "")[:200]
                news_text += f"[{i}] 제목: {title}\n내용: {summary}\n\n"

            system_prompt = "당신은 주식 투자 전문가입니다. 주어지는 뉴스들을 분석하여 호재 강도를 평가하세요."
            user_prompt = f"""
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

            response_content = ""
            start_time = time.time()

            if self.provider == 'zai':
                # Z.ai (OpenAI) 호출 - Blocking Call을 Thread로 분리
                model = app_config.ZAI_MODEL
                
                def _call_zai():
                    return self.client.chat.completions.create(
                        model=model,
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt}
                        ],
                        temperature=0.1
                    )
                
                completion = await asyncio.to_thread(_call_zai)
                api_elapsed = time.time() - start_time
                logger.info(f"[{self.provider.upper()}] API Response in {api_elapsed:.2f}s")
                response_content = completion.choices[0].message.content
            
            else:
                # Gemini 호출 - Blocking Call을 Thread로 분리
                full_prompt = system_prompt + "\n" + user_prompt
                
                def _call_gemini():
                    # Retry logic defined in wrapper or handle here?
                    # Since we are using wrapper below, simple call is enough
                    return self.client.models.generate_content(
                        model=app_config.GEMINI_MODEL,
                        contents=full_prompt
                    )

                # Retry Logic Wrapper
                max_retries = 3
                for attempt in range(max_retries):
                    try:
                        resp = await asyncio.to_thread(_call_gemini)
                        response_content = resp.text
                        break
                    except Exception as e:
                        if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                             if attempt < max_retries - 1:
                                wait_time = (2 ** attempt) + 1  # 2, 3, 5 seconds
                                logger.warning(f"[GEMINI] Rate limit hit (429). Retrying in {wait_time}s... ({attempt+1}/{max_retries})")
                                await asyncio.sleep(wait_time)
                                continue
                        # Other errors or max retries reached
                        raise e
                api_elapsed = time.time() - start_time
                logger.info(f"[{self.provider.upper()}] API Response in {api_elapsed:.2f}s")

            # 공통: 응답 처리
            result_text = response_content.strip()
            if not result_text:
                logger.warning(f"{self.provider} 응답 텍스트가 비어있습니다: {stock_name}")
                return None

            # 1. 마크다운 코드 블록 제거 및 JSON 추출 (정규식 활용)
            import re
            import json
            
            # JSON 객체({...})만 찾아내기 위한 정규식
            json_match = re.search(r'\{.*\}', result_text, re.DOTALL)
            json_str = json_match.group(0) if json_match else result_text

            # JSON 파싱
            try:
                result = json.loads(json_str)
                return result
            except json.JSONDecodeError as je:
                logger.error(f"JSON 파싱 실패 ({stock_name}): {je}\nRaw: {result_text}")
                return None

        except Exception as e:
            logger.error(f"{self.provider} 분석 실패 ({stock_name}): {e}")
            return None
        finally:
            elapsed = time.time() - start_time
            logger.info(f"[{self.provider.upper()}] Sentiment Analysis for {stock_name}: {elapsed:.2f}s")

    async def analyze_news_batch(self, items: List[Dict], market_status: Dict = None) -> Dict[str, Dict]:
        """
        뉴스 + 심층 데이터 일괄 분석 (Batch Processing)
        Args:
            items: [{
                'stock': StockData, 
                'news': [NewsItem...], 
                'supply': SupplyData, 
                'charts': ChartData
            }, ...]
            market_status: Market Gate Status Dict
        Returns:
            { "삼성전자": {"score": 2, "action": "BUY", "confidence": 85, "reason": "..."}, ... }
        """
        if not self.client or not items:
            return {}
            
        start_time = time.time()
        
        # 요청 시작 로깅
        def _get_stock_name(item):
            stock = item.get('stock')
            if stock is None:
                return 'Unknown'
            if isinstance(stock, dict):
                return stock.get('stock_name') or stock.get('name', 'Unknown')
            return getattr(stock, 'name', 'Unknown')
        
        stock_names = [_get_stock_name(item) for item in items]
        logger.info(f"[{self.provider.upper()}] 배치 분석 시작: {len(items)}개 종목 - {stock_names}")

        try:
            # 프롬프트 구성
            stocks_text = ""
            
            # Global Market Context
            market_context = ""
            if market_status:
                market_context = f"""
                [시장 상황]
                - 상태: {market_status.get('status', 'Unknown')}
                - 점수: {market_status.get('total_score', 0)}/100
                - KOSPI: {market_status.get('kospi_close', 0)} ({market_status.get('kospi_change', 0)}%)
                """

            for item in items:
                stock = item.get('stock')
                if not stock: continue
                
                news_list = item.get('news', [])
                supply = item.get('supply')
                # charts = item.get('charts') # 차트 데이터는 수치화된 지표 위주로 전달

                # 뉴스 텍스트
                news_text = ""
                for i, news in enumerate(news_list[:3], 1):
                    # 가중치 1.2 이상인 뉴스는 강조 표시
                    weight = getattr(news, 'weight', 1.0)
                    if isinstance(news, dict):
                         weight = news.get('weight', 1.0)
                         title = news.get('title', '')
                    else:
                        title = news.title

                    prefix = "[주요] " if weight >= 1.2 else ""
                    news_text += f"  {i}. {prefix}{title}\n"
                
                # 수급 텍스트
                supply_text = "N/A"
                if supply:
                    supply_text = f"외인 5일합: {supply.foreign_buy_5d:,}, 기관 5일합: {supply.inst_buy_5d:,}"

                # Stock 객체/Dict 호환 처리 (stock_name 필드 우선)
                if isinstance(stock, dict):
                    s_name = stock.get('stock_name') or stock.get('name', 'Unknown')
                    s_code = stock.get('stock_code') or stock.get('code', '')
                else:
                    s_name = getattr(stock, 'name', 'Unknown')
                    s_code = getattr(stock, 'code', '')
                s_close = getattr(stock, 'close', 0)
                if isinstance(stock, dict): s_close = stock.get('current_price', 0)
                
                s_change = getattr(stock, 'change_pct', 0)
                if isinstance(stock, dict): s_change = stock.get('change_pct', 0)
                
                s_value = getattr(stock, 'trading_value', 0)
                if isinstance(stock, dict): s_value = stock.get('trading_value', 0)
                
                stocks_text += f"""
                === {s_name} ({s_code}) ===
                [기술적/수급 지표]
                - 현재가: {s_close:,}원 (등락: {s_change}%)
                - 거래대금: {s_value // 100000000}억원
                - 수급: {supply_text}
                
                [최신 뉴스]
                {news_text}
                """

            system_prompt = "당신은 주식 투자 전문가입니다. 시장 상황, 수급, 뉴스를 종합적으로 분석하여 투자 판단을 내리세요."
            user_prompt = f"""
            {market_context}

            다음 종목들을 분석하여 투자 매력도를 평가하세요.
            문서에 정의된 '종합 분석' 기준을 따릅니다.

            [입력 데이터]
            {stocks_text}

            [평가 기준]
            1. **Score (0-3)**: 뉴스/재료 기반 호재 강도
               - 3점: 확실한 호재 (대규모 수주, 상한가 재료, 어닝 서프라이즈)
               - 2점: 긍정적 호재 (실적 개선, 기대감, 테마 상승)
               - 1점: 단순/중립적 소식
               - 0점: 악재 또는 별다른 호재 없음
            2. **Action**: BUY / HOLD / SELL
            3. **Confidence**: 확신도 (0-100%)
            4. **Reason**: 다음 요소를 종합하여 간결하게 작성하세요.
               - 뉴스/재료 분석 (호재 여부)
               - 수급 동향 (외인/기관)
               - 종합 투자 의견

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

            response_content = ""
            
            # API Timeout 설정 (Provider별 분기)
            is_analysis_llm = self.provider == 'gemini'
            API_TIMEOUT = app_config.ANALYSIS_LLM_API_TIMEOUT if is_analysis_llm else app_config.LLM_API_TIMEOUT
            
            logger.info(f"[{self.provider.upper()}] LLM API 호출 시작 (Timeout: {API_TIMEOUT}s)...")

            try:
                if self.provider == 'zai':
                    # Z.ai - Blocking Call -> Thread
                    def _call_zai_batch():
                        return self.client.chat.completions.create(
                            model=app_config.ZAI_MODEL,
                            messages=[
                                {"role": "system", "content": system_prompt},
                                {"role": "user", "content": user_prompt}
                            ],
                            temperature=0.1
                        )

                    completion = await asyncio.wait_for(asyncio.to_thread(_call_zai_batch), timeout=API_TIMEOUT)
                    response_content = completion.choices[0].message.content
                    logger.info(f"[ZAI] API 응답 수신 완료 (길이: {len(response_content)} chars)")
                else:
                # Gemini - Blocking Call -> Thread
                    full_prompt = system_prompt + "\n" + user_prompt
                    
                    def _call_gemini_batch():
                        return self.client.models.generate_content(
                            model=app_config.GEMINI_MODEL,
                            contents=full_prompt
                        )

                    # Retry Logic for Batch
                    max_retries = 3
                    for attempt in range(max_retries):
                        try:
                            # Use wait_for for timeout within the retry loop
                            resp = await asyncio.wait_for(asyncio.to_thread(_call_gemini_batch), timeout=API_TIMEOUT)
                            response_content = resp.text
                            logger.info(f"[GEMINI] API 응답 수신 완료 (길이: {len(response_content)} chars)")
                            break
                        except asyncio.TimeoutError:
                            logger.warning(f"[GEMINI] Batch Analysis Timeout (Attempt {attempt+1}/{max_retries})")
                            if attempt == max_retries - 1: raise
                            continue
                        except Exception as e:
                            if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                                if attempt < max_retries - 1:
                                    wait_time = (2 ** attempt) + 1
                                    logger.warning(f"[GEMINI] Rate limit (429) hit during batch. Retrying in {wait_time}s... ({attempt+1}/{max_retries})")
                                    await asyncio.sleep(wait_time)
                                    continue
                            raise e
            except asyncio.TimeoutError:
                logger.error(f"[{self.provider.upper()}] Batch Analysis Timeout after {API_TIMEOUT}s")
                return {}

            # JSON 파싱
            import re
            import json
            
            result_text = response_content.strip()
            json_match = re.search(r'\[.*\]', result_text, re.DOTALL)
            json_str = json_match.group(0) if json_match else result_text
            
            results_list = json.loads(json_str)
            logger.info(f"[{self.provider.upper()}] JSON 파싱 성공: {len(results_list)}개 종목 분석 결과")
            
            # Map 변환
            final_map = {}
            for item in results_list:
                name = item.get("name")
                if name:
                    final_map[name] = {
                        "score": item.get("score", 0),
                        "action": item.get("action", "HOLD"),
                        "confidence": item.get("confidence", 0),
                        "action": item.get("action", "HOLD"),
                        "confidence": item.get("confidence", 0),
                        "reason": item.get("reason", ""),
                        "model": app_config.ZAI_MODEL if self.provider == 'zai' else app_config.GEMINI_MODEL
                    }
                    logger.debug(f"  → {name}: {item.get('action')} (Score: {item.get('score')}, Conf: {item.get('confidence')}%)")
            
            logger.info(f"[{self.provider.upper()}] 최종 매핑 완료: {list(final_map.keys())}")
            return final_map

        except Exception as e:
            logger.error(f"{self.provider} 배치 분석 실패: {e}")
            return {}
        finally:
            elapsed = time.time() - start_time
            logger.info(f"[{self.provider.upper()}] Batch Analysis ({len(items)} stocks): {elapsed:.2f}s")

    async def generate_market_summary(self, signals: List[Dict]) -> str:
        """
        최종 시장 요약 리포트 생성 (Z.ai / Gemini)
        Args:
            signals: 시그널 리스트 (최종 선별된 종목들)
        Returns:
            str: 요약 텍스트
        """
        if not self.client or not signals:
            return "분석된 종목이 없거나 AI 클라이언트가 설정되지 않았습니다."

        try:
            # 상위 30개 종목만 추출하여 요약 (토큰 절약)
            # S급, A급 우선 정렬
            sorted_signals = sorted(signals, key=lambda x: x.get('score', {}).get('total', 0), reverse=True)
            top_signals = sorted_signals[:30]
            
            stocks_text = ""
            for s in top_signals:
                grade = s.get('grade', 'C')
                score = s.get('score', {}).get('total', 0)
                name = s.get('stock_name', '')
                reason = s.get('score', {}).get('llm_reason', '')
                
                stocks_text += f"- {name} ({grade}급/{score}점): {reason}\n"

            system_prompt = "당신은 주식 시장 분석 전문가입니다. 오늘의 포착된 종목들을 바탕으로 시장의 주도 테마와 분위기를 요약해주세요."
            user_prompt = f"""
            오늘 '종가베팅' 알고리즘에 포착된 상위 종목 리스트입니다.
            이들을 분석하여 다음 내용을 포함한 3~5줄 내외의 시장 요약 리포트를 작성해주세요.

            1. 오늘의 주도 섹터/테마
            2. 시장의 전반적인 분위기 (수급 강도 등)
            3. 특히 주목할만한 특징

            [종목 리스트]
            {stocks_text}
            
            [출력 형식]
            줄글 형태로 간결하게 요약. (Markdown 사용 가능)
            """

            response_content = ""
            
            if self.provider == 'zai':
                # Z.ai - Blocking Call -> Thread
                def _call_zai_summary():
                    return self.client.chat.completions.create(
                        model=app_config.ZAI_MODEL,
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt}
                        ],
                        temperature=0.3
                    )
                
                completion = await asyncio.to_thread(_call_zai_summary)
                response_content = completion.choices[0].message.content
            else:
                # Gemini - Blocking Call -> Thread
                full_prompt = system_prompt + "\n" + user_prompt
                
                def _call_gemini_summary():
                    return self.client.models.generate_content(
                        model=app_config.GEMINI_MODEL,
                        contents=full_prompt
                    )

                response = await asyncio.to_thread(_call_gemini_summary)
                response_content = response.text
                
            return response_content.strip()

        except Exception as e:
            logger.error(f"{self.provider} 시장 요약 실패: {e}")
            return f"시장 요약 생성 실패: {str(e)}"
