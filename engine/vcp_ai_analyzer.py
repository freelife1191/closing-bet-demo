#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VCP AI Analyzer - 멀티 AI 분석 (Gemini + GPT/Perplexity 지원)
"""
import os
import logging
import time
import json
import asyncio
import httpx
import random
from typing import List, Dict, Optional
from concurrent.futures import ThreadPoolExecutor

from engine.config import app_config

logger = logging.getLogger(__name__)


class VCPMultiAIAnalyzer:
    """VCP 시그널 멀티 AI 분석기 (Gemini + GPT/Perplexity 동시 분석)"""

    def __init__(self):
        self.providers = app_config.VCP_AI_PROVIDERS
        self.gemini_client = None
        self.gpt_client = None
        
        logger.info(f"VCP MultiAI 분석기 초기화: {self.providers}")
        
        # Gemini 초기화
        if 'gemini' in self.providers:
            api_key = app_config.GOOGLE_API_KEY
            if api_key:
                try:
                    from google import genai
                    self.gemini_client = genai.Client(api_key=api_key)
                    logger.info("✅ Gemini 클라이언트 초기화 성공")
                except Exception as e:
                    logger.error(f"Gemini 초기화 실패: {e}")
            else:
                logger.warning("GOOGLE_API_KEY가 설정되지 않아 Gemini 사용 불가")
        
        # GPT (OpenAI) 초기화
        if 'gpt' in self.providers or 'openai' in self.providers:
            api_key = app_config.OPENAI_API_KEY
            if api_key:
                try:
                    from openai import OpenAI
                    self.gpt_client = OpenAI(api_key=api_key)
                    logger.info("✅ GPT (OpenAI) 클라이언트 초기화 성공")
                except Exception as e:
                    logger.error(f"GPT 초기화 실패: {e}")
            else:
                logger.warning("OPENAI_API_KEY가 설정되지 않아 GPT 사용 불가")

        # Perplexity - httpx 직접 사용하므로 클라이언트 초기화 불필요
        self.perplexity_client = None 
        self.perplexity_disabled = False # Circuit Breaker Flag

        if 'perplexity' in self.providers or app_config.VCP_SECOND_PROVIDER == 'perplexity':
            if not app_config.PERPLEXITY_API_KEY:
                logger.warning("PERPLEXITY_API_KEY가 설정되지 않아 Perplexity 사용 불가")
                self.perplexity_disabled = True
    
    def _build_vcp_prompt(self, stock_name: str, stock_data: Dict) -> str:
        """VCP 분석용 프롬프트 생성"""
        return f"""
당신은 주식 투자 전문가입니다. VCP(Volatility Contraction Pattern) 패턴 종목을 분석하세요.

[종목 정보]
- 종목명: {stock_name}
- 현재가: {stock_data.get('current_price', 'N/A')}
- VCP 점수: {stock_data.get('vcp_score', 'N/A')}
- 수축 비율: {stock_data.get('contraction_ratio', 'N/A')}
- 외국인 5일 순매수: {stock_data.get('foreign_5d', 'N/A')}주
- 기관 5일 순매수: {stock_data.get('inst_5d', 'N/A')}주

[분석 요청]
1. VCP 패턴과 수급 상황을 종합 분석
2. 매수/매도/관망 의견 제시
3. 신뢰도(0-100%) 평가

