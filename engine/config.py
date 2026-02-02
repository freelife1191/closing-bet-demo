#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Engine - Configuration for 종가베팅
"""
from dataclasses import dataclass
from typing import List, Literal
from enum import Enum
import os
from dotenv import load_dotenv

load_dotenv(override=True)


class Grade(Enum):
    """종목 등급"""
    S = "S"  # 최고 - 풀배팅
    A = "A"  # 우수 - 기본배팅
    B = "B"  # 보통 - 절반배팅
    C = "C"  # 미달 - 매매안함

@dataclass
class SignalConfig:
    """시그널 생성 설정"""
    # 12점 점수 시스템
    max_score: int = 12

    # 등급 기준
    min_s_grade: int = 10
    min_a_grade: int = 8
    min_b_grade: int = 6

    # 거래대금 기준 (원) - 2026-01-31 업데이트
    trading_value_s: int = 1_000_000_000_000  # 1조 → 3점
    trading_value_a: int = 500_000_000_000    # 5000억 → 2점
    trading_value_b: int = 100_000_000_000    # 1000억 → 1점 (사용자 기준 반영)
    trading_value_c: int = 50_000_000_000     # 500억 → C급 기준
    trading_value_min: int = 30_000_000_000   # 300억 → 수집 최소 기준

    # 자금 관리
    capital: float = 50_000_000  # 5천만원
    risk_per_trade: float = 0.005  # 0.5% (R값)
    max_positions: int = 10

    # 손절/익절
    stop_loss_pct: float = 0.03  # -3%
    take_profit_pct: float = 0.05  # +5%
    r_multiplier: int = 3  # R:Reward = 1:3


@dataclass 
class MarketGateConfig:
    """Market Gate 설정 - 시장 진입 조건"""
    # 환율 기준 (USD/KRW)
    usd_krw_safe: float = 1350.0            # 안전 (초록)
    usd_krw_warning: float = 1400.0         # 주의 (노랑)
    usd_krw_danger: float = 1450.0          # 위험 (빨강)
    
    # KOSPI 기준
    kospi_ma_short: int = 20                # 단기 이평
    kospi_ma_long: int = 60                 # 장기 이평
    
    # 외인 수급 기준
    foreign_net_buy_threshold: int = 500_000_000_000  # 5000억원 순매수


class AppConfig:
    """애플리케이션 설정"""
    GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

    GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
    OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")

    # Z.ai 설정
    LLM_PROVIDER = os.getenv("LLM_PROVIDER", "gemini")  # gemini or zai
    ZAI_API_KEY = os.getenv("ZAI_API_KEY", "")
    ZAI_BASE_URL = os.getenv("ZAI_BASE_URL", "https://api.z.ai/v1")  # 기본값 설정
    ZAI_MODEL = os.getenv("ZAI_MODEL", "coding-plan")  # 기본값: coding-plan
    LLM_CONCURRENCY = int(os.getenv("LLM_CONCURRENCY", 2))  # 동시 요청 수 제한 (기본 2)
    LLM_CHUNK_SIZE = int(os.getenv("LLM_CHUNK_SIZE", 2))    # 한 번의 요청에 포함할 종목 수 (기본 2)
    LLM_API_TIMEOUT = int(os.getenv("LLM_API_TIMEOUT", 120))  # LLM API 타임아웃 (초, 기본 120)

    # Analysis LLM 설정 (Gemini 등)
    ANALYSIS_LLM_CONCURRENCY = int(os.getenv("ANALYSIS_LLM_CONCURRENCY", 2))
    ANALYSIS_LLM_CHUNK_SIZE = int(os.getenv("ANALYSIS_LLM_CHUNK_SIZE", 2))
    ANALYSIS_LLM_API_TIMEOUT = int(os.getenv("ANALYSIS_LLM_API_TIMEOUT", 120))

    # VCP Signals AI 분석 전용 설정 (멀티 AI 지원)
    # VCP_AI_PROVIDERS: 쉼표로 구분된 AI 목록 (gemini,gpt,perplexity)
    # VCP_SECOND_PROVIDER: gemini 외에 추가로 사용할 AI (gpt 또는 perplexity)
    VCP_SECOND_PROVIDER = os.getenv("VCP_SECOND_PROVIDER", "gpt").lower()
    
    _vcp_providers = os.getenv("VCP_AI_PROVIDERS", "gemini,gpt")
    VCP_AI_PROVIDERS = [p.strip().lower() for p in _vcp_providers.split(",") if p.strip()]
    
    # 각 AI별 모델 설정
    VCP_GEMINI_MODEL = os.getenv("VCP_GEMINI_MODEL", "gemini-flash-latest")
    VCP_GPT_MODEL = os.getenv("VCP_GPT_MODEL", "gpt-4o")
    VCP_PERPLEXITY_MODEL = os.getenv("VCP_PERPLEXITY_MODEL", "sonar-pro")

    # Perplexity API Key
    PERPLEXITY_API_KEY = os.getenv("PERPLEXITY_API_KEY", "").strip()

    # 데이터 소스
    DATA_SOURCE = os.getenv("DATA_SOURCE", "krx")

    # 캐시
    PRICE_CACHE_TTL = int(os.getenv("PRICE_CACHE_TTL", 300))

    # Market Gate Update Interval
    MARKET_GATE_UPDATE_INTERVAL_MINUTES = int(os.getenv("MARKET_GATE_UPDATE_INTERVAL_MINUTES", 30))


config = SignalConfig()
app_config = AppConfig()
