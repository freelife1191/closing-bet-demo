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
    # 18점 점수 시스템 (종가베팅)
    max_score: int = 18

    # 등급 기준
    min_s_grade: int = 10
    min_a_grade: int = 8
    min_b_grade: int = 6

    # 거래대금 기준 (원) - 2026-02-08 업데이트 (Dos 조건 반영)
    trading_value_s: int = 1_000_000_000_000  # 1조
    trading_value_a: int = 500_000_000_000    # 5000억
    trading_value_b: int = 100_000_000_000    # 1000억
    trading_value_c: int = 50_000_000_000     # 500억
    trading_value_min: int = 50_000_000_000   # 500억 (문서 기준)

    # 자금 관리
    capital: float = 50_000_000  # 5천만원
    risk_per_trade: float = 0.005  # 0.5% (R값)
    max_positions: int = 10

    # 손절/익절 (User Request: +5%, -3%)
    stop_loss_pct: float = 0.03  # -3%
    take_profit_pct: float = 0.05  # +5%
    r_multiplier: int = 3  # R:Reward = 3:5 approx (Not strictly 1:3 anymore, but keeping field)


@dataclass 
class MarketGateConfig:
    """Market Gate 설정 - 시장 진입 조건"""
    # 환율 기준 (USD/KRW)
    # 환율 기준 (New Normal Regime applied 2026-02-08)
    usd_krw_safe: float = 1420.0            # 안전 (초록) - 1420 이하
    usd_krw_warning: float = 1450.0         # 주의 (노랑) - 1450 이하
    usd_krw_danger: float = 1480.0          # 위험 (빨강) - 1480 이상 (Penalty)
    
    # KOSPI 기준
    kospi_ma_short: int = 20                # 단기 이평
    kospi_ma_long: int = 60                 # 장기 이평
    
    # 외인 수급 기준
    foreign_net_buy_threshold: int = 500_000_000_000  # 5000억원 순매수



class AppConfig:
    """애플리케이션 설정 (Dynamic)"""
    
    @property
    def GOOGLE_API_KEY(self):
        return os.getenv("GOOGLE_API_KEY", "")

    @property
    def OPENAI_API_KEY(self):
        return os.getenv("OPENAI_API_KEY", "")

    @property
    def GEMINI_MODEL(self):
        """챗봇용 Gemini 모델"""
        return os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

    @property
    def ANALYSIS_GEMINI_MODEL(self):
        """종가베팅 분석 엔진용 Gemini 모델"""
        return os.getenv("ANALYSIS_GEMINI_MODEL", "gemini-2.0-flash")

    @property
    def OPENAI_MODEL(self):
        return os.getenv("OPENAI_MODEL", "gpt-4o")

    # Z.ai 설정
    @property
    def LLM_PROVIDER(self):
        return os.getenv("LLM_PROVIDER", "gemini")

    @property
    def ZAI_API_KEY(self):
        return os.getenv("ZAI_API_KEY", "")

    @property
    def ZAI_BASE_URL(self):
        return os.getenv("ZAI_BASE_URL", "https://api.z.ai/v1")

    @property
    def ZAI_MODEL(self):
        return os.getenv("ZAI_MODEL", "coding-plan")
        
    @property
    def LLM_CONCURRENCY(self):
        return int(os.getenv("LLM_CONCURRENCY", 2))

    @property
    def LLM_CHUNK_SIZE(self):
        return int(os.getenv("LLM_CHUNK_SIZE", 2))

    @property
    def LLM_API_TIMEOUT(self):
        return int(os.getenv("LLM_API_TIMEOUT", 120))

    # Analysis LLM 설정
    @property
    def ANALYSIS_LLM_CONCURRENCY(self):
        return int(os.getenv("ANALYSIS_LLM_CONCURRENCY", 1))

    @property
    def ANALYSIS_LLM_CHUNK_SIZE(self):
        return int(os.getenv("ANALYSIS_LLM_CHUNK_SIZE", 2))

    @property
    def ANALYSIS_LLM_API_TIMEOUT(self):
        return int(os.getenv("ANALYSIS_LLM_API_TIMEOUT", 120))
    
    @property
    def ANALYSIS_LLM_REQUEST_DELAY(self):
        """API 호출 간 강제 대기 시간 (초)"""
        return float(os.getenv("ANALYSIS_LLM_REQUEST_DELAY", 5.0))

    # VCP Signals AI Analysis Settings
    @property
    def VCP_SECOND_PROVIDER(self):
        return os.getenv("VCP_SECOND_PROVIDER", "gpt").lower()
    
    @property
    def VCP_AI_PROVIDERS(self):
        _vcp_providers = os.getenv("VCP_AI_PROVIDERS", "gemini,gpt")
        return [p.strip().lower() for p in _vcp_providers.split(",") if p.strip()]

    @property
    def VCP_GEMINI_MODEL(self):
        return os.getenv("VCP_GEMINI_MODEL", "gemini-flash-latest")

    @property
    def VCP_GPT_MODEL(self):
        return os.getenv("VCP_GPT_MODEL", "gpt-4o")

    @property
    def VCP_PERPLEXITY_MODEL(self):
        return os.getenv("VCP_PERPLEXITY_MODEL", "sonar-pro")

    @property
    def PERPLEXITY_API_KEY(self):
        return os.getenv("PERPLEXITY_API_KEY", "").strip()

    @property
    def DATA_SOURCE(self):
        return os.getenv("DATA_SOURCE", "krx")

    @property
    def PRICE_CACHE_TTL(self):
        return int(os.getenv("PRICE_CACHE_TTL", 300))

    @property
    def MARKET_GATE_UPDATE_INTERVAL_MINUTES(self):
        val = os.getenv("MARKET_GATE_UPDATE_INTERVAL_MINUTES", "30")
        try:
            return int(val)
        except:
            return 30
    
    @MARKET_GATE_UPDATE_INTERVAL_MINUTES.setter
    def MARKET_GATE_UPDATE_INTERVAL_MINUTES(self, value):
        # Setter support for runtime update (optional, but requested in previous code)
        os.environ["MARKET_GATE_UPDATE_INTERVAL_MINUTES"] = str(value)

    @property
    def SCHEDULER_ENABLED(self):
        """스케줄러 활성화 여부"""
        return os.getenv("SCHEDULER_ENABLED", "true").lower() == "true"


config = SignalConfig()
app_config = AppConfig()
