#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Engine - Market Gate (시장 상태 분석)
PART 1 (Macro) & PART 7 (Technical) 통합 분석

Refactored to use GlobalDataFetcher for cleaner global data collection.
"""
import json
import logging
import os
from datetime import datetime
from typing import Dict, Tuple, Any

import pandas as pd

# Import GlobalDataFetcher from data_sources module
from engine.data_sources import GlobalDataFetcher, DataSourceManager
from engine.market_gate_logic import (
    build_default_result as _build_default_result_impl,
    calculate_indicators as _calculate_indicators_impl,
    fetch_benchmark_data as _fetch_benchmark_data_impl,
    get_global_data as _get_global_data_impl,
    get_sector_data as _get_sector_data_impl,
    get_usd_krw as _get_usd_krw_impl,
    load_price_data as _load_price_data_impl,
    load_supply_data as _load_supply_data_impl,
    resolve_analysis_date_str as _resolve_analysis_date_str_impl,
    sanitize_for_json as _sanitize_for_json_impl,
    score_macro as _score_macro_impl,
    score_macd as _score_macd_impl,
    score_rs as _score_rs_impl,
    score_rsi as _score_rsi_impl,
    score_supply as _score_supply_impl,
    score_trend as _score_trend_impl,
    score_volume as _score_volume_impl,
)
from engine.market_gate_analysis import analyze_market_state
from numpy_json_encoder import NumpyEncoder
from services.kr_market_data_cache_service import atomic_write_text

# Config Import
try:
    from engine.config import MarketGateConfig
except ImportError:
    # Fallback if running standalone
    from dataclasses import dataclass
    @dataclass
    class MarketGateConfig:
        usd_krw_safe: float = 1420.0
        usd_krw_warning: float = 1450.0
        usd_krw_danger: float = 1480.0
        kospi_ma_short: int = 20
        kospi_ma_long: int = 60
        foreign_net_buy_threshold: int = 500_000_000_000

logger = logging.getLogger(__name__)

class MarketGate:
    """시장 상태 분석기 (신호등) - KODEX 200 + 환율 + 수급"""

    def __init__(self, data_dir: str = 'data'):
        self.data_dir = data_dir
        self.kodex_ticker = '069500' # KODEX 200
        self.config = MarketGateConfig()

        # [REFACTORED] Use GlobalDataFetcher for global market data
        self.global_fetcher = GlobalDataFetcher(DataSourceManager())

        # [2026-02-06] KIS 실시간 수급 수집기 초기화
        try:
            from .kis_collector import KisCollector
            self.kis = KisCollector()
        except ImportError:
            self.kis = None
            logger.warning("KisCollector not found. Real-time supply score will be disabled.")

        # 주요 섹터 ETF (KODEX/TIGER)
        self.sectors = {
            '반도체': '091160',      # KODEX 반도체
            '2차전지': '305720',     # TIGER 2차전지테마
            '자동차': '091170',      # KODEX 자동차
            '헬스케어': '102780',    # KODEX 헬스케어
            'IT': '091180',          # TIGER 200 IT
            '은행': '102960',        # KODEX 은행
            '철강': '117680',        # TIGER 200 철강소재
            '증권': '102970',        # KODEX 증권
            '조선': '139230',        # TIGER 200 중공업 (Data replacement for 446910)
            '에너지': '117690',      # KODEX 에너지화학
            'KOSPI 200': '069500'    # KODEX 200
        }
        
    def _fetch_benchmark_data(self, start_date: str, end_date: str) -> pd.DataFrame:
        """KOSPI 지수 데이터 로드 (RS 계산용)"""
        return _fetch_benchmark_data_impl(start_date, end_date, logger)

    def analyze(self, target_date: str = None) -> Dict[str, Any]:
        """시장 상태 분석 실행 (target_date: YYYY-MM-DD)"""
        return analyze_market_state(self, target_date, logger)

    def _get_global_data(self, target_date: str = None) -> dict:
        """
        글로벌 시장 데이터 수집 (Refactored)

        Uses GlobalDataFetcher from data_sources module for cleaner code.
        Returns dict with 'indices', 'commodities', 'crypto', and 'usd_krw' keys.
        """
        return _get_global_data_impl(
            global_fetcher=self.global_fetcher,
            target_date=target_date,
            logger=logger,
        )

    def _get_sector_data(self, target_date: str = None, global_data: dict = None) -> dict:
        """주요 섹터 ETF 등락률 수집 (pykrx 사용)"""
        return _get_sector_data_impl(
            sectors=self.sectors,
            target_date=target_date,
            global_data=global_data,
            logger=logger,
        )

    def _load_price_data(self, target_date: str = None) -> pd.DataFrame:
        """KODEX 200 데이터 로드 및 날짜 필터링 (Fallback: pykrx)"""
        return _load_price_data_impl(
            data_dir=self.data_dir,
            kodex_ticker=self.kodex_ticker,
            target_date=target_date,
            logger=logger,
        )

    def _sanitize_for_json(self, data):
        """JSON 직렬화를 위해 NaN, Infinity 등을 None으로 변환 (Recursive)"""
        return _sanitize_for_json_impl(data)

    def save_analysis(self, result: Dict, target_date: str = None) -> str:
        """분석 결과 JSON 저장"""
        # Sanitize data to remove NaN/Infinity which breaks JS JSON.parse
        result = self._sanitize_for_json(result)
        date_str = _resolve_analysis_date_str_impl(result, target_date)
        payload_json = json.dumps(result, ensure_ascii=False, indent=2, cls=NumpyEncoder)
            
        # 1. 날짜별 파일 저장
        filename = f'market_gate_{date_str}.json'
        filepath = os.path.join(self.data_dir, filename)
        
        try:
            atomic_write_text(filepath, payload_json)
            logger.debug(f"Market Gate 저장 완료: {filepath}")
        except Exception as e:
            logger.error(f"Market Gate 저장 실패: {e}")
            return ""
            
        # 2. 최신 파일(market_gate.json) 갱신 (오늘 날짜이거나 target_date가 없을 때)
        is_today = target_date == datetime.now().strftime('%Y-%m-%d')
        if not target_date or is_today:
            latest_path = os.path.join(self.data_dir, 'market_gate.json')
            try:
                atomic_write_text(latest_path, payload_json)
            except Exception as e:
                logger.error(f"최신 Market Gate 갱신 실패: {e}")
                
        return filepath

    def _get_usd_krw(self) -> float:
        """환율 조회 (FDR -> yfinance) - 실패 시 1350(SAFE) 반환"""
        return _get_usd_krw_impl(logger)

    def _load_supply_data(self) -> Dict:
        """최근 수급 데이터 로드 (실시간 KIS 지원)"""
        return _load_supply_data_impl(
            data_dir=self.data_dir,
            kis=self.kis,
            logger=logger,
        )

    def _calculate_indicators(self, df: pd.DataFrame, bench_df: pd.DataFrame = None) -> pd.DataFrame:
        """기술적 지표 계산 (RS 포함)"""
        return _calculate_indicators_impl(
            df=df,
            bench_df=bench_df,
            config=self.config,
            logger=logger,
        )

    def _score_trend(self, row) -> int:
        """추세 점수 (25점): 정배열"""
        return _score_trend_impl(row)

    def _score_rsi(self, row) -> int:
        """RSI 점수 (25점): 50-70 구간"""
        return _score_rsi_impl(row)

    def _score_macd(self, row) -> int:
        """MACD 점수 (20점): 골든크로스"""
        return _score_macd_impl(row)

    def _score_volume(self, row) -> int:
        """거래량 점수 (15점): 20일 평균 상회"""
        return _score_volume_impl(row)
        
    def _score_rs(self, row) -> int:
        """RS 점수 (15점): KOSPI 대비 강세"""
        return _score_rs_impl(row)

    def _score_macro(self, usd_krw: float) -> Tuple[int, str]:
        """환율 점수 및 상태 (15점 + Penalty)"""
        return _score_macro_impl(usd_krw, self.config)

    def _score_supply(self, data: Dict) -> int:
        """수급 점수 (15점)"""
        return _score_supply_impl(data, self.config)

    def _default_result(self, msg: str) -> Dict[str, Any]:
        """기본 응답"""
        return _build_default_result_impl(msg)