[출력 형식 - 반드시 JSON만 출력]
{{"action": "BUY|SELL|HOLD", "confidence": 75, "reason": "분석 요약 (한국어, 2-3문장)"}}
"""
    
    async def _analyze_with_gemini(self, stock_name: str, stock_data: Dict) -> Optional[Dict]:
        """Gemini로 분석 (Retry Logic 적용)"""
        if not self.gemini_client:
            return None
        
        max_retries = 3
        base_delay = 2
        
        for attempt in range(max_retries + 1):
            try:
                prompt = self._build_vcp_prompt(stock_name, stock_data)
                model = app_config.VCP_GEMINI_MODEL
                
                start = time.time()
                
                # Gemini API 호출 (동기 호출을 executor로 실행)
                def _call():
                    response = self.gemini_client.models.generate_content(
                        model=model,
                        contents=prompt
                    )
                    return response.text
                
                loop = asyncio.get_event_loop()
                with ThreadPoolExecutor() as executor:
                    response_text = await loop.run_in_executor(executor, _call)
                
                elapsed = time.time() - start
                logger.debug(f"[Gemini] {stock_name} 분석 완료 ({elapsed:.2f}s)")
                
                # JSON 파싱
                result = self._parse_json_response(response_text)
                return result
                
            except Exception as e:
                error_msg = str(e)
                if attempt < max_retries and ('429' in error_msg or 'Resource exhausted' in error_msg or 'Quota exceeded' in error_msg):
                    delay = base_delay * (2 ** attempt) + (random.randint(0, 1000) / 1000)
                    logger.warning(f"[Gemini] {stock_name} 429 Error. Retrying in {delay:.2f}s... ({attempt+1}/{max_retries})")
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"[Gemini] {stock_name} 분석 실패 (Final): {e}")
                    return None
        return None
    
    async def _analyze_with_gpt(self, stock_name: str, stock_data: Dict) -> Optional[Dict]:
        """GPT로 분석"""
        if not self.gpt_client:
            return None
        
        try:
            prompt = self._build_vcp_prompt(stock_name, stock_data)
            model = app_config.VCP_GPT_MODEL
            
            start = time.time()
            
            # GPT API 호출 (동기 호출을 executor로 실행)
            def _call():
                response = self.gpt_client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": "당신은 주식 투자 전문가입니다. JSON 형식으로만 응답하세요."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.7,
                    max_tokens=500
                )
                return response.choices[0].message.content
            
            loop = asyncio.get_event_loop()
            with ThreadPoolExecutor() as executor:
                response_text = await loop.run_in_executor(executor, _call)
            
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
        try:
            # 마크다운 코드 블록 제거
            text = text.strip()
            if text.startswith("```"):
                lines = text.split("\n")
                text = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])
            
            # JSON 파싱
            result = json.loads(text)
            
            # 필수 필드 검증
            if 'action' in result and 'confidence' in result:
                # action 정규화
                action = result['action'].upper()
                if action in ['BUY', 'SELL', 'HOLD']:
                    result['action'] = action
                else:
                    result['action'] = 'HOLD'
                return result
            
        except json.JSONDecodeError:
            # JSON 추출 시도
            import re
            match = re.search(r'\{[^}]+\}', text, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group())
                except:
                    pass
        
        return None
    
    async def analyze_stock(self, stock_name: str, stock_data: Dict) -> Dict:
        """단일 종목 멀티 AI 분석 (Gemini + GPT/Perplexity 동시 실행 - 병렬 처리)"""
        results = {
            'ticker': stock_data.get('ticker', ''),
            'stock_name': stock_name,
            'gemini_recommendation': None,
            'gpt_recommendation': None,
            'perplexity_recommendation': None
        }
        
        # 두 AI 동시 실행을 위한 코루틴 리스트
        tasks = []
        providers_map = [] # 인덱스 매핑용
        
        # 1. Gemini (Primary)
        if 'gemini' in self.providers:
            tasks.append(self._analyze_with_gemini(stock_name, stock_data))
            providers_map.append('gemini')
        
        # 2. Second Provider (GPT or Perplexity)
        second_provider = app_config.VCP_SECOND_PROVIDER  # gpt or perplexity
        
        if second_provider == 'perplexity' and ('perplexity' in self.providers or 'gpt' in self.providers): # Fallback logic in init suggests checking list
             if not self.perplexity_disabled:
                 tasks.append(self._analyze_with_perplexity(stock_name, stock_data))
                 providers_map.append('perplexity')
        elif second_provider == 'gpt' and ('gpt' in self.providers or 'openai' in self.providers):
             tasks.append(self._analyze_with_gpt(stock_name, stock_data))
             providers_map.append('gpt')
        
        if not tasks:
            logger.warning(f"{stock_name}: 실행 가능한 AI Provider가 없습니다.")
            return results

        # 병렬 실행 (asyncio.gather)
        try:
            # return_exceptions=True로 하여 하나가 실패해도 나머지는 건짐
            responses = await asyncio.gather(*tasks, return_exceptions=True)
            
            for i, result in enumerate(responses):
                provider = providers_map[i]
                if isinstance(result, Exception):
                    logger.error(f"[{provider}] {stock_name} 분석 중 예외 발생: {result}")
                elif result:
                    results[f'{provider}_recommendation'] = result
                    # logger.info(f"[{provider}] {stock_name} 분석 결과 수신 완료") # 너무 시끄러울 수 있으므로 생략하거나 DEBUG
                else:
                    logger.warning(f"[{provider}] {stock_name} 분석 결과 없음 (None)")

        except Exception as e:
            logger.error(f"{stock_name} AI 병렬 분석 전체 실패: {e}")
        
        return results
    
    async def _analyze_with_perplexity(self, stock_name: str, stock_data: Dict) -> Optional[Dict]:
        """Perplexity로 분석 (httpx 사용 - Retry Logic 적용)"""
        if not app_config.PERPLEXITY_API_KEY or self.perplexity_disabled:
            return None
        
        max_retries = 3
        base_delay = 2
        
        for attempt in range(max_retries + 1):
            try:
                prompt = self._build_vcp_prompt(stock_name, stock_data)
                model = app_config.VCP_PERPLEXITY_MODEL
                url = "https://api.perplexity.ai/chat/completions"
                headers = {
                    "Authorization": f"Bearer {app_config.PERPLEXITY_API_KEY}",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
                }
                payload = {
                    "model": model,
                    "messages": [
                        {"role": "system", "content": "당신은 주식 투자 전문가입니다. JSON 형식으로만 응답하세요. 정확하고 통찰력 있는 분석을 제공하세요."},
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.2
                }
                
                
                start = time.time()
                
                async with httpx.AsyncClient(timeout=60.0) as client:
                    response = await client.post(url, headers=headers, json=payload)
                
                if response.status_code == 429:
                    if attempt < max_retries:
                        delay = base_delay * (2 ** attempt) + (random.randint(0, 1000) / 1000)
                        logger.warning(f"[Perplexity] {stock_name} 429 Error. Retrying in {delay:.2f}s... ({attempt+1}/{max_retries})")
                        await asyncio.sleep(delay)
                        continue
                    else:
                        logger.error(f"[Perplexity] Max retries exceeded for {stock_name}")
                        return None
                    
                if response.status_code != 200:
                    logger.error(f"[Perplexity] API Error: {response.status_code} - {response.text[:200]}")
                    # 401/403 인증 에러 발생 시 서킷 브레이커 발동 (이후 요청 생략)
                    if response.status_code in [401, 403]:
                        logger.warning("[Perplexity] 인증 오류 발생. 이번 세션에서 Perplexity 분석을 비활성화합니다.")
                        self.perplexity_disabled = True
                    return None
                
                response_json = response.json()
                response_text = response_json['choices'][0]['message']['content']
                
                elapsed = time.time() - start
                logger.debug(f"[Perplexity] {stock_name} 분석 완료 ({elapsed:.2f}s)")
                
                # JSON 파싱
                result = self._parse_json_response(response_text)
                return result
                
            except Exception as e:
                logger.error(f"[Perplexity] {stock_name} 분석 실패: {e}")
                return None
        return None
    
    async def analyze_batch(self, stocks: List[Dict]) -> Dict[str, Dict]:
        """여러 종목 일괄 분석 (완전 병렬 처리 + 진행률 로그)"""
        results = {}
        total = len(stocks)
        concurrency = getattr(app_config, 'ANALYSIS_LLM_CONCURRENCY', 2)
        logger.info(f"VCP AI 일괄 분석 시작: 총 {total}개 종목 (Concurrency: {concurrency})")
        
        # 동시 실행 제한 (Rate Limit 고려)
        sem = asyncio.Semaphore(concurrency) 
        
        async def _bounded_analyze(stock, idx):
            async with sem:
                ticker = stock.get('ticker', '')
                name = stock.get('name', ticker)
                # logger.info(f"[{idx+1}/{total}] {name} AI 분석 시작...") # 너무 많으면 생략
                try:
                    res = await self.analyze_stock(name, stock)
                    logger.info(f"✅ [{idx+1}/{total}] {name} AI 분석 완료") # 진행 상황 가시화
                    return ticker, res
                except Exception as e:
                    logger.error(f"❌ [{idx+1}/{total}] {name} 분석 실패: {e}")
                    return ticker, None

        # Task 생성
        tasks = [_bounded_analyze(stocks[i], i) for i in range(total)]
        
        # 전체 동시 실행
        batch_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        success_count = 0
        for item in batch_results:
            if isinstance(item, Exception):
                logger.error(f"배치 작업 중 예외 발생: {item}")
                continue
            if item:
                ticker, res = item
                if res:
                    results[ticker] = res
                    success_count += 1
        
        logger.info(f"VCP AI 일괄 분석 종료: 성공 {success_count}/{total}건")
        return results
    
    def get_available_providers(self) -> List[str]:
        """현재 사용 가능한 AI 제공자 목록"""
        available = []
        if self.gemini_client:
            available.append('gemini')
        if self.gpt_client:
            available.append('gpt')
        if app_config.PERPLEXITY_API_KEY:
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
