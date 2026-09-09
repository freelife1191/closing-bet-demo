#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Engine - Global Constants and Thresholds

기존 외부 import 호환을 위해 상수 정의를 재노출한다.
"""

from __future__ import annotations

from typing import Final

from engine.constants_market_scoring import (
    BollingerThresholds,
    CandlestickThresholds,
    NewsThresholds,
    PriceChangeThresholds,
    ScoringThresholds,
    SupplyThresholds,
    TradingValueThresholds,
    VCPThresholds,
    VolumeThresholds,
)
from engine.constants_market_system import (
    FXThresholds,
    FilePaths,
    GradeLabels,
    LLMThresholds,
    MarketGateThresholds,
    ResponseStatus,
    ScreeningConfig,
    StatusLabels,
    TickerSymbols,
)


TRADING_VALUES: Final[TradingValueThresholds] = TradingValueThresholds()
VCP_THRESHOLDS: Final[VCPThresholds] = VCPThresholds()
SCORING: Final[ScoringThresholds] = ScoringThresholds()
VOLUME: Final[VolumeThresholds] = VolumeThresholds()
PRICE_CHANGE: Final[PriceChangeThresholds] = PriceChangeThresholds()
FX: Final[FXThresholds] = FXThresholds()
MARKET_GATE: Final[MarketGateThresholds] = MarketGateThresholds()
SUPPLY: Final[SupplyThresholds] = SupplyThresholds()
BOLLINGER: Final[BollingerThresholds] = BollingerThresholds()
CANDLESTICK: Final[CandlestickThresholds] = CandlestickThresholds()
LLM: Final[LLMThresholds] = LLMThresholds()
NEWS: Final[NewsThresholds] = NewsThresholds()
SCREENING: Final[ScreeningConfig] = ScreeningConfig()
FILE_PATHS: Final[FilePaths] = FilePaths()
TICKERS: Final[TickerSymbols] = TickerSymbols()

# 종가베팅 생성·누락 보정·성과 계산이 함께 쓰는 기본 익절/손절 폭이다.
JONGGA_TARGET_PCT: Final[float] = 0.05
JONGGA_STOP_PCT: Final[float] = 0.03


__all__ = [
    "BOLLINGER",
    "CANDLESTICK",
    "FILE_PATHS",
    "FX",
    "LLM",
    "JONGGA_STOP_PCT",
    "JONGGA_TARGET_PCT",
    "MARKET_GATE",
    "NEWS",
    "PRICE_CHANGE",
    "SCORING",
    "SCREENING",
    "SUPPLY",
    "TICKERS",
    "TRADING_VALUES",
    "VCP_THRESHOLDS",
    "VOLUME",
    "BollingerThresholds",
    "CandlestickThresholds",
    "FXThresholds",
    "FilePaths",
    "GradeLabels",
    "LLMThresholds",
    "MarketGateThresholds",
    "NewsThresholds",
    "PriceChangeThresholds",
    "ResponseStatus",
    "ScoringThresholds",
    "ScreeningConfig",
    "StatusLabels",
    "SupplyThresholds",
    "TickerSymbols",
    "TradingValueThresholds",
    "VCPThresholds",
    "VolumeThresholds",
]
